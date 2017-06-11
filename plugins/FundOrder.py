#
# Provide funding source from exchange and margin accounts
from plugins.Plugin import Plugin
import modules.Poloniex as Poloniex
from modules import FundManager
from decimal import Decimal


class OpenOrderFund(FundManager.BaseFund): 
    """
    Provides funds from cancellable open orders
    """

    def __init__(self):
        self.orders = {}
    
    def update(self,name=None):
        if name is not None:
            return
    
        print("DEBUG: Updating Open Orders Fund")

        orders = self.api.return_open_orders('all')
        
        self.orders = {}
        
        # Save the orders depending on if they are buy or sell
        for pair in orders:
            left_cur, right_cur = pair.split('_')
            
            for order in orders[pair]:
                order['pair'] = pair
            
                if order['type'] == 'sell':
                    cur = right_cur
                    order['pair_amount'] = Decimal(order['amount'])
                else:
                    cur = left_cur
                    order['pair_amount'] = Decimal(order['total'])
            
                if cur not in self.orders:
                    self.orders[cur] = []
                
                self.orders[cur].append(order)
        
    def currencies(self):
        """
        Return list of currencies
        """
        
        return [cur for cur in self.orders]
        
    def available_balance(self, cur):
        """
        Return balance available for currency
        """
        
        if cur not in self.orders:
            return Decimal('0.0')
        
        return sum([Decimal(order['pair_amount']) for order in self.orders[cur]])
        
    def prepare(self, cur, account, balance):
        """
        Transfer funds from this account to lending
        """
        
        if cur not in self.orders:
            return balance
        
        while len(self.orders[cur]) and balance > Decimal('0.0'):
            order = self.orders[cur].pop(0)

            transfer_amount = min(Decimal(order['pair_amount']), balance)
        
            if transfer_amount > Decimal('0.0'):
                print("  - Cancelling order for {:.8f} of coin {:s} and transfering {:.8f} to {:s}".format(Decimal(order['pair_amount']), cur, transfer_amount, account))
                msg = self.api.cancel(order['pair'], order['orderNumber'])
                self.log.log(self.log.digestApiMsg(msg))
                self.log.notify(self.log.digestApiMsg(msg), self.notify_conf)
            
                msg = self.api.transfer_balance(cur, transfer_amount, 'exchange', account)
                FundManager.add_balance(cur, 'exchange', Decimal(order['pair_amount'])-transfer_amount)
                
                self.log.log(self.log.digestApiMsg(msg))
                self.log.notify(self.log.digestApiMsg(msg), self.notify_conf)
            
            balance -= transfer_amount
        
        return balance



class FundOrder(Plugin):

    def on_bot_init(self):
        super(FundOrder, self).on_bot_init()

        # Add open orders
        FundManager.add_fund( OpenOrderFund(), priority=50)
    