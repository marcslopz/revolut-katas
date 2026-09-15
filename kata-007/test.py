import datetime

import pytest

from main import RoomBookingService, BookingConflict


def test_create_booking_first_time_ok():
    service = RoomBookingService()
    start_time = (datetime.datetime.now())
    end_time = start_time + datetime.timedelta(hours=1)

    service.create_booking("room_1", start_time, end_time)

    bookings_list = service.list_bookings("room_1")
    assert len(bookings_list) == 1
    assert bookings_list[0][0] == start_time
    assert bookings_list[0][1] == end_time

def test_create_booking_not_conflicting_booking_ok():
    service = RoomBookingService()
    start_time_1 = (datetime.datetime.now())
    end_time_1 = start_time_1 + datetime.timedelta(hours=1)
    service.create_booking("room_1", start_time_1, end_time_1)
    start_time_2 = end_time_1
    end_time_2 = start_time_2 + datetime.timedelta(hours=1)

    service.create_booking("room_1", start_time_2, end_time_2)

    bookings_list = service.list_bookings("room_1")
    assert len(bookings_list) == 2
    assert (start_time_1, end_time_1) in bookings_list
    assert (start_time_2, end_time_2) in bookings_list

def test_create_booking_conflicting_booking():
    service = RoomBookingService()
    start_time_1 = (datetime.datetime.now())
    end_time_1 = start_time_1 + datetime.timedelta(hours=1)
    service.create_booking("room_1", start_time_1, end_time_1)
    start_time_2 = start_time_1 + datetime.timedelta(minutes=15)
    end_time_2 = start_time_2 + datetime.timedelta(hours=1)

    with pytest.raises(BookingConflict):
        service.create_booking("room_1", start_time_2, end_time_2)

    bookings_list = service.list_bookings("room_1")
    assert len(bookings_list) == 1
    assert bookings_list[0][0] == start_time_1
    assert bookings_list[0][1] == end_time_1
