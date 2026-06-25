"""
Audio I/O for Windows using sounddevice + PortAudio.

Microphone input streams raw int16 PCM chunks into a thread-safe queue.
Speaker output plays raw int16 PCM via sounddevice.
Barge-in detection compares RMS energy against a configurable threshold
and calls a registered callback (from the sounddevice input thread)
whenever the user speaks during playback.

Windows isolation: all sounddevice calls are here. To add Linux support
later, replace or extend this module only.
"""

import logging
import queue
import threading
from typing import Callable

import numpy as np
import sounddevice as sd

logger = logging.getLogger(__name__)


class AudioManager:
    def __init__(self, config):
        self.config = config
        self.sample_rate: int = config.audio_sample_rate
        self.channels: int = config.audio_channels
        self._vad_threshold: float = config.vad_energy_threshold

        # Thread-safe queue: sounddevice callback → async consumer
        self._mic_queue: queue.Queue[bytes] = queue.Queue(maxsize=200)

        self._input_stream: sd.InputStream | None = None
        self._playback_stop = threading.Event()
        self._is_playing = False
        self._barge_in_callback: Callable | None = None

    # ------------------------------------------------------------------
    # Initialization
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Probe audio devices; raise if no input or output is available."""
        try:
            inp = sd.query_devices(kind="input")
            out = sd.query_devices(kind="output")
        except sd.PortAudioError as exc:
            raise RuntimeError(f"Audio device error: {exc}") from exc

        logger.info(f"Input device : {inp['name']}")
        logger.info(f"Output device: {out['name']}")

    # ------------------------------------------------------------------
    # Barge-in
    # ------------------------------------------------------------------

    def set_barge_in_callback(self, callback: Callable) -> None:
        """Register the function to call when speech is detected during playback."""
        self._barge_in_callback = callback

    # ------------------------------------------------------------------
    # Microphone
    # ------------------------------------------------------------------

    def start_microphone(self) -> None:
        """Begin capturing microphone audio into the internal queue."""

        def _callback(
            indata: np.ndarray, frames: int, time_info, status
        ) -> None:
            if status:
                logger.debug(f"Mic status: {status}")

            audio_bytes = indata.tobytes()

            # Drop oldest chunk if the queue is full to avoid memory growth
            if self._mic_queue.full():
                try:
                    self._mic_queue.get_nowait()
                except queue.Empty:
                    pass
            self._mic_queue.put_nowait(audio_bytes)

            # Barge-in VAD: only fires when TTS is playing
            if self._is_playing and self._barge_in_callback:
                rms = float(np.sqrt(np.mean(indata.astype(np.float32) ** 2))) / 32768.0
                if rms > self._vad_threshold:
                    self._barge_in_callback()

        self._input_stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="int16",
            blocksize=960,  # ~60 ms at 16 kHz
            callback=_callback,
        )
        self._input_stream.start()
        logger.info("Microphone started.")

    def stop_microphone(self) -> None:
        if self._input_stream:
            self._input_stream.stop()
            self._input_stream.close()
            self._input_stream = None
            logger.info("Microphone stopped.")

    def get_audio_chunk(self, timeout: float = 0.1) -> bytes | None:
        """Blocking read from the mic queue; returns None on timeout."""
        try:
            return self._mic_queue.get(timeout=timeout)
        except queue.Empty:
            return None

    def clear_mic_queue(self) -> None:
        """Discard all buffered mic audio (e.g. after barge-in)."""
        while not self._mic_queue.empty():
            try:
                self._mic_queue.get_nowait()
            except queue.Empty:
                break

    # ------------------------------------------------------------------
    # Playback
    # ------------------------------------------------------------------

    def play_audio(self, audio_bytes: bytes, sample_rate: int | None = None) -> None:
        """
        Play raw int16 PCM audio synchronously.
        Blocks until playback finishes or stop_playback() is called.
        Must be called from a thread (not the event loop).
        """
        sr = sample_rate or self.sample_rate
        self._playback_stop.clear()
        self._is_playing = True

        try:
            arr = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0
            # Play in 100 ms chunks so stop_playback can interrupt promptly
            chunk = sr // 10
            offset = 0
            while offset < len(arr):
                if self._playback_stop.is_set():
                    break
                sd.play(arr[offset : offset + chunk], samplerate=sr, blocking=True)
                offset += chunk
        finally:
            self._is_playing = False

    def stop_playback(self) -> None:
        """Signal the playback loop to stop and halt the sounddevice stream."""
        self._playback_stop.set()
        sd.stop()
        self._is_playing = False

    @property
    def is_playing(self) -> bool:
        return self._is_playing

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self) -> None:
        self.stop_playback()
        self.stop_microphone()