import pytest

from main import (
    AlreadyExistingSku,
    InventoryService,
    InvalidQuantity,
    InvalidSku,
    InvalidStock,
    NotEnoughStock,
    SkuNotFound,
)


class TestAddSku:
    def setup_method(self) -> None:
        self.service = InventoryService()
        self.sku = "product_1"

    def test_add_sku_creates_product(self) -> None:
        self.service.add_sku(self.sku, 1)
        stock = self.service.get_stock(self.sku)
        assert stock == 1

    def test_add_sku_raises_when_duplicate(self) -> None:
        self.service.add_sku(self.sku, 1)
        with pytest.raises(AlreadyExistingSku):
            self.service.add_sku(self.sku, 1)

    @pytest.mark.parametrize("stock", [-1, None, "invalid"])
    def test_add_sku_raises_when_invalid_stock(self, stock) -> None:
        with pytest.raises(InvalidStock):
            # noinspection bad-argument-type
            self.service.add_sku(self.sku, stock)

    @pytest.mark.parametrize("sku", ["", None, 123])
    def test_add_sku_raises_when_invalid_sku(self, sku) -> None:
        with pytest.raises(InvalidSku):
            # noinspection bad-argument-type
            self.service.add_sku(sku, 1)


class TestDeductStock:
    def setup_method(self) -> None:
        self.service = InventoryService()
        self.sku = "product_1"
        self.service.add_sku(self.sku, 1)

    def test_deduct_stock_reduces_quantity(self) -> None:
        self.service.deduct_stock(self.sku, 1)
        stock = self.service.get_stock(self.sku)
        assert stock == 0

    def test_deduct_stock_raises_when_insufficient(self) -> None:
        with pytest.raises(NotEnoughStock):
            self.service.deduct_stock(self.sku, 2)
        stock = self.service.get_stock(self.sku)
        assert stock == 1

    def test_deduct_sku_not_found(self) -> None:
        with pytest.raises(SkuNotFound):
            self.service.deduct_stock("not found", 2)

    @pytest.mark.parametrize("quantity", [0, -1, None, "invalid"])
    def test_deduct_stock_raises_when_invalid_quantity(self, quantity) -> None:
        with pytest.raises(InvalidQuantity):
            # noinspection bad-argument-type
            self.service.deduct_stock(self.sku, quantity)


class TestGetStock:
    def setup_method(self) -> None:
        self.service = InventoryService()
        self.sku_1 = "product_1"
        self.sku_2 = "product_2"
        self.service.add_sku(self.sku_1, 1)
        self.service.add_sku(self.sku_2, 2)

    def test_get_stock_returns_current_quantity(self) -> None:
        stock_1 = self.service.get_stock(self.sku_1)
        stock_2 = self.service.get_stock(self.sku_2)
        assert stock_1 == 1
        assert stock_2 == 2

    def test_get_stock_raises_when_sku_unknown(self) -> None:
        with pytest.raises(SkuNotFound):
            self.service.get_stock("not found")

    @pytest.mark.parametrize("sku", ["", None, 123])
    def test_get_stock_raises_when_invalid_sku(self, sku) -> None:
        with pytest.raises(InvalidSku):
            # noinspection bad-argument-type
            self.service.get_stock(sku)
