import pytest

from main import (
    LibraryService,
    AlreadyHaveACopy,
    MAX_NUMBER_OF_BOOKS_PER_MEMBER,
    MaxBorrowedBooksPerMember,
)


class TestAddBook:
    def setup_method(self):
        self.service = LibraryService()

    def test_add_book_ok(self):
        self.service.add_book("isbn_1", 10)
        assert self.service.get_available_copies("isbn_1") == 10

class TestBorrowBook:
    def setup_method(self):
        self.service = LibraryService()
        self.isbn_1 = "isbn_1"
        for i in range(MAX_NUMBER_OF_BOOKS_PER_MEMBER + 1):
            self.service.add_book(f"isbn_{i}", 10)


    def test_borrow_book_ok(self):
        self.service.borrow_book("member_1", self.isbn_1)
        borrowed_books = self.service.list_member_borrowed_books("member_1")
        assert len(borrowed_books) == 1
        assert self.isbn_1 in borrowed_books

    def test_borrow_book_twice(self):
        self.service.borrow_book("member_1", self.isbn_1)

        with pytest.raises(AlreadyHaveACopy):
            self.service.borrow_book("member_1", self.isbn_1)

    def test_member_can_only_have_n_books(self):
        for i in range(MAX_NUMBER_OF_BOOKS_PER_MEMBER):
            self.service.borrow_book("member_1", f"isbn_{i}")

        with pytest.raises(MaxBorrowedBooksPerMember):
            self.service.borrow_book("member_1", f"isbn_{MAX_NUMBER_OF_BOOKS_PER_MEMBER}")
