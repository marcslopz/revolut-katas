import concurrent.futures
import datetime
import threading
import uuid

import pytest

from main import (
    BookingService,
    BookingOverlap,
    RoomNotFound,
    UserNotFound,
    BookingNotFound,
    CancelConflict,
    InvalidBookingId,
)


def test_create_booking():
    service = BookingService()

    booking_id = service.create_booking(
        "key_1",
        "room_1",
        "user_1",
        datetime.datetime.now(),
        datetime.datetime.now() + datetime.timedelta(hours=1),
    )

    room_bookings = service.list_room_bookings("room_1")
    user_bookings = service.list_user_bookings("user_1")
    assert len(room_bookings) == 1
    assert room_bookings[0].booking_id == booking_id
    assert len(user_bookings) == 1
    assert user_bookings[0].booking_id == booking_id


def test_create_bookings_with_overlap_but_different_room():
    service = BookingService()

    start_time = datetime.datetime.now()
    end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
    booking_id_1 = service.create_booking(
        "key_1",
        "room_1",
        "user_1",
        start_time,
        end_time,
    )

    booking_id_2 = service.create_booking("key_2", "room_2", "user_1", start_time, end_time)

    room_1_bookings = service.list_room_bookings("room_1")
    room_2_bookings = service.list_room_bookings("room_2")
    user_bookings = service.list_user_bookings("user_1")
    assert len(room_1_bookings) == 1
    assert room_1_bookings[0].booking_id == booking_id_1
    assert len(room_2_bookings) == 1
    assert room_2_bookings[0].booking_id == booking_id_2
    assert len(user_bookings) == 2
    user_booking_ids = [booking.booking_id for booking in user_bookings]
    assert booking_id_1 in user_booking_ids
    assert booking_id_2 in user_booking_ids


def test_create_bookings_with_overlap_same_room():
    service = BookingService()

    start_time = datetime.datetime.now()
    end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
    service.create_booking(
        "key_1",
        "room_1",
        "user_1",
        start_time,
        end_time,
    )

    with pytest.raises(BookingOverlap):
        service.create_booking("key_2", "room_1", "user_1", start_time, end_time)


def test_create_bookings_without_overlap_same_room():
    service = BookingService()

    start_time = datetime.datetime.now()
    end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
    booking_id_1 = service.create_booking(
        "key_1",
        "room_1",
        "user_1",
        start_time,
        end_time,
    )
    start_time_2 = end_time
    end_time_2 = start_time + datetime.timedelta(hours=1)
    booking_id_2 = service.create_booking("key_2", "room_1", "user_1", start_time_2, end_time_2)

    room_1_bookings = service.list_room_bookings("room_1")
    user_bookings = service.list_user_bookings("user_1")
    assert len(room_1_bookings) == 2
    room_booking_ids = [booking.booking_id for booking in room_1_bookings]
    assert booking_id_1 in room_booking_ids
    assert booking_id_2 in room_booking_ids
    assert len(user_bookings) == 2
    user_booking_ids = [booking.booking_id for booking in user_bookings]
    assert booking_id_1 in user_booking_ids
    assert booking_id_2 in user_booking_ids


def test_cancel_booking():
    service = BookingService()
    start_time = datetime.datetime.now()
    end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
    booking_id = service.create_booking("key_1", "room_1", "user_1", start_time, end_time)

    service.cancel_booking(booking_id, "room_1", "user_1")

    bookings = service.list_room_bookings("room_1")
    assert len(bookings) == 0


@pytest.mark.parametrize(
    "booking_id_is_right, room_id_is_right, user_id_is_right, expected_exception",
    [
        (False, True, True, BookingNotFound),
        (True, False, True, RoomNotFound),
        (True, True, False, UserNotFound),
    ],
)
def test_cancel_booking_unexisting_id(
    booking_id_is_right, room_id_is_right, user_id_is_right, expected_exception
):
    service = BookingService()
    start_time = datetime.datetime.now()
    end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
    booking_id = service.create_booking("key_1", "room_1", "user_1", start_time, end_time)
    used_booking_id = booking_id if booking_id_is_right else str(uuid.uuid4())
    room_id = "room_1" if room_id_is_right else "room_2"
    user_id = "user_1" if user_id_is_right else "user_2"

    with pytest.raises(expected_exception):
        service.cancel_booking(used_booking_id, room_id, user_id)

    bookings = service.list_room_bookings("room_1")
    assert len(bookings) == 1
    assert bookings[0].booking_id == booking_id


def test_cancel_booking_wrong_user_id():
    service = BookingService()
    start_time = datetime.datetime.now()
    end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
    start_time_2 = end_time
    end_time_2 = start_time_2 + datetime.timedelta(hours=1)
    booking_id_1 = service.create_booking("key_1", "room_1", "user_1", start_time, end_time)
    booking_id_2 = service.create_booking("key_2", "room_1", "user_2", start_time_2, end_time_2)

    with pytest.raises(CancelConflict):
        service.cancel_booking(booking_id_1, "room_1", "user_2")

    bookings = service.list_room_bookings("room_1")
    assert len(bookings) == 2
    booking_ids = [booking.booking_id for booking in bookings]
    assert booking_id_1 in booking_ids
    assert booking_id_2 in booking_ids


def test_cancel_booking_wrong_room_id():
    service = BookingService()
    start_time = datetime.datetime.now()
    end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
    booking_id_1 = service.create_booking("key_1", "room_1", "user_1", start_time, end_time)
    service.create_booking("key_2", "room_2", "user_1", start_time, end_time)

    with pytest.raises(CancelConflict):
        service.cancel_booking(booking_id_1, "room_2", "user_1")

    bookings = service.list_room_bookings("room_1")
    assert len(bookings) == 1
    assert bookings[0].booking_id == booking_id_1


def test_cancel_invalid_booking_id():
    service = BookingService()

    with pytest.raises(InvalidBookingId):
        service.cancel_booking("invalid_booking_id", "room_1", "user_1")


def test_concurrent_overlapping_creations():
    service = BookingService()
    start_time = datetime.datetime.now()
    end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
    number_of_threads = 10
    barrier = threading.Barrier(number_of_threads)

    def worker():
        barrier.wait()
        try:
            service.create_booking(str(uuid.uuid4()), "room_1", "user_1", start_time, end_time)
            return True
        except BookingOverlap:
            return False

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=number_of_threads
    ) as executor:
        futures = [executor.submit(worker) for _ in range(number_of_threads)]
        results = [
            future.result() for future in concurrent.futures.as_completed(futures)
        ]

    assert len(results) == number_of_threads
    assert results.count(True) == 1
    assert results.count(False) == number_of_threads - 1


def test_concurrent_not_overlapping_creations():
    service = BookingService()
    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(hours=1)
    number_of_threads = 10
    barrier = threading.Barrier(number_of_threads)

    def worker(used_start, used_end):
        barrier.wait()
        try:
            service.create_booking(str(uuid.uuid4()), "room_1", "user_1", used_start, used_end)
            return True
        except BookingOverlap:
            return False

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=number_of_threads
    ) as executor:
        futures = [
            executor.submit(
                worker,
                start_time + i * datetime.timedelta(hours=1),
                end_time + i * datetime.timedelta(hours=1),
            )
            for i in range(number_of_threads)
        ]
        results = [
            future.result() for future in concurrent.futures.as_completed(futures)
        ]

    assert len(results) == number_of_threads
    assert results.count(True) == number_of_threads
    assert results.count(False) == 0

def test_concurrent_cancels():
    service = BookingService()
    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(hours=1)
    booking_id = service.create_booking("key_1", "room_1", "user_1", start_time, end_time)
    number_of_threads = 10
    barrier = threading.Barrier(number_of_threads)

    def worker():
        barrier.wait()
        try:
            service.cancel_booking(booking_id, "room_1", "user_1")
            return True
        except BookingNotFound:
            return False

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=number_of_threads
    ) as executor:
        futures = [
            executor.submit(
                worker,
            )
            for _ in range(number_of_threads)
        ]
        results = [
            future.result() for future in concurrent.futures.as_completed(futures)
        ]

    assert len(results) == number_of_threads
    assert results.count(True) == 1
    assert results.count(False) == number_of_threads - 1
    room_bookings = service.list_room_bookings("room_1")
    user_bookings = service.list_user_bookings("user_1")
    assert len(room_bookings) == 0
    assert len(user_bookings) == 0

def test_concurrent_idempotent_creations():
    service = BookingService()
    start_time = datetime.datetime.now()
    end_time = datetime.datetime.now() + datetime.timedelta(hours=1)
    number_of_threads = 10
    barrier = threading.Barrier(number_of_threads)

    def worker():
        barrier.wait()
        return service.create_booking("key_1", "room_1", "user_1", start_time, end_time)

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=number_of_threads
    ) as executor:
        futures = [executor.submit(worker) for _ in range(number_of_threads)]
        results = [
            future.result() for future in concurrent.futures.as_completed(futures)
        ]

    assert len(results) == number_of_threads
    assert results.count(results[0]) == number_of_threads
    room_bookings = service.list_room_bookings("room_1")
    user_bookings = service.list_user_bookings("user_1")
    assert len(room_bookings) == 1
    assert room_bookings[0].booking_id == results[0]
    assert len(user_bookings) == 1
    assert user_bookings[0].booking_id == results[0]
