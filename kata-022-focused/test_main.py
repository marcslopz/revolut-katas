from main import *


def test_freeze_card_and_claim():
    service = CardStatusService()
    service.add_card("card_1")
    service.add_card("card_2")

    event_id = service.freeze_card("card_1")

    now = datetime.datetime.now()
    event = service.claim_next_event(now=now)

    assert event is not None
    assert event.claimed_at == now
    assert event.status == EventStatus.CLAIMED.name.lower()
    assert event.event_id == event_id


def test_freeze_card_and_claim_twice_after_ttl():
    service = CardStatusService()
    service.add_card("card_1")
    service.add_card("card_2")

    event_id = service.freeze_card("card_1")

    now = datetime.datetime.now()
    event = service.claim_next_event(now=now)

    assert event is not None
    assert event.claimed_at == now
    assert event.status == EventStatus.CLAIMED.name.lower()
    assert event.event_id == event_id

    after_ttl = now + datetime.timedelta(seconds=(CLAIM_TTL_IN_SECONDS + 1))
    event = service.claim_next_event(now=after_ttl)
    assert event is not None
    assert event.claimed_at == after_ttl
    assert event.status == EventStatus.CLAIMED.name.lower()
    assert event.event_id == event_id


def test_claim_two_events():
    service = CardStatusService()
    service.add_card("card_1")
    service.add_card("card_2")

    now = datetime.datetime.now()

    event1_id = service.freeze_card("card_1")
    event1 = service.claim_next_event(now=now)
    assert event1 is not None
    assert event1.claimed_at == now
    assert event1.status == EventStatus.CLAIMED.name.lower()
    assert event1.event_id == event1_id

    event2_id = service.unfreeze_card("card_2")
    after_now = datetime.datetime.now() + datetime.timedelta(seconds=1)
    event2 = service.claim_next_event(now=after_now)
    assert event2 is not None
    assert event2.event_id == event2_id
    assert event2.claimed_at == after_now
    assert event2.status == EventStatus.CLAIMED.name.lower()
