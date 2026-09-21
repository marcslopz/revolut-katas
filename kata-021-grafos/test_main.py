from main import *


def test_cheapest_path():
    service = ShortestConventionPath()

    service.add_conversion("EUR", "USD", 5)
    service.add_conversion("EUR", "GBP", 10)
    service.add_conversion("USD", "GBP", 3)

    weight, shortest_path = service.cheapest_path("EUR", "GBP")

    assert weight == 8
    assert shortest_path == ["EUR", "USD", "GBP"]


def test_cheapest_path_without_result():
    service = ShortestConventionPath()

    service.add_conversion("EUR", "USD", 5)
    service.add_conversion("GBP", "USD", 3)

    weight, shortest_path = service.cheapest_path("EUR", "GBP")

    assert weight == float("inf")
    assert shortest_path == []
