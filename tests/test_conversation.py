"""
Unit tests for conversation state, transfer stub, and tool-result logic
that can be verified without live APIs.
"""

import asyncio
import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from dataclasses import fields

from conversation import ConversationState, ConversationManager
from transfer import request_human_transfer, TransferResult


# ---------------------------------------------------------------------------
# ConversationState
# ---------------------------------------------------------------------------

class TestConversationState:
    def test_all_fields_default_to_none_or_false(self):
        s = ConversationState()
        assert s.intent is None
        assert s.customer_name is None
        assert s.name_confirmed is False
        assert s.customer_email is None
        assert s.email_confirmed is False
        assert s.requested_date is None
        assert s.requested_time is None
        assert s.offered_slots == []
        assert s.booking_confirmed is False
        assert s.calendar_event_id is None
        assert s.transfer_requested is False
        assert s.knowledge_found is False

    def test_two_instances_are_independent(self):
        s1 = ConversationState()
        s1.customer_name = "Alice"
        s1.booking_confirmed = True
        s1.offered_slots.append("slot1")

        s2 = ConversationState()
        assert s2.customer_name is None
        assert s2.booking_confirmed is False
        assert s2.offered_slots == []


# ---------------------------------------------------------------------------
# Transfer stub
# ---------------------------------------------------------------------------

class TestTransferStub:
    def test_always_returns_not_implemented(self):
        result = request_human_transfer("Help needed")
        assert isinstance(result, TransferResult)
        assert result.success is False
        assert result.status == "not_implemented"

    def test_message_is_non_empty(self):
        result = request_human_transfer()
        assert len(result.message) > 0

    def test_message_does_not_claim_success(self):
        result = request_human_transfer("any reason")
        lowered = result.message.lower()
        # Must not say something like "transfer successful"
        assert "success" not in lowered or "not" in lowered


# ---------------------------------------------------------------------------
# Tool: search_knowledge
# ---------------------------------------------------------------------------

class TestToolSearchKnowledge:
    def _make_manager(self, kb_result):
        kb = MagicMock()
        kb.search.return_value = kb_result
        mgr = ConversationManager.__new__(ConversationManager)
        mgr.kb = kb
        mgr.state = ConversationState()
        return mgr

    def test_found_result_sets_knowledge_found_flag(self):
        mgr = self._make_manager("Here is the answer.")
        result = mgr._tool_search_knowledge("return policy")
        assert result["found"] is True
        assert "answer" in result["content"]
        assert mgr.state.knowledge_found is True

    def test_not_found_result(self):
        mgr = self._make_manager(None)
        result = mgr._tool_search_knowledge("unknown topic")
        assert result["found"] is False
        assert result["content"] is None
        assert mgr.state.knowledge_found is False


# ---------------------------------------------------------------------------
# Tool: check_calendar_availability (business-hours enforcement)
# ---------------------------------------------------------------------------

class TestToolCheckAvailability:
    def _make_manager(self, is_business=True, is_available=True):
        config = MagicMock()
        config.google_timezone = "Europe/Madrid"
        config.appointment_duration_minutes = 30

        cal = MagicMock()
        cal.is_business_hours.return_value = is_business
        cal.check_availability.return_value = is_available
        cal.find_available_slots.return_value = []

        mgr = ConversationManager.__new__(ConversationManager)
        mgr.config = config
        mgr.calendar = cal
        mgr.state = ConversationState()
        return mgr

    def test_available_slot_returns_true(self):
        mgr = self._make_manager(is_business=True, is_available=True)
        result = asyncio.run(
            mgr._tool_check_availability("2026-07-07", "10:00")
        )
        assert result["available"] is True

    def test_outside_business_hours_returns_unavailable(self):
        mgr = self._make_manager(is_business=False)
        result = asyncio.run(
            mgr._tool_check_availability("2026-07-07", "08:00")
        )
        assert result["available"] is False
        assert "business hours" in result["reason"].lower()

    def test_occupied_slot_returns_false_with_alternatives(self):
        from datetime import datetime
        from zoneinfo import ZoneInfo
        tz = ZoneInfo("Europe/Madrid")
        alt_slot = datetime(2026, 7, 7, 10, 30, tzinfo=tz)

        mgr = self._make_manager(is_business=True, is_available=False)
        mgr.calendar.find_available_slots.return_value = [alt_slot]

        result = asyncio.run(
            mgr._tool_check_availability("2026-07-07", "10:00")
        )
        assert result["available"] is False
        assert len(result["alternatives"]) == 1

    def test_invalid_date_format_returns_error(self):
        mgr = self._make_manager()
        result = asyncio.run(
            mgr._tool_check_availability("not-a-date", "not-a-time")
        )
        assert result["available"] is False


# ---------------------------------------------------------------------------
# Tool: create_appointment
# ---------------------------------------------------------------------------

class TestToolCreateAppointment:
    def _make_manager(self, is_business=True, is_available=True, create_raises=None):
        config = MagicMock()
        config.google_timezone = "Europe/Madrid"
        config.appointment_duration_minutes = 30

        cal = MagicMock()
        cal.is_business_hours.return_value = is_business
        cal.check_availability.return_value = is_available
        if create_raises:
            cal.create_appointment.side_effect = create_raises
        else:
            cal.create_appointment.return_value = {"id": "evt-123", "htmlLink": "http://cal"}

        mgr = ConversationManager.__new__(ConversationManager)
        mgr.config = config
        mgr.calendar = cal
        mgr.state = ConversationState()
        return mgr

    def test_success_sets_booking_confirmed(self):
        mgr = self._make_manager()
        result = asyncio.run(
            mgr._tool_create_appointment("Alice", "alice@example.com", "2026-07-07", "10:00")
        )
        assert result["success"] is True
        assert mgr.state.booking_confirmed is True
        assert mgr.state.calendar_event_id == "evt-123"

    def test_outside_hours_cannot_book(self):
        mgr = self._make_manager(is_business=False)
        result = asyncio.run(
            mgr._tool_create_appointment("Alice", "alice@example.com", "2026-07-07", "08:00")
        )
        assert result["success"] is False
        assert mgr.state.booking_confirmed is False

    def test_unavailable_slot_cannot_book(self):
        mgr = self._make_manager(is_available=False)
        result = asyncio.run(
            mgr._tool_create_appointment("Alice", "alice@example.com", "2026-07-07", "10:00")
        )
        assert result["success"] is False

    def test_calendar_api_failure_returns_failure(self):
        from googleapiclient.errors import HttpError
        # Build a minimal fake HttpError
        resp = MagicMock()
        resp.status = 500
        err = HttpError(resp=resp, content=b"Internal Server Error")
        mgr = self._make_manager(create_raises=err)
        result = asyncio.run(
            mgr._tool_create_appointment("Alice", "alice@example.com", "2026-07-07", "10:00")
        )
        assert result["success"] is False
        assert mgr.state.booking_confirmed is False

    def test_success_message_does_not_appear_on_failure(self):
        resp = MagicMock()
        resp.status = 500
        from googleapiclient.errors import HttpError
        err = HttpError(resp=resp, content=b"Error")
        mgr = self._make_manager(create_raises=err)
        result = asyncio.run(
            mgr._tool_create_appointment("Bob", "bob@example.com", "2026-07-07", "11:00")
        )
        assert "confirmed" not in result.get("message", "").lower()