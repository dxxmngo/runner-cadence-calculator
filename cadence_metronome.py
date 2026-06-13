#!/usr/bin/env python3
"""
Running Cadence Metronome Generator
=====================================
Creates an MP3 audio guide that holds you on cadence through a race using a
progressive (slow → fast) pacing strategy.

Beat pattern : 4/4 time — beats 1, 2, 3 are regular clicks (880 Hz);
               beat 4 is a higher-pitched accent (1760 Hz) marking the measure.
Cadence      : linearly progresses from 165 SPM (race start) → 180 SPM (finish).

Dependencies
------------
  Required : numpy          (pip install numpy)
  Optional : pydub + ffmpeg (pip install pydub  AND  ffmpeg in PATH)
             Falls back to WAV output when neither is available.
"""

from __future__ import annotations

import os
import sys
import wave
import subprocess
from datetime import datetime

import numpy as np

# ── tuneable constants ────────────────────────────────────────────────────────
SAMPLE_RATE   = 22050   # Hz — good quality; half the size of 44.1 kHz
REGULAR_FREQ  = 880     # Hz — A5: regular beats (1, 2, 3)
ACCENT_FREQ   = 1760    # Hz — A6 (one octave up): beat 4 ascent/accent
CLICK_MS      = 45      # total click duration in milliseconds
VOLUME        = 0.82    # amplitude 0.0–1.0
CHUNK_SEC     = 60      # seconds rendered per chunk (caps peak RAM use)
START_CADENCE = 165     # SPM at race start
END_CADENCE   = 180     # SPM at race finish


# ── audio primitive ───────────────────────────────────────────────────────────

def make_click(freq: float, duration_ms: float = CLICK_MS) -> np.ndarray:
    """
    Sine-wave click with near-instant attack and exponential decay (tau ≈ duration/5).
    Returns a float32 array normalised to [-1, +1].
    """
    n = int(SAMPLE_RATE * duration_ms / 1000)
    t = np.linspace(0.0, duration_ms / 1000.0, n, endpoint=False)
    tone = np.sin(2.0 * np.pi * freq * t).astype(np.float32)
    tau  = (duration_ms / 1000.0) / 5.0
    env  = np.exp(-t / tau).astype(np.float32)
    return tone * env


# ── helpers ───────────────────────────────────────────────────────────────────

def cadence_at(elapsed: float, total: float) -> float:
    """Linear interpolation from START_CADENCE to END_CADENCE."""
    frac = float(np.clip(elapsed / total, 0.0, 1.0))
    return START_CADENCE + (END_CADENCE - START_CADENCE) * frac


def parse_pace(text: str) -> float:
    """Parse 'MM:SS' or decimal string → decimal minutes per km."""
    text = text.strip()
    if ":" in text:
        m, s = text.split(":", 1)
        return int(m) + int(s) / 60.0
    return float(text)


def fmt_pace(min_per_km: float) -> str:
    m = int(min_per_km)
    s = round((min_per_km - m) * 60)
    if s == 60:
        m += 1
        s = 0
    return f"{m}:{s:02d}"


def fmt_time(total_seconds: float) -> str:
    h = int(total_seconds // 3600)
    m = int((total_seconds % 3600) // 60)
    s = int(total_seconds % 60)
    return f"{h}h {m:02d}m {s:02d}s" if h else f"{m}m {s:02d}s"


# ── beat schedule ─────────────────────────────────────────────────────────────

def build_beat_schedule(total_sec: float) -> list:
    """
    Return [(sample_index: int, is_accent: bool), …] for the whole race.
    Cadence increases linearly from START_CADENCE to END_CADENCE.
    Every 4th beat (count % 4 == 3) is the accent — the 4th beat of the measure.
    """
    beats = []
    t     = 0.0
    count = 0
    while t < total_sec:
        beats.append((int(t * SAMPLE_RATE), count % 4 == 3))
        t    += 60.0 / cadence_at(t, total_sec)
        count += 1
    return beats


# ── WAV writer ────────────────────────────────────────────────────────────────

def write_wav_chunked(path: str, beats: list, total_sec: float,
                      regular: np.ndarray, accent: np.ndarray) -> None:
    """
    Stream mono 16-bit WAV in CHUNK_SEC-second slices.
    Correctly handles clicks that straddle a chunk boundary.
    """
    total_samples = int(total_sec * SAMPLE_RATE)
    chunk_samples = int(CHUNK_SEC * SAMPLE_RATE)
    click_len     = len(regular)          # accent click has the same length
    n_beats       = len(beats)
    beat_ptr      = 0                     # first beat still relevant to future chunks

    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)                # 16-bit samples
        wf.setframerate(SAMPLE_RATE)

        chunk_start = 0
        while chunk_start < total_samples:
            chunk_end = min(chunk_start + chunk_samples, total_samples)
            buf       = np.zeros(chunk_end - chunk_start, dtype=np.float32)

            # Render every beat whose click overlaps this chunk
            i = beat_ptr
            while i < n_beats:
                bs, is_ac = beats[i]
                if bs >= chunk_end:
                    break                 # beats beyond this chunk come later
                if bs + click_len > chunk_start:
                    click     = accent if is_ac else regular
                    src_start = max(0, chunk_start - bs)
                    dst_start = max(0, bs - chunk_start)
                    src_end   = min(click_len, chunk_end - bs)
                    length    = src_end - src_start
                    buf[dst_start : dst_start + length] += (
                        click[src_start : src_end] * VOLUME
                    )
                i += 1

            # Advance beat_ptr past beats whose clips have fully ended in this chunk
            while (beat_ptr < n_beats
                   and beats[beat_ptr][0] + click_len <= chunk_end):
                beat_ptr += 1

            np.clip(buf, -1.0, 1.0, out=buf)
            wf.writeframes((buf * 32767.0).astype(np.int16).tobytes())

            chunk_start = chunk_end

            # Live progress bar
            pct  = chunk_start / total_samples
            bar  = "█" * int(pct * 40) + "░" * (40 - int(pct * 40))
            print(f"  [{bar}] {pct * 100:5.1f}%", end="\r", flush=True)

    print()  # newline after final progress update


# ── MP3 conversion ────────────────────────────────────────────────────────────

def convert_to_mp3(wav_path: str, mp3_path: str) -> bool:
    """Try pydub first, then fall back to ffmpeg CLI. Returns True on success."""
    # attempt 1 — pydub
    try:
        from pydub import AudioSegment
        AudioSegment.from_wav(wav_path).export(mp3_path, format="mp3", bitrate="128k")
        return True
    except Exception:
        pass

    # attempt 2 — ffmpeg CLI
    result = subprocess.run(
        ["ffmpeg", "-y", "-i", wav_path,
         "-acodec", "libmp3lame", "-ab", "128k", mp3_path],
        capture_output=True,
    )
    return result.returncode == 0


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print()
    print("╔══════════════════════════════════════════╗")
    print("║   Running Cadence Metronome Generator    ║")
    print("╚══════════════════════════════════════════╝")
    print()

    # ── user inputs ──────────────────────────────────────────────────────────
    while True:
        raw = input("Average race pace (MM:SS /km, e.g. 5:30): ").strip()
        try:
            avg_pace = parse_pace(raw)
            if avg_pace <= 0:
                raise ValueError
            break
        except (ValueError, IndexError):
            print("  → Enter pace as MM:SS (e.g. 5:30) or decimal minutes (e.g. 5.5)\n")

    while True:
        raw = input("Total race distance in km (e.g. 10 or 21.1): ").strip()
        try:
            distance = float(raw)
            if distance <= 0:
                raise ValueError
            break
        except ValueError:
            print("  → Enter a positive number (e.g. 5, 10, 21.1, 42.2)\n")

    # ── race summary ─────────────────────────────────────────────────────────
    total_sec  = distance * avg_pace * 60.0
    pace_start = avg_pace * 1.10   # ~10 % slower at the gun
    pace_end   = avg_pace * 0.90   # ~10 % faster at the finish

    print()
    print("── Race summary ─────────────────────────────────────")
    print(f"  Distance      : {distance} km")
    print(f"  Average pace  : {fmt_pace(avg_pace)} /km")
    print(f"  Start pace    : ~{fmt_pace(pace_start)} /km  (first km)")
    print(f"  Finish pace   : ~{fmt_pace(pace_end)} /km  (last km)")
    print(f"  Total time    : {fmt_time(total_sec)}")
    print(f"  Cadence       : {START_CADENCE} → {END_CADENCE} SPM  (linear progression)")
    print(f"  Beat pattern  : 4/4 — beat 4 is higher-pitch accent  ({int(ACCENT_FREQ)} Hz)")
    print()

    # ── km milestone table ───────────────────────────────────────────────────
    print("── Cadence milestones ───────────────────────────────")
    print(f"  {'KM':>6}  {'Pace':>7}  {'Cadence':>9}")

    step    = max(1, int(distance) // 10)
    km_list = list(range(0, int(distance) + 1, step))
    if distance not in km_list:
        km_list.append(distance)

    for km in km_list:
        frac   = km / distance if distance else 0.0
        pace_k = pace_start + (pace_end - pace_start) * frac
        cad_k  = START_CADENCE + (END_CADENCE - START_CADENCE) * frac
        print(f"  {km:>6.1f}  {fmt_pace(pace_k):>7}  {cad_k:>7.0f} SPM")
    print()

    # ── generate audio ───────────────────────────────────────────────────────
    regular_click = make_click(REGULAR_FREQ)
    accent_click  = make_click(ACCENT_FREQ)

    beats = build_beat_schedule(total_sec)
    print(f"  Beats to render : {len(beats):,}")
    print()

    # ── output filenames ─────────────────────────────────────────────────────
    pace_tag = fmt_pace(avg_pace).replace(":", "m") + "s"
    dist_tag = (str(int(distance))
                if distance == int(distance)
                else str(distance).replace(".", "p"))
    stamp    = datetime.now().strftime("%Y%m%d_%H%M")
    base     = f"cadence_run_{dist_tag}km_{pace_tag}perkm_{stamp}"
    wav_path = base + ".wav"
    mp3_path = base + ".mp3"

    print("Generating audio…")
    write_wav_chunked(wav_path, beats, total_sec, regular_click, accent_click)

    wav_mb = os.path.getsize(wav_path) / 1_048_576
    print(f"  WAV : {wav_path}  ({wav_mb:.1f} MB)")

    print("Converting to MP3…")
    ok = convert_to_mp3(wav_path, mp3_path)
    if ok:
        os.remove(wav_path)
        mp3_mb = os.path.getsize(mp3_path) / 1_048_576
        print(f"  MP3 : {mp3_path}  ({mp3_mb:.1f} MB)")
    else:
        print(f"  MP3 conversion failed — WAV kept at: {wav_path}")
        print("  Install pydub + ffmpeg or add ffmpeg to PATH to enable MP3 output.")

    print()
    print("All done! Load the file onto your device and run strong.")
    print()


if __name__ == "__main__":
    main()
