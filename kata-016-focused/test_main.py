from main import AccountService

def test_create_account():
    service = AccountService()
    service.create_account("account_1", 0)

def test_transfer_amount():
    service = AccountService()
    service.create_account("account_1", 1)
    service.create_account("account_2", 0)

    service.transfer("account_1", "account_2", 1)