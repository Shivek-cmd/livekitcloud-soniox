"""Measure Soniox speech-end→FINAL delay under restaurant noise (PR 066).

Synthesizes a test order phrase (macOS `say`), mixes it with the agent's own
ambient track at several SNRs, streams each mix to the Soniox real-time WS API
at real-time pace, and prints how long after the last speech frame the FINAL
transcript (endpoint) arrived — per (sensitivity × max_delay × latency-level)
combo. This is the evidence loop for tuning SONIOX_ENDPOINT_SENSITIVITY /
SONIOX_MAX_ENDPOINT_DELAY_MS / SONIOX_ENDPOINT_LATENCY_ADJUSTMENT_LEVEL.

Usage:
    uv run python scripts/endpoint_noise_probe.py

Needs: SONIOX_API_KEY in .env, macOS `say`, ffmpeg on PATH.
"""

from __future__ import annotations

import array
import asyncio
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import aiohttp
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parent.parent
AMBIENCE_MP3 = REPO_ROOT / "data" / "audio" / "restaurant_ambience.mp3"
SONIOX_WS_URL = "wss://stt-rt.soniox.com/transcribe-websocket"

SAMPLE_RATE = 16000
FRAME_MS = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000
NOISE_TAIL_SEC = 8.0  # noise-only tail; also the cap on waiting for a FINAL

TEST_PHRASE = "Hi, can I get two samosas and one mango lassi for pickup please."

# (label, snr_db) — snr_db=None means no noise mixed in.
SNR_CASES: list[tuple[str, float | None]] = [
    ("clean", None),
    ("10dB", 10.0),
    ("5dB", 5.0),
]

# (endpoint_sensitivity, max_endpoint_delay_ms, endpoint_latency_adjustment_level)
PARAM_COMBOS: list[tuple[float | None, int, int | None]] = [
    (None, 2000, None),  # plugin defaults before PR 064
    (None, 1000, None),  # PR 064 default
    (0.3, 1000, None),  # PR 066 sensitivity
    (0.3, 1000, 2),  # PR 066 full stack
    (0.3, 1500, 2),  # Soniox voice-AI recommendation
]


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {proc.stderr.strip()[:400]}")


def _decode_to_pcm(path: Path, duration_sec: float | None = None) -> array.array:
    """Decode any audio file to 16kHz mono s16le PCM via ffmpeg."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(path)]
    if duration_sec is not None:
        cmd += ["-t", f"{duration_sec:.2f}"]
    cmd += ["-f", "s16le", "-acodec", "pcm_s16le", "-ac", "1", "-ar", str(SAMPLE_RATE), "-"]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {proc.stderr.decode()[:400]}")
    pcm = array.array("h")
    pcm.frombytes(proc.stdout[: len(proc.stdout) // 2 * 2])
    return pcm


def _synthesize_phrase() -> array.array:
    """Render TEST_PHRASE with macOS `say` (Soniox TTS synth failed for this —
    APIConnectionError — so we use the OS voice; see turnwatchdog.md)."""
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "phrase.aiff"
        _run(["say", "-o", str(aiff), TEST_PHRASE])
        return _decode_to_pcm(aiff)


def _rms(pcm: array.array) -> float:
    if not pcm:
        return 0.0
    return math.sqrt(sum(s * s for s in pcm) / len(pcm))


def _mix_at_snr(speech: array.array, noise: array.array, snr_db: float | None) -> array.array:
    """speech + scaled noise, plus a noise-only tail of NOISE_TAIL_SEC."""
    tail_samples = int(NOISE_TAIL_SEC * SAMPLE_RATE)
    total = len(speech) + tail_samples
    if snr_db is None:
        mixed = array.array("h", speech)
        mixed.extend([0] * tail_samples)
        return mixed

    if len(noise) < total:
        reps = total // len(noise) + 1
        noise = array.array("h", noise * reps)
    speech_rms = _rms(speech)
    noise_rms = _rms(noise[:total]) or 1.0
    # Scale noise so speech_rms / (noise_rms * scale) matches the target SNR.
    scale = speech_rms / (noise_rms * (10 ** (snr_db / 20)))

    mixed = array.array("h")
    for i in range(total):
        s = speech[i] if i < len(speech) else 0
        v = s + int(noise[i] * scale)
        mixed.append(max(-32768, min(32767, v)))
    return mixed


@dataclass
class ProbeResult:
    final_delay_ms: int | None
    transcript: str


async def _probe_once(
    api_key: str,
    pcm: array.array,
    speech_end_sample: int,
    sensitivity: float | None,
    max_delay_ms: int,
    latency_level: int | None,
) -> ProbeResult:
    config: dict = {
        "api_key": api_key,
        "model": "stt-rt-v5",
        "audio_format": "pcm_s16le",
        "sample_rate": SAMPLE_RATE,
        "num_channels": 1,
        "language_hints": ["pa", "en", "hi"],
        "enable_endpoint_detection": True,
        "max_endpoint_delay_ms": max_delay_ms,
    }
    if sensitivity is not None:
        config["endpoint_sensitivity"] = sensitivity
    if latency_level is not None:
        config["endpoint_latency_adjustment_level"] = latency_level

    speech_end_at: float | None = None
    final_at: float | None = None
    transcript_parts: list[str] = []

    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(SONIOX_WS_URL) as ws:
            await ws.send_str(json.dumps(config))

            async def _send() -> None:
                nonlocal speech_end_at
                sent = 0
                start = time.monotonic()
                while sent < len(pcm):
                    frame = pcm[sent : sent + FRAME_SAMPLES]
                    await ws.send_bytes(frame.tobytes())
                    sent += FRAME_SAMPLES
                    if speech_end_at is None and sent >= speech_end_sample:
                        speech_end_at = time.monotonic()
                    # Real-time pacing: sleep until this frame's wall-clock slot.
                    target = start + sent / SAMPLE_RATE
                    delay = target - time.monotonic()
                    if delay > 0:
                        await asyncio.sleep(delay)

            send_task = asyncio.create_task(_send())
            try:
                deadline = time.monotonic() + len(pcm) / SAMPLE_RATE + NOISE_TAIL_SEC
                while final_at is None and time.monotonic() < deadline:
                    timeout = max(0.1, deadline - time.monotonic())
                    try:
                        msg = await ws.receive(timeout=timeout)
                    except asyncio.TimeoutError:
                        break
                    if msg.type != aiohttp.WSMsgType.TEXT:
                        break
                    data = json.loads(msg.data)
                    if data.get("error_code"):
                        raise RuntimeError(f"Soniox error: {data}")
                    for token in data.get("tokens", []):
                        if token.get("text") == "<end>":
                            final_at = time.monotonic()
                        elif token.get("is_final"):
                            transcript_parts.append(token.get("text", ""))
            finally:
                send_task.cancel()
                try:
                    await send_task
                except asyncio.CancelledError:
                    pass

    delay_ms = None
    if final_at is not None and speech_end_at is not None:
        delay_ms = int((final_at - speech_end_at) * 1000)
    return ProbeResult(final_delay_ms=delay_ms, transcript="".join(transcript_parts).strip())


async def main() -> int:
    load_dotenv()
    api_key = os.getenv("SONIOX_API_KEY", "").strip()
    if not api_key:
        print("SONIOX_API_KEY not set (load it via .env)", file=sys.stderr)
        return 1
    if not AMBIENCE_MP3.exists():
        print(f"missing ambience track: {AMBIENCE_MP3}", file=sys.stderr)
        return 1

    print(f"phrase: {TEST_PHRASE!r}")
    speech = _synthesize_phrase()
    speech_sec = len(speech) / SAMPLE_RATE
    print(f"synthesized {speech_sec:.1f}s of speech; decoding ambience…")
    noise = _decode_to_pcm(AMBIENCE_MP3, duration_sec=speech_sec + NOISE_TAIL_SEC + 5)

    header = f"{'case':>6} | {'sens':>5} | {'max_delay':>9} | {'level':>5} | {'final_delay':>11} | transcript"
    print(header)
    print("-" * len(header))
    for label, snr_db in SNR_CASES:
        pcm = _mix_at_snr(speech, noise, snr_db)
        for sensitivity, max_delay_ms, latency_level in PARAM_COMBOS:
            result = await _probe_once(
                api_key, pcm, len(speech), sensitivity, max_delay_ms, latency_level
            )
            delay = f"{result.final_delay_ms}ms" if result.final_delay_ms is not None else "NO FINAL"
            sens = "srv" if sensitivity is None else f"{sensitivity:.1f}"
            level = "srv" if latency_level is None else str(latency_level)
            print(
                f"{label:>6} | {sens:>5} | {max_delay_ms:>9} | {level:>5} | {delay:>11} | "
                f"{result.transcript[:50]!r}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
