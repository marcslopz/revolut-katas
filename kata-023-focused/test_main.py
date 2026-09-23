from datetime import datetime, timedelta

from main import (
    Case,
    CaseDto,
    CasePriority,
    CaseService,
    CaseStatus,
    CLAIM_TTL_IN_SECONDS,
)


def test_claim_next_with_all_statuses_should_remove_completed_and_return_unclaimed():
    service = CaseService()

    service.add_case("case_1", CasePriority.HIGH)
    service.add_case("case_2", CasePriority.HIGH)
    service.add_case("case_3", CasePriority.HIGH)

    claimed_at = datetime.now()
    case_1_dto = service.claim_next_case("worker_1", claimed_at)
    assert case_1_dto is not None
    assert case_1_dto.status == CaseStatus.CLAIMED.name.lower()
    assert case_1_dto.claimed_at is not None
    assert case_1_dto.claimed_at == str(claimed_at)

    assert service.get_claim_pool_size() == 3

    claimed_at_2 = claimed_at + timedelta(seconds=(CLAIM_TTL_IN_SECONDS - 2))
    case_2_dto = service.claim_next_case("worker_2", claimed_at_2)
    assert case_2_dto is not None
    assert case_2_dto.status == CaseStatus.CLAIMED.name.lower()
    assert case_2_dto.claimed_at is not None
    assert case_2_dto.claimed_at == str(claimed_at_2)

    assert service.get_claim_pool_size() == 3

    service.mark_case_completed("case_2", "worker_2")
    assert service.get_claim_pool_size() == 3

    case3_dto = service.claim_next_case("worker_3", claimed_at_2)
    assert case3_dto is not None
    assert case3_dto.status == CaseStatus.CLAIMED.name.lower()
    assert case3_dto.claimed_at is not None
    assert case3_dto.claimed_at == str(claimed_at_2)
    assert service.get_claim_pool_size() == 3

    assert service.claim_next_case("worker_3", claimed_at_2) is None

    case_1_dto = service.claim_next_case(
        "worker_1", claimed_at + timedelta(seconds=CLAIM_TTL_IN_SECONDS + 1)
    )
    assert case_1_dto is not None
    assert case_1_dto.case_id == "case_1"

    assert (
        service.claim_next_case(
            "worker_1", claimed_at + timedelta(seconds=CLAIM_TTL_IN_SECONDS + 1)
        )
        is None
    )

    case_3_dto = service.claim_next_case(
        "worker_1", claimed_at_2 + timedelta(seconds=CLAIM_TTL_IN_SECONDS + 1)
    )
    assert case_3_dto is not None
    assert case_3_dto.case_id == "case_3"
