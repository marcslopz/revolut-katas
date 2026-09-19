import concurrent.futures
import datetime
import threading
import uuid
from unittest import mock

import pytest

from main import (
    JobManager,
    JobStatus,
    InvalidRunAt,
    InvalidUuid,
    Job,
    InvalidStatusForCancel,
    NotMatchingOwner,
    JobNotFound,
    IS_SUCCESS_EXPECTED,
)


def test_schedule_job():
    manager = JobManager()

    job_id = manager.schedule_job(
        str(uuid.uuid4()), {}, datetime.datetime.now() + datetime.timedelta(hours=1)
    )

    assert manager.fetch_job_status(job_id) == JobStatus.PENDING


def test_schedule_job_in_the_past():
    manager = JobManager()

    with pytest.raises(InvalidRunAt):
        manager.schedule_job(str(uuid.uuid4()), {}, datetime.datetime.now())


@pytest.mark.parametrize(
    "owner_id, run_at, expected_exception",
    [
        (None, datetime.datetime.now() + datetime.timedelta(hours=1), InvalidUuid),
        ("invalid", datetime.datetime.now() + datetime.timedelta(hours=1), InvalidUuid),
        (0, datetime.datetime.now() + datetime.timedelta(hours=1), InvalidUuid),
        (str(uuid.uuid4()), None, InvalidRunAt),
        (str(uuid.uuid4()), 0, InvalidRunAt),
        (str(uuid.uuid4()), "invalid", InvalidRunAt),
    ],
)
def test_schedule_job_invalid_input(owner_id, run_at, expected_exception):
    manager = JobManager()

    with pytest.raises(expected_exception):
        # noinspection bad-argument-type
        manager.schedule_job(owner_id, {}, run_at)


def test_cancel_job():
    manager = JobManager()
    owner_id = str(uuid.uuid4())
    run_at = datetime.datetime.now() + datetime.timedelta(hours=1)
    job_id = manager.schedule_job(owner_id, {}, run_at)

    manager.cancel_job(job_id, owner_id)

    assert manager.fetch_job_status(job_id) == JobStatus.CANCELED


def test_cancel_job_already_canceled():
    manager = JobManager()
    owner_id = str(uuid.uuid4())
    run_at = datetime.datetime.now() + datetime.timedelta(hours=1)
    job_id = manager.schedule_job(owner_id, {}, run_at)

    manager.cancel_job(job_id, owner_id)
    manager.cancel_job(job_id, owner_id)

    assert manager.fetch_job_status(job_id) == JobStatus.CANCELED


@pytest.mark.parametrize(
    "status",
    [
        job_status
        for job_status in JobStatus
        if job_status not in (JobStatus.PENDING, JobStatus.CANCELED)
    ],
)
def test_cancel_job_wrong_status(status):
    manager = JobManager()
    owner_uuid = uuid.uuid4()
    run_at = datetime.datetime.now() + datetime.timedelta(hours=1)
    with mock.patch.object(manager, "_get_job") as mock_get_job:
        mock_get_job.return_value = Job(owner_uuid, {}, run_at, status)
        with pytest.raises(InvalidStatusForCancel):
            manager.cancel_job(str(uuid.uuid4()), str(owner_uuid))


def test_cancel_job_wrong_owner():
    manager = JobManager()
    owner_id = str(uuid.uuid4())
    run_at = datetime.datetime.now() + datetime.timedelta(hours=1)
    job_id = manager.schedule_job(owner_id, {}, run_at)

    with pytest.raises(NotMatchingOwner):
        manager.cancel_job(job_id, str(uuid.uuid4()))


@pytest.mark.parametrize(
    "job_id, owner_id",
    [
        (None, str(uuid.uuid4())),
        ("invalid", str(uuid.uuid4())),
        (42, str(uuid.uuid4())),
        (str(uuid.uuid4()), None),
        (str(uuid.uuid4()), "invalid"),
        (str(uuid.uuid4()), 42),
    ],
)
def test_cancel_invalid_input(job_id, owner_id):
    manager = JobManager()
    with pytest.raises(InvalidUuid):
        # noinspection bad-argument-type
        manager.cancel_job(job_id, owner_id)


def test_cancel_job_not_found():
    manager = JobManager()
    with pytest.raises(JobNotFound):
        manager.cancel_job(str(uuid.uuid4()), str(uuid.uuid4()))


def test_fetch_job_status_job_not_found():
    manager = JobManager()
    with pytest.raises(JobNotFound):
        manager.fetch_job_status(str(uuid.uuid4()))


@pytest.mark.parametrize("job_id", [None, "invalid", 42])
def test_fetch_job_status_invalid_input(job_id):
    manager = JobManager()
    with pytest.raises(InvalidUuid):
        # noinspection bad-argument-type
        manager.fetch_job_status(job_id)


def test_process_due_jobs_only_takes_the_pending_ones():
    manager = JobManager()
    owner_uuid = uuid.uuid4()
    pending_job_uuid_succeeded = uuid.uuid4()
    pending_job_uuid_failed = uuid.uuid4()
    past_run_at = datetime.datetime.now() - datetime.timedelta(hours=1)
    body_succeeded = {IS_SUCCESS_EXPECTED: True}
    body_failed = {IS_SUCCESS_EXPECTED: False}
    with mock.patch.object(manager, "_get_job_values") as mock_get_job:
        mock_get_job.return_value = (
            Job(
                owner_uuid,
                body_succeeded,
                past_run_at,
                JobStatus.PENDING,
                pending_job_uuid_succeeded,
            ),
            Job(
                owner_uuid,
                body_failed,
                past_run_at,
                JobStatus.PENDING,
                pending_job_uuid_failed,
            ),
            Job(owner_uuid, body_succeeded, past_run_at, JobStatus.RUNNING),
            Job(owner_uuid, body_succeeded, past_run_at, JobStatus.CANCELED),
            Job(owner_uuid, body_succeeded, past_run_at, JobStatus.FAILED),
            Job(owner_uuid, body_succeeded, past_run_at, JobStatus.SUCCEEDED),
        )
        executed_jobs = manager.process_due_jobs()

    assert len(executed_jobs) == 2
    assert executed_jobs[0].job_id == str(pending_job_uuid_succeeded)
    assert executed_jobs[0].has_succeeded is True
    assert executed_jobs[1].job_id == str(pending_job_uuid_failed)
    assert executed_jobs[1].has_succeeded is False


def test_process_due_jobs_only_takes_the_past_ones():
    manager = JobManager()
    owner_uuid = uuid.uuid4()
    expected_to_be_run = uuid.uuid4()
    past_run_at = datetime.datetime.now() - datetime.timedelta(hours=1)
    future_run_at = datetime.datetime.now() + datetime.timedelta(hours=1)
    body_succeeded = {IS_SUCCESS_EXPECTED: True}
    with mock.patch.object(manager, "_get_job_values") as mock_get_job:
        mock_get_job.return_value = (
            Job(
                owner_uuid,
                body_succeeded,
                past_run_at,
                JobStatus.PENDING,
                expected_to_be_run,
            ),
            Job(owner_uuid, body_succeeded, future_run_at, JobStatus.PENDING),
        )
        executed_jobs = manager.process_due_jobs()

    assert len(executed_jobs) == 1
    assert executed_jobs[0].job_id == str(expected_to_be_run)
    assert executed_jobs[0].has_succeeded is True


@mock.patch("main.execute_body")
def test_process_due_jobs_concurrently(mock_execute_body):
    manager = JobManager()
    number_of_threads = 10
    barrier = threading.Barrier(number_of_threads)
    past_run_at = datetime.datetime.now() - datetime.timedelta(hours=1)
    job = Job(
        uuid.uuid4(),
        {IS_SUCCESS_EXPECTED: True},
        past_run_at,
        JobStatus.PENDING,
    )

    def worker():
        barrier.wait()
        with mock.patch.object(manager, "_get_job_values") as mock_get_job:
            mock_get_job.return_value = (job,)
            return manager.process_due_jobs()

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=number_of_threads
    ) as executor:
        futures = [executor.submit(worker) for _ in range(number_of_threads)]
        results = [future.result() for future in futures]

    assert len(results) == number_of_threads
    assert mock_execute_body.call_count == 1
