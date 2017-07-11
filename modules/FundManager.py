"""
    Provide an interface that allows us to define custom funding sources. These can be extended through plugins
"""

from decimal import Decimal

config = None
api = None
log = None
notify_conf = None
funds = {}

def init(cfg, api1, log1, notify_conf1):
    """
    @type cfg1: modules.Configuration
    @type api1: modules.Poloniex.Poloniex
    @type log1: modules.Logger.Logger
    """
    global config, api, log, notify_conf
    config = cfg
    api = api1
    log = log1
    notify_conf = notify_conf1
    
    # Default Fund Manager with a our built in accounts
    
    accounts = map(str.strip, config.get("FUNDING", "accounts").split(','))
    
    if 'lending' in accounts:
        add_fund( AccountFund('lending'), priority=0)
        
    if 'exchange' in accounts:
        add_fund( AccountFund('exchange'), priority=5)
        
    if 'margin' in accounts:
        add_fund( AccountFund('margin'), priority=5)
    
    
def add_fund(fund, priority=0):
    """
    Add a new funding source. 
    """
        
    if priority not in funds:
        funds[priority] = []
            
    funds[priority].append(fund)
        
    fund.init(config, api, log, notify_conf)
        
def update(name=None):
    """
    Update all funds
    """
        
    for priority in sorted(funds):
        for fund in funds[priority]:
            fund.update(name)
            
def add_balance(cur, account, balance):
    """
    Manually add balance to a fund. Needed to speed things up
    """
        
    for priority in sorted(funds):
        for fund in funds[priority]:
            fund.add_balance(cur, account, balance)

def available_balances():
    """
    Return a list of all balances
    """
    
    totals = {}
    
    for priority in sorted(funds):
        for fund in funds[priority]:
            for cur in fund.currencies:
                if cur not in totals:
                    totals[cur] = Decimal('0.0')
                
                totals[cur] += fund.available_balance(cur)
    
    return totals
    
def currencies():
    """
    Return a list of all currencies
    """
    
    currency_list = []
    
    for priority in sorted(funds):
        for fund in funds[priority]:
            currency_list += fund.currencies()
    
    return list(set(currency_list))

def available_balance(cur):
    """
    Return the balance available for currency
    """
        
    total = Decimal('0.0')
        
    for priority in sorted(funds):
        for fund in funds[priority]:
            total += fund.available_balance(cur)
                
    return total
    
def prepare(cur, account, balance):
    """
    Prepare funding for an amount of balance of currency cur for the account
    This is done by enumerating each fund and executing its prepare function until
    balance is fulfilled.
        
    Returns the balance left unfulfilled
    """
        
    total_needed = Decimal(balance)
    
    print("I need {:.8f} of coin {:s} in account {:s}".format(total_needed, cur, account))
        
    for priority in sorted(funds):
        for fund in funds[priority]:
            total_needed = fund.prepare(cur, account, total_needed)

            if total_needed <= Decimal('0.0'):
                return total_needed
        
    return total_needed
                    
        

class BaseFund(object):

    def init(self, config, api, log, notify_conf):
        self.config = config
        self.api = api
        self.log = log
        self.notify_conf = notify_conf
        
    def add_balance(self, cur, account, balance):
        pass

class AccountFund(BaseFund):
    """
    An AccountFund will provide available funds from accounts
    """

    def __init__(self, account):
        self.balance = {}
        self.account = account
    
    def update(self,name=None):
        if name is None or name == self.account:
            print("DEBUG: Updating Account Fund for: %s" % self.account)
            balance = self.api.return_available_account_balances(self.account)[self.account]
            
            # Empty seems to return a list??
            if isinstance(balance, list):
                balance = {}
            
            # Decimalize it
            self.balance = {k: Decimal(v) for k,v in balance.iteritems()}
            
            
        
    def currencies(self):
        """
        Return list of currencies
        """
        
        return [cur for cur in self.balance]
        
    def available_balance(self, cur):
        """
        Return balance available for currency
        """
        
        if cur not in self.balance:
            return Decimal('0.0')
        
        return Decimal(self.balance[cur])
        
    def add_balance(self, cur, account, balance):
        """
        Manually add balance to account for cur
        """
        
        
        if account == self.account:
            print("  - Adding {:.8f} of coin {:s} to account {:s}".format(balance, cur, account))
            if cur not in self.balance:
                self.balance[cur] = Decimal('0.0')
            
            self.balance[cur] += Decimal(balance)
            
        
    def prepare(self, cur, account, balance):
        """
        Transfer funds from this account to 'account'
        """
        
        if cur not in self.balance:
            return balance
        
        transfer_amount = min(self.available_balance(cur), balance)
        
        # If the destination is not our own account, we need to perform a transfer
        if account != self.account:
        
            if transfer_amount > Decimal('0.0'):
                print("  - Transferring {:.8f} of coin {:s} from {:s} to {:s}".format(transfer_amount, cur, self.account, account))
                msg = self.api.transfer_balance(cur, transfer_amount, self.account, account)
                self.log.log(self.log.digestApiMsg(msg))
                self.log.notify(self.log.digestApiMsg(msg), notify_conf)
            
        
        self.balance[cur] = Decimal(self.balance[cur]) - transfer_amount
        
        
        return balance - transfer_amount


        
        
