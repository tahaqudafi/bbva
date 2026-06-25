"""Configuration: load and validate all environment variables."""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Config:
    def __init__(self):
        self.deepgram_api_key: str = os.getenv("DEEPGRAM_API_KEY", "")
        self.deepgram_stt_model: str = os.getenv("DEEPGRAM_STT_MODEL", "")
        self.deepgram_tts_model: str = os.getenv("DEEPGRAM_TTS_MODEL", "")

        self.openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
        self.openrouter_model: str = os.getenv("OPENROUTER_MODEL", "")

        self.google_calendar_id: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")
        self.google_timezone: str = os.getenv("GOOGLE_TIMEZONE", "Europe/Madrid")

        self.business_start_hour: tuple[int, int] = self._parse_time(
            os.getenv("BUSINESS_START_HOUR", "09:00")
        )
        self.business_end_hour: tuple[int, int] = self._parse_time(
            os.getenv("BUSINESS_END_HOUR", "17:00")
        )
        self.appointment_duration_minutes: int = int(
            os.getenv("APPOINTMENT_DURATION_MINUTES", "30")
        )

        self.knowledge_dir: Path = Path(os.getenv("KNOWLEDGE_DIR", "knowledge"))
        self.credentials_file: Path = Path(
            os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        )
        self.token_file: Path = Path(os.getenv("GOOGLE_TOKEN_FILE", "token.json"))

        self.audio_sample_rate: int = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
        self.audio_channels: int = int(os.getenv("AUDIO_CHANNELS", "1"))
        self.vad_energy_threshold: float = float(
            os.getenv("VAD_ENERGY_THRESHOLD", "0.005")
        )

    def _parse_time(self, time_str: str) -> tuple[int, int]:
        parts = time_str.strip().split(":")
        return (int(parts[0]), int(parts[1]))

    def validate(self) -> None:
        """Raise ValueError if any required variable is missing."""
        required = {
            "DEEPGRAM_API_KEY": self.deepgram_api_key,
            "DEEPGRAM_STT_MODEL": self.deepgram_stt_model,
            "DEEPGRAM_TTS_MODEL": self.deepgram_tts_model,
            "OPENROUTER_API_KEY": self.openrouter_api_key,
            "OPENROUTER_MODEL": self.openrouter_model,
        }
        missing = [k for k, v in required.items() if not v.strip()]
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}\n"
                "Copy .env.example to .env and fill in the values."
            )
