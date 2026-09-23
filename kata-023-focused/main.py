import dataclasses
import enum
import heapq
import threading
from datetime import datetime, timedelta

CLAIM_TTL_IN_SECONDS = 30


class CasePriority(enum.IntEnum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3


class CaseStatus(enum.IntEnum):
    COMPLETED = 1
    UNCLAIMED = 2
    CLAIMED = 3


@dataclasses.dataclass(frozen=True)
class CaseDto:
    status: str
    priority: str
    created_at: str
    case_id: str
    claimed_at: str
    worker_id: str | None


@dataclasses.dataclass(order=True)
class Case:
    status: CaseStatus
    claimed_at: datetime
    priority: CasePriority
    case_id: str
    created_at: datetime
    worker_id: str | None = dataclasses.field(default=None, compare=False)

    def to_dto(self):
        return CaseDto(
            self.status.name.lower(),
            self.priority.name.lower(),
            str(self.created_at),
            self.case_id,
            str(self.claimed_at),
            self.worker_id,
        )

    def claim_should_be_leased(self, now):
        return self.claimed_at + timedelta(seconds=CLAIM_TTL_IN_SECONDS) < now

    def mark_completed(self, worker_id: str) -> None:
        if self.status == CaseStatus.UNCLAIMED:
            raise ValueError("Unclaimed case can't be completed", self.case_id, worker_id)
        if self.worker_id != worker_id:
            raise ValueError("Worker id mismatch", worker_id, self.worker_id)
        self.status = CaseStatus.COMPLETED




class CaseService:
    def __init__(self):
        self._cases_by_id: dict[str, Case] = {}
        self._ordered_by_status_and_priority: list[Case] = []
        self._lock = threading.Lock()
    def add_case(
        self, case_id: str, priority: int, now: datetime | None = None
    ) -> None:
        with self._lock:
            if case_id in self._cases_by_id:
                raise ValueError("Case already exists", case_id)
            if now is None:
                now = datetime.now()
            case = Case(
                CaseStatus.UNCLAIMED, datetime.min, CasePriority(priority), case_id, now
            )
            self._cases_by_id[case_id] = case
            heapq.heappush(self._ordered_by_status_and_priority, case)

    def claim_next_case(
        self, worker_id: str, now: datetime | None = None
    ) -> CaseDto | None:
        if now is None:
            now = datetime.now()
        with self._lock:
            while self._ordered_by_status_and_priority:
                case = heapq.heappop(self._ordered_by_status_and_priority)
                if case.status == CaseStatus.COMPLETED:
                    continue
                if case.status == CaseStatus.UNCLAIMED:
                    case.status = CaseStatus.CLAIMED
                    case.worker_id = worker_id
                    case.claimed_at = now
                    heapq.heappush(self._ordered_by_status_and_priority, case)
                    return case.to_dto()
                # status is CLAIMED, ordered by claimed_at
                if not case.claim_should_be_leased(now):
                    # No more cases unclaimed or leased-claimed to take, finish here
                    heapq.heappush(self._ordered_by_status_and_priority, case)
                    return None
                # the case is CLAIMED, but can be leased
                case.worker_id = worker_id
                case.claimed_at = now
                heapq.heappush(self._ordered_by_status_and_priority, case)
                return case.to_dto()
        return None

    def mark_case_completed(self, case_id: str, worker_id: str) -> None:
        with self._lock:
            if case_id not in self._cases_by_id:
                raise KeyError("Case not found", case_id)
            case = self._cases_by_id[case_id]
            case.mark_completed(worker_id)

    def get_claim_pool_size(self) -> int:
        with self._lock:
            return len(self._ordered_by_status_and_priority)
