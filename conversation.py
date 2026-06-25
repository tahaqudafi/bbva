"""
Conversation manager: orchestrates the STT → LLM (with tools) → TTS loop.

State is held in a ConversationState dataclass for the current session only.
No database or persistent storage is used.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from phonetic import parse_spelled_text, validate_email_format, spell_out_text
from transfer import request_human_transfer

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You are an inbound receptionist voice agent for a local business.
You speak naturally and concisely, as if on a phone call.

BEHAVIOR RULES:
- Ask only one question at a time.
- Keep responses short and conversational. No bullet lists, no markdown, no asterisks.
- Never invent company information. Use only what the search_knowledge tool returns.
- Never say a calendar booking was created unless create_appointment returned success=true.
- Never say a transfer happened. Tell the caller a representative will follow up.
- Do not pretend to be human. Say you are an automated assistant if asked.
- Use the full date and Madrid time when discussing appointments.
- Always ask for explicit yes or no confirmation before creating a calendar event.

CALL FLOW:
1. Greet the caller and ask how you can help.
2. Determine whether they need customer support, an appointment, or a human representative.
3. Support: call search_knowledge. If not found, offer to have someone follow up.
4. Appointment: follow the booking flow using the calendar tools.
5. Human representative: call request_transfer and relay its message. Never claim transfer occurred.

BOOKING FLOW:
1. Ask for their preferred date and time.
2. Ask them to spell their full name letter by letter. Call parse_spelled_text to decode it.
   Read the result back with spell_out_for_readback and ask them to confirm (yes/no).
   Repeat if they say no.
3. Ask them to spell their email address letter by letter. Call parse_spelled_text to decode it.
   Call validate_email to verify the format. Read it back with spell_out_for_readback.
   Ask them to confirm (yes/no). Repeat if they say no or if validation fails.
4. Call check_calendar_availability with the requested date and time.
   If unavailable, offer the alternatives returned by the tool.
5. Read back: confirmed name, confirmed email, full date, time in Madrid timezone, 30-minute duration.
6. Ask: "Shall I go ahead and book that for you?"
7. Only call create_appointment after the caller says yes.
8. Report success only when create_appointment returns success=true.
   If it returns success=false, say the booking could not be completed and offer to try again.

IMPORTANT: When the caller spells something, always call parse_spelled_text on their transcript
before using or reading back any name or email. Never skip the confirmation step.
""".strip()

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge",
            "description": (
                "Search the local knowledge base for an answer to a customer support question."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The customer's question or topic.",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "parse_spelled_text",
            "description": (
                "Decode text where the caller spelled a name or email phonetically "
                "(e.g. 'Alpha Bravo at Charlie dot com'). Returns the normalized string."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "spelled_text": {
                        "type": "string",
                        "description": "The caller's spoken spelling as transcribed.",
                    }
                },
                "required": ["spelled_text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "validate_email",
            "description": "Validate that a string is a properly formatted email address.",
            "parameters": {
                "type": "object",
                "properties": {
                    "email": {
                        "type": "string",
                        "description": "The email address to validate.",
                    }
                },
                "required": ["email"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spell_out_for_readback",
            "description": (
                "Convert a name or email into a spoken letter-by-letter readback string "
                "so you can read it back to the caller for confirmation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to spell out.",
                    }
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_calendar_availability",
            "description": (
                "Check whether a 30-minute appointment slot is free. "
                "Returns availability and up to 3 alternative slots if the slot is taken."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format.",
                    },
                    "time": {
                        "type": "string",
                        "description": "Time in HH:MM 24-hour format.",
                    },
                },
                "required": ["date", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_appointment",
            "description": (
                "Create a 30-minute appointment in Google Calendar. "
                "Call this ONLY after the caller has given explicit yes confirmation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Confirmed customer full name.",
                    },
                    "email": {
                        "type": "string",
                        "description": "Confirmed customer email address.",
                    },
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format.",
                    },
                    "time": {
                        "type": "string",
                        "description": "Time in HH:MM 24-hour format.",
                    },
                },
                "required": ["name", "email", "date", "time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_transfer",
            "description": (
                "Request a transfer to a human representative. "
                "Returns a message to relay to the caller. "
                "Note: live transfer is not implemented — this only returns a message."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why the caller needs a human.",
                    }
                },
                "required": ["reason"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# Conversation state
# ---------------------------------------------------------------------------


@dataclass
class ConversationState:
    intent: Optional[str] = None  # 'support' | 'booking' | 'transfer'
    customer_name: Optional[str] = None
    name_confirmed: bool = False
    customer_email: Optional[str] = None
    email_confirmed: bool = False
    requested_date: Optional[str] = None
    requested_time: Optional[str] = None
    offered_slots: list = field(default_factory=list)
    booking_confirmed: bool = False
    calendar_event_id: Optional[str] = None
    transfer_requested: bool = False
    knowledge_found: bool = False


# ---------------------------------------------------------------------------
# Conversation manager
# ---------------------------------------------------------------------------


class ConversationManager:
    def __init__(self, config, knowledge_base, calendar, llm, stt, tts, audio):
        self.config = config
        self.kb = knowledge_base
        self.calendar = calendar
        self.llm = llm
        self.stt = stt
        self.tts = tts
        self.audio = audio
        self.state = ConversationState()
        self.messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        self._barge_in_event = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    async def run(self, stop_event: asyncio.Event) -> None:
        """Main conversation loop. Runs until stop_event is set."""
        self._loop = asyncio.get_running_loop()
        self.audio.set_barge_in_callback(self._handle_barge_in)

        self.audio.start_microphone()
        await self.stt.start()

        forward_task = asyncio.create_task(
            self._forward_audio(stop_event), name="audio-forward"
        )

        await self._speak("Hello! Thank you for calling. How can I help you today?")

        try:
            while not stop_event.is_set():
                try:
                    utterance = await asyncio.wait_for(
                        self.stt.get_utterance(), timeout=0.5
                    )
                except asyncio.TimeoutError:
                    continue

                self._barge_in_event.clear()
                await self._handle_utterance(utterance)

        finally:
            forward_task.cancel()
            try:
                await forward_task
            except asyncio.CancelledError:
                pass
            await self.stt.stop()
            self.audio.stop_microphone()

    # ------------------------------------------------------------------
    # Barge-in
    # ------------------------------------------------------------------

    def _handle_barge_in(self) -> None:
        """Called from the sounddevice callback thread when speech is detected."""
        if self._loop:
            self._loop.call_soon_threadsafe(self._barge_in_event.set)
        self.audio.stop_playback()
        logger.info("Barge-in detected — playback stopped.")

    # ------------------------------------------------------------------
    # Audio forwarding
    # ------------------------------------------------------------------

    async def _forward_audio(self, stop_event: asyncio.Event) -> None:
        """Read mic chunks from the queue and push them to Deepgram STT."""
        loop = asyncio.get_running_loop()
        while not stop_event.is_set():
            chunk = await loop.run_in_executor(
                None, self.audio.get_audio_chunk, 0.1
            )
            if chunk:
                await self.stt.send(chunk)

    # ------------------------------------------------------------------
    # Utterance handling
    # ------------------------------------------------------------------

    async def _handle_utterance(self, utterance: str) -> None:
        """Process one complete user utterance through the LLM + tool loop."""
        print(f"\nYou  : {utterance}")
        self.messages.append({"role": "user", "content": utterance})

        # Tool-call loop: keep calling LLM until it produces a plain text response
        while True:
            if self._barge_in_event.is_set():
                logger.info("Barge-in during LLM call — aborting response.")
                # Remove the user message so it does not cause a dangling turn
                if self.messages and self.messages[-1]["role"] == "user":
                    self.messages.pop()
                self._barge_in_event.clear()
                return

            try:
                response = await self.llm.chat(self.messages, TOOLS)
            except Exception as exc:
                logger.error(f"LLM error: {exc}")
                await self._speak(
                    "I'm sorry, I had a problem processing that. Could you please repeat?"
                )
                return

            self.messages.append(response)

            tool_calls = response.get("tool_calls")
            if tool_calls:
                tool_results = []
                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args = json.loads(tc["function"]["arguments"])
                    result = await self._execute_tool(fn_name, fn_args)
                    logger.debug(f"Tool {fn_name} → {result}")
                    tool_results.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "content": json.dumps(result),
                        }
                    )
                self.messages.extend(tool_results)
                continue  # Let LLM see the tool results

            # Plain text response
            text = (response.get("content") or "").strip()
            if text:
                print(f"Agent : {text}")
                await self._speak(text)
            break

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def _execute_tool(self, name: str, args: dict) -> dict:
        if name == "search_knowledge":
            return self._tool_search_knowledge(args["query"])

        if name == "parse_spelled_text":
            parsed = parse_spelled_text(args["spelled_text"])
            return {"parsed": parsed}

        if name == "validate_email":
            email = args["email"]
            return {"email": email, "valid": validate_email_format(email)}

        if name == "spell_out_for_readback":
            return {"readback": spell_out_text(args["text"])}

        if name == "check_calendar_availability":
            return await self._tool_check_availability(args["date"], args["time"])

        if name == "create_appointment":
            return await self._tool_create_appointment(
                args["name"], args["email"], args["date"], args["time"]
            )

        if name == "request_transfer":
            result = request_human_transfer(args.get("reason", ""))
            self.state.transfer_requested = True
            return {
                "implemented": False,
                "message": result.message,
            }

        return {"error": f"Unknown tool: {name}"}

    def _tool_search_knowledge(self, query: str) -> dict:
        result = self.kb.search(query)
        if result:
            self.state.knowledge_found = True
            return {"found": True, "content": result}
        return {"found": False, "content": None}

    async def _tool_check_availability(self, date_str: str, time_str: str) -> dict:
        try:
            tz = ZoneInfo(self.config.google_timezone)
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=tz)
        except ValueError as exc:
            return {"available": False, "reason": f"Invalid date/time format: {exc}", "alternatives": []}

        if not self.calendar.is_business_hours(dt):
            return {
                "available": False,
                "reason": "That time is outside business hours (Monday–Friday, 09:00–17:00 Madrid time).",
                "alternatives": [],
            }

        try:
            available = self.calendar.check_availability(dt)
        except Exception as exc:
            return {"available": False, "reason": f"Calendar error: {exc}", "alternatives": []}

        if available:
            self.state.requested_date = date_str
            self.state.requested_time = time_str
            return {"available": True, "slot": f"{date_str} {time_str}"}

        # Find alternatives
        try:
            slots = self.calendar.find_available_slots(dt, count=3)
        except Exception:
            slots = []

        alternatives = [
            {"date": s.strftime("%Y-%m-%d"), "time": s.strftime("%H:%M")} for s in slots
        ]
        return {
            "available": False,
            "reason": "That slot is already booked.",
            "alternatives": alternatives,
        }

    async def _tool_create_appointment(
        self, name: str, email: str, date_str: str, time_str: str
    ) -> dict:
        try:
            tz = ZoneInfo(self.config.google_timezone)
            dt = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            dt = dt.replace(tzinfo=tz)
        except ValueError as exc:
            return {"success": False, "error": f"Invalid date/time format: {exc}"}

        if not self.calendar.is_business_hours(dt):
            return {"success": False, "error": "Slot is outside business hours."}

        try:
            available = self.calendar.check_availability(dt)
        except Exception as exc:
            return {"success": False, "error": f"Could not verify availability: {exc}"}

        if not available:
            return {"success": False, "error": "Slot is no longer available."}

        try:
            event = self.calendar.create_appointment(name, email, dt)
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        self.state.booking_confirmed = True
        self.state.calendar_event_id = event.get("id")
        self.state.customer_name = name
        self.state.customer_email = email

        return {
            "success": True,
            "event_id": event.get("id"),
            "message": (
                f"Appointment confirmed for {name} on {date_str} at {time_str} Madrid time, "
                f"30 minutes. A confirmation has been sent to {email}."
            ),
        }

    # ------------------------------------------------------------------
    # TTS playback
    # ------------------------------------------------------------------

    async def _speak(self, text: str) -> None:
        """Synthesize text with Deepgram TTS and play through speakers."""
        if not text.strip():
            return

        self._barge_in_event.clear()

        try:
            audio_bytes = await self.tts.synthesize(text)
        except Exception as exc:
            logger.error(f"TTS synthesis failed: {exc}")
            print(f"[TTS unavailable]: {text}")
            return

        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            self.audio.play_audio,
            audio_bytes,
            self.config.audio_sample_rate,
        )
