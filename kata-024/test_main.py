import concurrent.futures
import threading
import uuid

import pytest

from main import (
    SupportService,
    DuplicateEmail,
    InvalidEmail,
    InvalidCapacity,
    TicketStatus,
    TicketInvalidStatusTransition,
    TicketNotFound,
    AgentNotFound,
    NotEnoughCapacity,
    AssigneeMismatch,
    TicketPriority,
)


class TestRegisterAgent:
    def setup_method(self):
        self.service = SupportService()

    def test_register_agent_ok(self):
        agent_id = self.service.register_agent("valid_email@domain.com", 10)

        agent = self.service.get_agent_by_id(agent_id)
        assert agent.agent_email == "valid_email@domain.com"
        assert agent.capacity == 10

    def test_register_duplicated_email(self):
        agent_id = self.service.register_agent("valid_email@domain.com", 10)

        with pytest.raises(DuplicateEmail):
            self.service.register_agent("valid_email@domain.com", 10)

    @pytest.mark.parametrize(
        "agent_email,capacity, expected_exception",
        [
            ("", 10, InvalidEmail),
            (2, 10, InvalidEmail),
            (None, 10, InvalidEmail),
            ("valid_email@domain.com", -1, InvalidCapacity),
            ("valid_email@domain.com", 0, InvalidCapacity),
            ("valid_email@domain.com", None, InvalidCapacity),
            ("valid_email@domain.com", "invalid", InvalidCapacity),
        ],
    )
    def test_invalid_input(self, agent_email, capacity, expected_exception):
        with pytest.raises(expected_exception):
            # noinspection bad-argument-type
            self.service.register_agent(agent_email, capacity)


class TestCreateTicket:
    def setup_method(self):
        self.service = SupportService()

    def test_create_ticket_ok(self):
        ticket_id = self.service.create_ticket("summary", "description")
        ticket = self.service.get_ticket_by_id(ticket_id)
        assert ticket.summary == "summary"
        assert ticket.description == "description"


class TestAssignTicket:
    def setup_method(self):
        self.service = SupportService()
        self.agent_id = self.service.register_agent("valid_email", 1)
        self.agent_id_2 = self.service.register_agent("valid_email_2", 1)
        self.ticket_id = self.service.create_ticket("summary", "description")
        self.ticket_id_2 = self.service.create_ticket("summary", "description")

    def test_assign_ticket_ok(self):
        self.service.assign_ticket(self.ticket_id, self.agent_id)
        ticket = self.service.get_ticket_by_id(self.ticket_id)
        assert ticket.status == TicketStatus.ASSIGNED
        assert ticket.assignee_id == self.agent_id

    def test_already_assigned_ticket(self):
        self.service.assign_ticket(self.ticket_id, self.agent_id)
        with pytest.raises(TicketInvalidStatusTransition):
            self.service.assign_ticket(self.ticket_id, self.agent_id_2)

    def test_ticket_not_found(self):
        with pytest.raises(TicketNotFound):
            self.service.assign_ticket(uuid.uuid4(), self.agent_id)

    def test_agent_not_found(self):
        with pytest.raises(AgentNotFound):
            self.service.assign_ticket(self.ticket_id, uuid.uuid4())

    def test_not_enough_capacity(self):
        self.service.assign_ticket(self.ticket_id, self.agent_id)
        with pytest.raises(NotEnoughCapacity):
            self.service.assign_ticket(self.ticket_id_2, self.agent_id)


class TestResolveTicket:
    def setup_method(self):
        self.service = SupportService()
        self.assigned_agent_id = self.service.register_agent("valid_email", 10)
        self.other_agent_id = self.service.register_agent("valid_email_2", 10)
        self.assigned_ticket_id = self.service.create_ticket("summary", "description")
        self.unassigned_ticket_id = self.service.create_ticket("summary", "description")
        self.service.assign_ticket(self.assigned_ticket_id, self.assigned_agent_id)

    def test_resolve_ticket_ok(self):
        self.service.resolve_ticket(self.assigned_ticket_id, self.assigned_agent_id)

        ticket = self.service.get_ticket_by_id(self.assigned_ticket_id)
        assert ticket.status == TicketStatus.RESOLVED
        assert ticket.assignee_id == self.assigned_agent_id

        agent = self.service.get_agent_by_id(self.assigned_agent_id)
        assert agent.assigned_tickets == 0

    def test_resolve_ticket_not_found(self):
        with pytest.raises(TicketNotFound):
            self.service.resolve_ticket(uuid.uuid4(), self.assigned_agent_id)

    def test_resolve_agent_not_found(self):
        with pytest.raises(AgentNotFound):
            self.service.resolve_ticket(self.assigned_ticket_id, uuid.uuid4())

    def test_try_resolve_with_other_agent(self):
        with pytest.raises(AssigneeMismatch):
            self.service.resolve_ticket(self.assigned_ticket_id, self.other_agent_id)

    def test_try_resolve_with_unassigned(self):
        with pytest.raises(TicketInvalidStatusTransition):
            self.service.resolve_ticket(self.unassigned_ticket_id, self.other_agent_id)

    def test_try_resolve_already_resolved(self):
        self.service.resolve_ticket(self.assigned_ticket_id, self.assigned_agent_id)
        with pytest.raises(TicketInvalidStatusTransition):
            self.service.resolve_ticket(self.assigned_ticket_id, self.assigned_agent_id)


class TestAssignNextTicket:
    def setup_method(self):
        self.service = SupportService()
        self.agent_id = self.service.register_agent("valid_email", 1)
        self._low_ticket_id = self.service.create_ticket(
            "low", "description", TicketPriority.LOW
        )
        self._medium_ticket_id = self.service.create_ticket(
            "medium", "description", TicketPriority.MEDIUM
        )
        self._high_ticket_id = self.service.create_ticket(
            "high", "description", TicketPriority.HIGH
        )

    def test_assign_next_ticket_ok(self):
        ticket_1 = self.service.assign_next_ticket(self.agent_id)
        assert ticket_1.status == TicketStatus.ASSIGNED
        assert ticket_1.assignee_id == self.agent_id
        assert ticket_1.ticket_id == self._high_ticket_id

        self.service.resolve_ticket(ticket_1.ticket_id, self.agent_id)

        ticket_2 = self.service.assign_next_ticket(self.agent_id)
        assert ticket_2.status == TicketStatus.ASSIGNED
        assert ticket_2.assignee_id == self.agent_id
        assert ticket_2.ticket_id == self._medium_ticket_id

        self.service.resolve_ticket(ticket_2.ticket_id, self.agent_id)

        ticket_3 = self.service.assign_next_ticket(self.agent_id)
        assert ticket_3.status == TicketStatus.ASSIGNED
        assert ticket_3.assignee_id == self.agent_id
        assert ticket_3.ticket_id == self._low_ticket_id

        with pytest.raises(TicketNotFound):
            self.service.assign_next_ticket(self.agent_id)


class TestConcurrency:
    def setup_method(self):
        self.service = SupportService()
        self.agent_capacity = 2
        self.agent_id = self.service.register_agent("valid_email", self.agent_capacity)
        self.number_of_threads = 10
        self.ticket_ids = [
            self.service.create_ticket("summary", "description")
            for _ in range(self.number_of_threads)
        ]

    def test_concurrent_agent_assignations(self):
        barrier = threading.Barrier(self.number_of_threads)

        def worker(ticket_index):
            barrier.wait()
            try:
                self.service.assign_ticket(self.ticket_ids[ticket_index], self.agent_id)
                return True
            except NotEnoughCapacity:
                return False

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=self.number_of_threads
        ) as executor:
            futures = [
                executor.submit(worker, i) for i in range(self.number_of_threads)
            ]
            results = [future.result() for future in futures]

        assert len(results) == self.number_of_threads
        assert results.count(True) == self.agent_capacity
        assert results.count(False) == self.number_of_threads - self.agent_capacity
