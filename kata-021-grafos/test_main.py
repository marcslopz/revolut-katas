import pytest

from main import *


def test_cheapest_path():
    service = ShortestConversionPath()

    service.add_conversion("EUR", "USD", 5)
    service.add_conversion("EUR", "GBP", 10)
    service.add_conversion("USD", "GBP", 3)

    weight, shortest_path = service.cheapest_path("EUR", "GBP")

    assert weight == 8
    assert shortest_path == ["EUR", "USD", "GBP"]


def test_cheapest_path_without_result():
    service = ShortestConversionPath()

    service.add_conversion("EUR", "USD", 5)
    service.add_conversion("GBP", "USD", 3)

    weight, shortest_path = service.cheapest_path("EUR", "GBP")

    assert weight == float("inf")
    assert shortest_path == []


@pytest.mark.parametrize(
    "conversion_weights, expected_weight, expected_path",
    [
        (
            (
                ("EUR", "USD", 5),
                ("EUR", "GBP", 4),
                ("USD", "GBP", -3),
            ),
            2,
            ["EUR", "USD", "GBP"],
        ),
        (
            (
                ("EUR", "USD", 5),
                ("EUR", "GBP", 10),
                ("USD", "GBP", 3),
            ),
            8,
            ["EUR", "USD", "GBP"],
        ),
    ],
)
def test_cheapest_path_with_negatives(
    conversion_weights, expected_weight, expected_path
):
    service = ShortestConversionPathWithNegative()

    for from_currency, to_currency, weight in conversion_weights:
        service.add_conversion(from_currency, to_currency, weight)

    weight, shortest_path = service.cheapest_path("EUR", "GBP")

    assert weight == expected_weight
    assert shortest_path == expected_path


def test_cheapest_path_with_negative_exception():
    service = ShortestConversionPathWithNegative()

    service.add_conversion("EUR", "USD", 1)
    service.add_conversion("GBP", "USD", -3)
    service.add_conversion("USD", "GBP", 1)

    with pytest.raises(ValueError):
        service.cheapest_path("EUR", "GBP")
