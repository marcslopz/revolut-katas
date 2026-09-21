import hashlib
from typing import Iterator

NUMBER_OF_BITS = 22055507
NUMBER_OF_HASHES = 8

def get_hashes_from_card_number(card_number) -> Iterator[int]:
    hash_1 = int(hashlib.md5(card_number.encode()).hexdigest(), 16)
    hash_2 = int(hashlib.sha1(card_number.encode()).hexdigest(), 16)
    return ((hash_1 + i * hash_2) % NUMBER_OF_BITS for i in range(NUMBER_OF_HASHES))

class CheckBlockedCardService:
    def __init__(self):
        self._hashed_bits: bytearray = bytearray((NUMBER_OF_BITS + 7) // 8)

    def add(self, card_number: str) -> None:
        hashes = get_hashes_from_card_number(card_number)
        for hash_index in hashes:
            byte_i, bit_i = divmod(hash_index, 8)
            self._hashed_bits[byte_i] |= (1 << bit_i)

    def might_be_blocked(self, card_number: str) -> bool:
        hashes = get_hashes_from_card_number(card_number)
        for hash_index in hashes:
            byte_i, bit_i = divmod(hash_index, 8)
            matches = bool(self._hashed_bits[byte_i] & (1 << bit_i))
            if not matches:
                return False
        return True


