import copy
import dataclasses
import enum
import heapq
import threading
import uuid


class ValidationException(Exception):
    pass


class InvalidCapacity(ValidationException):
    pass


class InvalidUuid(ValidationException):
    pass


class InvalidEmail(ValidationException):
    pass


class ServiceException(Exception):
    pass


class DuplicateEmail(ServiceException):
    pass


class AgentNotFound(ServiceException):
    pass


class TicketNotFound(ServiceException):
    pass


class TicketInvalidStatusTransition(ServiceException):
    pass


class NotEnoughCapacity(ServiceException):
    pass


class AssigneeMismatch(ServiceException):
    pass


@dataclasses.dataclass
class Agent:
    capacity: int
    agent_email: str
    assigned_tickets: int = 0
    agent_id: uuid.UUID = dataclasses.field(default_factory=uuid.uuid4)

    def __post_init__(self):
        if not isinstance(self.capacity, int) or self.capacity <= 0:
            raise InvalidCapacity(self.capacity)
        if not isinstance(self.agent_email, str) or not self.agent_email:
            raise InvalidEmail(self.agent_email)

    def assign_ticket(self):
        self.assigned_tickets += 1

    def is_at_full_capacity(self):
        return self.assigned_tickets == self.capacity

    def resolve_ticket(self):
        self.assigned_tickets -= 1


class TicketStatus(enum.StrEnum):
    UNASSIGNED = enum.auto()
    ASSIGNED = enum.auto()
    RESOLVED = enum.auto()


class TicketPriority(enum.IntEnum):
    HIGH = 1
    MEDIUM = 2
    LOW = 3


@dataclasses.dataclass(frozen=True, order=True)
class OrderedTicket:
    priority: TicketPriority
    status: TicketStatus
    ticket_id: uuid.UUID


@dataclasses.dataclass
class Ticket:
    summary: str
    description: str
    priority: TicketPriority
    ticket_id: uuid.UUID = dataclasses.field(default_factory=uuid.uuid4)
    status: TicketStatus = TicketStatus.UNASSIGNED
    assignee_id: uuid.UUID | None = None

    def assign_agent(self, agent_id: uuid.UUID) -> None:
        self.assignee_id = agent_id
        self.status = TicketStatus.ASSIGNED

    def resolve(self, agent_id):
        if self.status != TicketStatus.ASSIGNED:
            raise TicketInvalidStatusTransition(self.status)
        if self.assignee_id != agent_id:
            raise AssigneeMismatch(self.assignee_id, agent_id)
        self.status = TicketStatus.RESOLVED

    def to_ordered_ticket(self):
        return OrderedTicket(self.priority, self.status, self.ticket_id)


def assign_ticket_to_agent(ticket: Ticket, agent: Agent) -> None:
    if agent.is_at_full_capacity():
        raise NotEnoughCapacity()
    if ticket.status != TicketStatus.UNASSIGNED:
        raise TicketInvalidStatusTransition(ticket.status)
    agent.assign_ticket()
    ticket.assign_agent(agent.agent_id)


class SupportService:
    def __init__(self) -> None:
        self._agents_by_email: dict[str, uuid.UUID] = {}
        self._agents_by_uuid: dict[uuid.UUID, Agent] = {}
        self._tickets_by_uuid: dict[uuid.UUID, Ticket] = {}
        self._tickets_ordered_by_priority: list[OrderedTicket] = []
        self._lock = threading.Lock()

    def register_agent(self, agent_email: str, capacity: int) -> uuid.UUID:
        with self._lock:
            if agent_email in self._agents_by_email:
                raise DuplicateEmail(agent_email)
            agent = Agent(capacity, agent_email)
            self._agents_by_email[agent_email] = agent.agent_id
            self._agents_by_uuid[agent.agent_id] = agent
            return agent.agent_id

    def create_ticket(
        self,
        summary: str,
        description: str,
        priority: TicketPriority = TicketPriority.HIGH,
    ) -> uuid.UUID:
        ticket = Ticket(summary, description, priority)
        with self._lock:
            self._tickets_by_uuid[ticket.ticket_id] = ticket
            heapq.heappush(self._tickets_ordered_by_priority, ticket.to_ordered_ticket())
            return ticket.ticket_id

    def assign_ticket(self, ticket_id: uuid.UUID, agent_id: uuid.UUID) -> None:
        with self._lock:
            if agent_id not in self._agents_by_uuid:
                raise AgentNotFound(agent_id)
            if ticket_id not in self._tickets_by_uuid:
                raise TicketNotFound(ticket_id)
            ticket = self._tickets_by_uuid[ticket_id]
            agent = self._agents_by_uuid[agent_id]
            assign_ticket_to_agent(ticket, agent)

    def resolve_ticket(self, ticket_id: uuid.UUID, agent_id: uuid.UUID) -> None:
        with self._lock:
            if agent_id not in self._agents_by_uuid:
                raise AgentNotFound(agent_id)
            if ticket_id not in self._tickets_by_uuid:
                raise TicketNotFound(ticket_id)
            ticket = self._tickets_by_uuid[ticket_id]
            ticket.resolve(agent_id)
            agent = self._agents_by_uuid[agent_id]
            agent.resolve_ticket()

    def get_agent_by_id(self, agent_id: uuid.UUID) -> Agent:
        with self._lock:
            if agent_id not in self._agents_by_uuid:
                raise AgentNotFound(agent_id)
            return copy.copy(self._agents_by_uuid[agent_id])

    def get_ticket_by_id(self, ticket_id: uuid.UUID) -> Ticket:
        with self._lock:
            if ticket_id not in self._tickets_by_uuid:
                raise TicketNotFound(ticket_id)
            return copy.copy(self._tickets_by_uuid[ticket_id])

    def assign_next_ticket(self, agent_id: uuid.UUID) -> Ticket:
        with self._lock:
            if agent_id not in self._agents_by_uuid:
                raise AgentNotFound(agent_id)
            agent = self._agents_by_uuid[agent_id]
            while self._tickets_ordered_by_priority:
                ordered_ticket = heapq.heappop(self._tickets_ordered_by_priority)
                ticket = self._tickets_by_uuid[ordered_ticket.ticket_id]
                if ticket.status != TicketStatus.UNASSIGNED:
                    continue
                assign_ticket_to_agent(ticket, agent)
                return copy.copy(ticket)

        raise TicketNotFound

