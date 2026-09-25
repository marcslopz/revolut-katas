import dataclasses
import threading

MAX_NUMBER_OF_BOOKS_PER_MEMBER = 3


class BookConflict(Exception):
    pass


class BookNotFound(Exception):
    pass


class NotEnoughCopies(Exception):
    pass


class AlreadyHaveACopy(Exception):
    pass


class UserDoesNotHaveThisBook(Exception):
    pass


class MemberNotFound(Exception):
    pass


class MaxBorrowedBooksPerMember(Exception):
    pass


@dataclasses.dataclass
class BookCapacity:
    isbn: str
    number_of_copies: int
    borrowers: set[str] = dataclasses.field(default_factory=set)

    def can_be_borrowed(self, member_id: str):
        if len(self.borrowers) == self.number_of_copies:
            raise NotEnoughCopies(self.isbn)
        if member_id in self.borrowers:
            raise AlreadyHaveACopy(self.isbn, member_id)

    def borrow(self, member_id):
        self.borrowers.add(member_id)

    def is_book_availaible(self):
        return len(self.borrowers) < self.number_of_copies

    def return_book(self, member_id):
        if member_id not in self.borrowers:
            raise UserDoesNotHaveThisBook(self.isbn, member_id)
        self.borrowers.remove(member_id)


@dataclasses.dataclass
class Book:
    isbn: str


def check_can_be_borrowed(book_capacity, borrowed_books, member_id):
    book_capacity.can_be_borrowed(member_id)
    if len(borrowed_books) == MAX_NUMBER_OF_BOOKS_PER_MEMBER:
        raise MaxBorrowedBooksPerMember(member_id)


class LibraryService:
    def __init__(self) -> None:
        self._library: dict[str, BookCapacity] = {}
        self._books_by_member: dict[str, set[str]] = {}
        self._lock = threading.Lock()

    def validate_book_is_found(self, isbn: str) -> None:
        if isbn not in self._library:
            raise BookNotFound(isbn)

    def add_book(self, isbn: str, number_of_copies: int) -> None:
        with self._lock:
            if isbn in self._library:
                raise BookConflict(isbn)
            self._library[isbn] = BookCapacity(isbn, number_of_copies)

    def is_book_available(self, isbn: str) -> bool:
        with self._lock:
            self.validate_book_is_found(isbn)
            book_capacity = self._library[isbn]
            return book_capacity.is_book_availaible()

    def borrow_book(self, member_id: str, isbn: str) -> None:
        with self._lock:
            self.validate_book_is_found(isbn)
            book_capacity = self._library[isbn]
            if member_id not in self._books_by_member:
                self._books_by_member[member_id] = set()
            check_can_be_borrowed(
                book_capacity, self._books_by_member[member_id], member_id
            )
            book_capacity.borrow(member_id)
            self._books_by_member[member_id].add(isbn)

    def return_book(self, member_id: str, isbn: str) -> None:
        with self._lock:
            self.validate_book_is_found(isbn)
            book_capacity = self._library[isbn]
            book_capacity.return_book(member_id)

    def add_copies_to_book(self, isbn: str, copies: int) -> None:
        with self._lock:
            self.validate_book_is_found(isbn)

            self._library[isbn].number_of_copies += copies

    def get_available_copies(self, isbn: str) -> int:
        with self._lock:
            self.validate_book_is_found(isbn)

            return self._library[isbn].number_of_copies

    def list_book_borrowers(self, isbn: str) -> set[str]:
        with self._lock:
            self.validate_book_is_found(isbn)
            return set(self._library[isbn].borrowers)

    def list_member_borrowed_books(self, member_id: str) -> set[str]:
        with self._lock:
            if member_id not in self._books_by_member:
                raise MemberNotFound(member_id)
            return set(self._books_by_member[member_id])
