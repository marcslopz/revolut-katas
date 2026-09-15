import concurrent.futures
import datetime
import threading

import pytest

from main import RoomBookingService, BookingConflict, RoomBookingCancelConflict, RoomBookingNotFound


def test_create_booking_first_time_ok():
    service = RoomBookingService()
    start_time = datetime.datetime.now()
    end_time = start_time + datetime.timedelta(hours=1)

    service.create_booking("room_1", "user_1", start_time, end_time)

    bookings_list = service.list_bookings_by_room_id("room_1")
    assert len(bookings_list) == 1
    assert bookings_list[0].start == start_time
    assert bookings_list[0].end == end_time


def test_create_booking_not_conflicting_booking_ok():
    service = RoomBookingService()
    start_time_1 = datetime.datetime.now()
    end_time_1 = start_time_1 + datetime.timedelta(hours=1)
    service.create_booking("room_1", "user_1", start_time_1, end_time_1)
    start_time_2 = end_time_1
    end_time_2 = start_time_2 + datetime.timedelta(hours=1)

    service.create_booking("room_1", "user_1", start_time_2, end_time_2)

    bookings_list = service.list_bookings_by_room_id("room_1")
    assert len(bookings_list) == 2


def test_create_booking_conflicting_booking():
    service = RoomBookingService()
    start_time_1 = datetime.datetime.now()
    end_time_1 = start_time_1 + datetime.timedelta(hours=1)
    service.create_booking("room_1", "user_1", start_time_1, end_time_1)
    start_time_2 = start_time_1 + datetime.timedelta(minutes=15)
    end_time_2 = start_time_2 + datetime.timedelta(hours=1)

    with pytest.raises(BookingConflict):
        service.create_booking("room_1", "user_1", start_time_2, end_time_2)

    bookings_list = service.list_bookings_by_room_id("room_1")
    assert len(bookings_list) == 1
    assert bookings_list[0].start == start_time_1
    assert bookings_list[0].end == end_time_1


def test_cancel_booking():
    service = RoomBookingService()
    booking_id = service.create_booking(
        "room_1", "user_1", datetime.datetime.now(), datetime.datetime.now()
    )

    service.cancel_booking(booking_id, "room_1", "user_1")


def test_cancel_booking_with_different_user():
    service = RoomBookingService()
    booking_id = service.create_booking(
        "room_1", "user_1", datetime.datetime.now(), datetime.datetime.now()
    )

    with pytest.raises(RoomBookingCancelConflict):
        service.cancel_booking(booking_id, "room_1", "user_2")

    booking_list_by_room = service.list_bookings_by_room_id("room_1")
    booking_list_by_user = service.list_bookings_by_user_id("user_1")
    assert len(booking_list_by_room) == 1
    assert len(booking_list_by_user) == 1


def test_cancel_booking_with_different_room():
    service = RoomBookingService()
    booking_id = service.create_booking(
        "room_1", "user_1", datetime.datetime.now(), datetime.datetime.now()
    )

    with pytest.raises(RoomBookingCancelConflict):
        service.cancel_booking(booking_id, "room_2", "user_1")


def test_create_concurrent_bookings():
    service = RoomBookingService()
    start_1 = datetime.datetime.now()
    end_1 = start_1 + datetime.timedelta(hours=1)
    start_2 = end_1
    end_2 = start_2 + datetime.timedelta(hours=1)
    conflicting_start = start_1
    conflicting_end = end_1
    service.create_booking("room_1", "user_1", start_1, end_1)
    service.create_booking("room_2", "user_1", start_1, end_1)
    number_of_same_room_non_conflicting_threads = 4
    number_of_same_room_conflicting_threads = 4
    number_of_different_room_non_conflicting_threads = 4
    total_num_of_threads = (
        number_of_same_room_non_conflicting_threads
        + number_of_same_room_conflicting_threads
        + number_of_different_room_non_conflicting_threads
    )
    barrier = threading.Barrier(total_num_of_threads)

    def worker(room_id, user_id, start, end):
        barrier.wait()
        try:
            service.create_booking(room_id, user_id, start, end)
            return True
        except BookingConflict:
            return False

    moving_start = start_1 + datetime.timedelta(hours=1)
    moving_end = moving_start + datetime.timedelta(hours=1)
    with concurrent.futures.ThreadPoolExecutor(
        max_workers=total_num_of_threads
    ) as executor:
        futures_same_room_non_conflicting_threads = [
            executor.submit(
                worker,
                "room_1",
                "user_1",
                moving_start + i * datetime.timedelta(hours=1),
                moving_end + i * datetime.timedelta(hours=1),
            )
            for i in range(number_of_same_room_non_conflicting_threads)
        ]
        futures_same_room_conflicting_threads = [
            executor.submit(worker, "room_1", "user_1", start_1, end_1)
            for _ in range(number_of_same_room_conflicting_threads)
        ]
        futures_different_room_non_conflicting_threads = [
            executor.submit(
                worker,
                "room_2",
                "user_1",
                moving_start + i * datetime.timedelta(hours=1),
                moving_end + i * datetime.timedelta(hours=1),
            )
            for i in range(number_of_different_room_non_conflicting_threads)
        ]
        results_same_room_non_conflicting_threads = [
            future.result() for future in futures_same_room_non_conflicting_threads
        ]
        results_same_room_conflicting_threads = [
            future.result() for future in futures_same_room_conflicting_threads
        ]
        results_different_room_non_conflicting_threads = [
            future.result() for future in futures_different_room_non_conflicting_threads
        ]

    assert (
        len(results_same_room_non_conflicting_threads)
        == number_of_same_room_non_conflicting_threads
    )
    assert (
        len(results_same_room_conflicting_threads)
        == number_of_same_room_conflicting_threads
    )
    assert (
        len(results_different_room_non_conflicting_threads)
        == number_of_different_room_non_conflicting_threads
    )
    assert (
        results_same_room_non_conflicting_threads.count(True)
        == number_of_same_room_non_conflicting_threads
    )
    assert results_same_room_non_conflicting_threads.count(False) == 0
    assert results_same_room_conflicting_threads.count(True) == 0
    assert (
        results_same_room_conflicting_threads.count(False)
        == number_of_same_room_conflicting_threads
    )
    assert (
        results_different_room_non_conflicting_threads.count(True)
        == number_of_different_room_non_conflicting_threads
    )
    assert results_different_room_non_conflicting_threads.count(False) == 0


def test_concurrent_cancel_bookings():
    service = RoomBookingService()
    bookin_id = service.create_booking(
        "room_1",
        "user_1",
        datetime.datetime.now(),
        datetime.datetime.now() + datetime.timedelta(hours=1),
    )
    barrier = threading.Barrier(2)

    def worker():
        barrier.wait()
        try:
            service.cancel_booking(bookin_id, "room_1", "user_1")
            return True
        except RoomBookingNotFound:
            return False

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(worker) for _ in range(2)]
        results = [future.result() for future in futures]

    assert len(results) == 2
    assert results.count(True) == 1
    assert results.count(False) == 1
