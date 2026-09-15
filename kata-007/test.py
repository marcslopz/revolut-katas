import datetime

import pytest

from main import RoomBookingService, BookingConflict, RoomBookingCancelConflict


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
