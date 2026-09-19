import datetime
import threading
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Iterator


class ValidationException(Exception):
    pass


class InvalidUuid(ValidationException):
    pass


class InvalidRunAt(ValidationException):
    pass


class ServiceException(Exception):
    pass


class JobNotFound(ServiceException):
    pass


class NotMatchingOwner(ServiceException):
    pass


class InvalidStatusForCancel(ServiceException):
    pass


class JobStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    CANCELED = "CANCELED"
    FAILED = "FAILED"
    SUCCEEDED = "SUCCEEDED"


@dataclass(frozen=True)
class ExecutedJobDto:
    job_id: str
    has_succeeded: bool
    run_at: str


IS_SUCCESS_EXPECTED = "is_success_expected"


# noinspection unused-parameter
def execute_body(body):
    pass


@dataclass
class Job:
    owner_id: uuid.UUID
    body: dict[str, Any]
    run_at: datetime.datetime
    status: JobStatus = JobStatus.PENDING
    job_id: uuid.UUID = field(default_factory=uuid.uuid4)
    execute_lock: threading.Lock = field(default_factory=threading.Lock)

    def _validate_owner(self, owner_uuid: uuid.UUID) -> None:
        if owner_uuid != self.owner_id:
            raise NotMatchingOwner(self.job_id, owner_uuid)

    def cancel(self, owner_uuid):
        self._validate_owner(owner_uuid)
        with self.execute_lock:
            if self.status not in (JobStatus.PENDING, JobStatus.CANCELED):
                raise InvalidStatusForCancel(self.job_id, self.status)
            self.status = JobStatus.CANCELED

    def is_due(self) -> bool:
        return (
            self.status == JobStatus.PENDING and datetime.datetime.now() >= self.run_at
        )

    def execute(self) -> ExecutedJobDto | None:
        with self.execute_lock:
            if self.status != JobStatus.PENDING:
                return None
            self.status = JobStatus.RUNNING
            # Real execution code here
            execute_body(self.body)
            self.status = JobStatus.SUCCEEDED if self.body[IS_SUCCESS_EXPECTED] else JobStatus.FAILED
            return ExecutedJobDto(
                str(self.job_id),
                self.body[IS_SUCCESS_EXPECTED],
                str(datetime.datetime.now()),
            )


def get_uuid_from_str(uuid_str) -> uuid.UUID:
    try:
        return uuid.UUID(str(uuid_str))
    except ValueError:
        raise InvalidUuid(uuid_str)


def validate_run_at(run_at):
    if not isinstance(run_at, datetime.datetime) or run_at < datetime.datetime.now():
        raise InvalidRunAt(run_at)


class JobManager:
    def __init__(self):
        self._jobs: dict[uuid.UUID, Job] = {}
        self._jobs_lock = threading.Lock()

    def _get_job(self, job_uuid: uuid.UUID) -> Job:
        with self._jobs_lock:
            if job_uuid not in self._jobs:
                raise JobNotFound(job_uuid)
            return self._jobs[job_uuid]

    def schedule_job(
        self, owner_id: str, body: dict[str, Any], run_at: datetime.datetime
    ) -> str:
        owner_uuid = get_uuid_from_str(owner_id)
        validate_run_at(run_at)
        job = Job(owner_uuid, body, run_at)
        with self._jobs_lock:
            self._jobs[job.job_id] = job
        return str(job.job_id)

    def cancel_job(self, job_id: str, owner_id: str) -> None:
        owner_uuid = get_uuid_from_str(owner_id)
        job_uuid = get_uuid_from_str(job_id)
        job = self._get_job(job_uuid)
        job.cancel(owner_uuid)

    def fetch_job_status(self, job_id: str) -> str:
        job_uuid = get_uuid_from_str(job_id)
        job = self._get_job(job_uuid)
        return str(job.status)

    def _get_job_values(self) -> list[Job]:
        with self._jobs_lock:
            return [job for job in self._jobs.values()]

    def process_due_jobs(self) -> list[ExecutedJobDto | None]:
        due_jobs: list[Job] = [job for job in self._get_job_values() if job.is_due()]
        return [job.execute() for job in due_jobs]
