from main import *

def test_add():
    service = CheckBlockedCardService()

    service.add("1234567890")