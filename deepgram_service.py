"""
Deepgram speech-to-text (streaming WebSocket) and text-to-speech (REST).

Uses raw WebSockets for STT to avoid coupling to the frequently-changing
Deepgram Python SDK internals. TTS is a direct httpx REST call.

STT WebSocket protocol:
  wss://api.deepgram.com/v1/listen
  Send: binary PCM audio chunks
  Receive: JSON transcript / UtteranceEnd events

TTS REST protocol:
  POST https://api.deepgram.com/v1/speak
  Receive: raw PCM bytes
"""

import asyncio
import json
import logging
from urllib.parse import urlencode

import httpx
import websockets  # type: ignore[import-untyped]
import websockets.asyncio.client as ws_client  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)

_STT_WS_HOST = "wss://api.deepgram.com/v1/listen"
_TTS_URL = "https://api.deepgram.com/v1/speak"


class DeepgramSTT:
    """Streams microphone audio to Deepgram STT and queues complete utterances."""

    def __init__(self, config, audio_manager):
        self.config = config
        self.audio = audio_manager
        self._utterance_queue: asyncio.Queue[str] = asyncio.Queue()
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=500)
        self._accumulated: list[str] = []
        self._running = False
        self._ws_task: asyncio.Task | None = None
        self._connected = asyncio.Event()

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def _build_uri(self) -> str:
        params = {
            "model": self.config.deepgram_stt_model,
            "language": "en-US",
            "smart_format": "true",
            "punctuate": "true",
            "endpointing": "500",
            "utterance_end_ms": "1000",
            "interim_results": "true",
            "encoding": "linear16",
            "sample_rate": str(self.config.audio_sample_rate),
            "channels": str(self.config.audio_channels),
            "vad_events": "true",
        }
        return f"{_STT_WS_HOST}?{urlencode(params)}"

    async def start(self) -> None:
        """Open the Deepgram WebSocket. Waits until the connection is ready."""
        self._running = True
        self._connected.clear()
        self._ws_task = asyncio.create_task(self._ws_worker(), name="deepgram-stt")
        try:
            await asyncio.wait_for(self._connected.wait(), timeout=10.0)
        except asyncio.TimeoutError:
            raise RuntimeError("Timed out waiting for Deepgram STT connection.")
        logger.info("Deepgram STT connected.")

    async def _ws_worker(self) -> None:
        """Background task: maintain WebSocket, send audio, process events."""
        uri = self._build_uri()
        headers = {"Authorization": f"Token {self.config.deepgram_api_key}"}

        try:
            async with ws_client.connect(uri, additional_headers=headers) as ws:
                self._connected.set()
                sender_task = asyncio.create_task(self._sender(ws), name="dg-sender")
                try:
                    async for raw in ws:
                        if isinstance(raw, str):
                            await self._process_event(json.loads(raw))
                except websockets.ConnectionClosed as exc:
                    logger.warning(f"Deepgram STT WebSocket closed: {exc}")
                except asyncio.CancelledError:
                    pass
                finally:
                    sender_task.cancel()
                    try:
                        await sender_task
                    except asyncio.CancelledError:
                        pass
        except Exception as exc:
            logger.error(f"Deepgram STT worker error: {exc}")
        finally:
            self._running = False
            self._connected.set()  # Unblock anyone waiting even if connection failed

    async def _sender(self, ws) -> None:
        """Pull audio chunks from the internal queue and write to WebSocket."""
        while True:
            chunk = await self._audio_queue.get()
            if chunk is None:
                break  # Sentinel from stop()
            try:
                await ws.send(chunk)
            except websockets.ConnectionClosed:
                break

    # ------------------------------------------------------------------
    # Event processing
    # ------------------------------------------------------------------

    async def _process_event(self, data: dict) -> None:
        event_type = data.get("type", "")

        if event_type == "Results":
            try:
                text: str = data["channel"]["alternatives"][0]["transcript"]
            except (KeyError, IndexError):
                return

            is_final: bool = data.get("is_final", False)
            speech_final: bool = data.get("speech_final", False)

            if is_final and text:
                self._accumulated.append(text)
                logger.debug(f"STT segment: {text!r}")

            if speech_final and self._accumulated:
                await self._flush()

        elif event_type == "UtteranceEnd":
            # Backup flush in case speech_final was missed
            if self._accumulated:
                await self._flush()

    async def _flush(self) -> None:
        utterance = " ".join(self._accumulated).strip()
        self._accumulated = []
        if utterance:
            logger.info(f"Utterance: {utterance!r}")
            await self._utterance_queue.put(utterance)

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def send(self, audio_bytes: bytes) -> None:
        """Push a PCM audio chunk to the sender queue."""
        if self._running:
            try:
                self._audio_queue.put_nowait(audio_bytes)
            except asyncio.QueueFull:
                pass  # Drop if queue is full; Deepgram will handle gaps

    async def get_utterance(self) -> str:
        """Await and return the next complete user utterance."""
        return await self._utterance_queue.get()

    async def stop(self) -> None:
        self._running = False
        # Unblock the sender with a sentinel
        try:
            self._audio_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        logger.info("Deepgram STT stopped.")


# ---------------------------------------------------------------------------


class DeepgramTTS:
    """Calls the Deepgram TTS REST API and returns raw PCM audio bytes."""

    def __init__(self, config):
        self.config = config
        self._http = httpx.AsyncClient(
            headers={"Authorization": f"Token {config.deepgram_api_key}"},
            timeout=30.0,
        )

    async def synthesize(self, text: str) -> bytes:
        """
        Send text to Deepgram TTS. Returns raw linear16 PCM bytes.
        Raises httpx.HTTPStatusError on API failure.
        """
        params = {
            "model": self.config.deepgram_tts_model,
            "encoding": "linear16",
            "sample_rate": str(self.config.audio_sample_rate),
            "container": "none",
        }
        response = await self._http.post(
            _TTS_URL,
            params=params,
            json={"text": text},
            headers={"Content-Type": "application/json"},
        )
        response.raise_for_status()
        return response.content

    async def close(self) -> None:
        await self._http.aclose()