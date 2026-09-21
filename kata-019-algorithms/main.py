import dataclasses
import enum
import heapq

class Status(enum.StrEnum):
    PENDING = enum.auto()
    RESOLVED = enum.auto()

@dataclasses.dataclass(order=True)
class Ticket:
    priority: int
    ticket_id: str
    status: Status = dataclasses.field(default=Status.PENDING, compare=False)

    def __post_init__(self):
        if not isinstance(self.priority, int):
            raise TypeError("Priority must be an integer", self.priority)
        self.priority = -self.priority
        if not isinstance(self.ticket_id, str):
            raise TypeError("ticket_id must be a string", self.ticket_id)
        if not self.ticket_id:
            raise ValueError("ticket_id cannot be empty")

    def resolve(self):
        self.status = Status.RESOLVED


class SupportTriageService:
    def __init__(self):
        self._tickets_by_id: dict[str, Ticket] = {}
        self._ordered_tickets_by_priority_desc: list[Ticket] = []

    def add_ticket(self, ticket_id: str, priority: int) -> None:
        ticket = Ticket(priority, ticket_id)
        if ticket_id in self._tickets_by_id:
            raise ValueError("Ticket already exists", ticket_id)
        self._tickets_by_id[ticket_id] = ticket
        heapq.heappush(self._ordered_tickets_by_priority_desc, ticket)

    def get_most_urgent(self) -> str | None:
        if len(self._ordered_tickets_by_priority_desc) == 0:
            return None
        while len(self._ordered_tickets_by_priority_desc) > 0:
            ticket = heapq.heappop(self._ordered_tickets_by_priority_desc)
            sot_ticket = self._tickets_by_id[ticket.ticket_id]
            if sot_ticket.status == Status.PENDING:
                return ticket.ticket_id
        return None

    def list_pending_by_priority(self) -> list[str]:
        ordered_copy = list(self._ordered_tickets_by_priority_desc)
        returned_list = []
        while len(ordered_copy) > 0:
            ticket = heapq.heappop(ordered_copy)
            sot_ticket = self._tickets_by_id[ticket.ticket_id]
            if sot_ticket.status == Status.PENDING:
                returned_list.append(ticket.ticket_id)
        return returned_list

    def resolve_ticket(self, ticket_id: str) -> None:
        if ticket_id not in self._tickets_by_id:
            raise KeyError("Ticket does not exist", ticket_id)
        ticket = self._tickets_by_id[ticket_id]
        ticket.resolve()