"""
Inbound Voice Agent — local entry point.

Start with:  python main.py
Stop with:   Ctrl+C
"""

import asyncio
import logging
import sys

from config import Config
from audio import AudioManager
from deepgram_service import DeepgramSTT, DeepgramTTS
from openrouter_service import OpenRouterService
from calendar_service import CalendarService
from knowledge_base import KnowledgeBase
from conversation import ConversationManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _ok(msg: str) -> None:
    print(f"  [ok] {msg}")


def _err(msg: str) -> None:
    print(f"  [error] {msg}", file=sys.stderr)


async def main() -> None:
    print()
    print("=" * 56)
    print("  Inbound Voice Agent")
    print("=" * 56)
    print()

    # 1. Configuration --------------------------------------------------
    try:
        config = Config()
        config.validate()
        _ok("Configuration loaded")
    except ValueError as exc:
        _err(str(exc))
        sys.exit(1)

    # 2. Knowledge base -------------------------------------------------
    kb = KnowledgeBase(config.knowledge_dir)
    try:
        kb.load()
        if kb.is_empty:
            print("  [warn] Knowledge folder is empty — support answers unavailable.")
        else:
            _ok(f"Knowledge base loaded: {', '.join(kb.loaded_files)}")
    except Exception as exc:
        _err(f"Knowledge base failed to load: {exc}")
        sys.exit(1)

    # 3. Google Calendar ------------------------------------------------
    calendar = CalendarService(config)
    try:
        calendar.initialize()
        _ok("Google Calendar connected")
    except FileNotFoundError as exc:
        _err(str(exc))
        sys.exit(1)
    except Exception as exc:
        _err(f"Google Calendar error: {exc}")
        sys.exit(1)

    # 4. LLM and TTS clients --------------------------------------------
    llm = OpenRouterService(config)
    tts = DeepgramTTS(config)

    # 5. Audio ----------------------------------------------------------
    audio = AudioManager(config)
    try:
        audio.initialize()
        _ok("Audio devices ready")
    except Exception as exc:
        _err(f"Audio initialization failed: {exc}")
        sys.exit(1)

    # 6. STT ------------------------------------------------------------
    stt = DeepgramSTT(config, audio)

    # 7. Conversation manager -------------------------------------------
    conv = ConversationManager(config, kb, calendar, llm, stt, tts, audio)

    # 8. Run ------------------------------------------------------------
    stop_event = asyncio.Event()

    print()
    print("  Agent is ready. Speak to begin. Press Ctrl+C to stop.")
    print("-" * 56)
    print()

    try:
        await conv.run(stop_event)
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        audio.cleanup()
        await tts.close()
        await llm.close()
        print()
        print("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting.")