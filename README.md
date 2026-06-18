# 🏃 Runner Cadence Metronome

Generate a custom MP3 audio guide that locks you into a progressive cadence throughout your race — from first step to finish line.

---

## What It Does

You enter your average pace and race distance. The script calculates a complete audio metronome that:

- **Starts slow, finishes fast** — pacing ramps from ~10% slower than your average down to ~10% faster, matching a classic negative-split race strategy
- **Keeps your cadence in the optimal zone** — linearly progresses from **165 SPM** at the gun to **180 SPM** at the finish
- **Uses a 4/4 beat pattern** — beats 1, 2, 3 are regular clicks; **beat 4 is a higher-pitched accent** (one octave up) to mark each measure
- **Outputs a ready-to-use MP3** you can load on your phone or GPS watch

---

## How Cadence & Pace Work Together

| Race position | Pace (example at 5:30 avg) | Cadence |
|---|---|---|
| Start | ~6:03 /km | 165 SPM |
| Midpoint | ~5:30 /km | 172–173 SPM |
| Finish | ~4:57 /km | 180 SPM |

Higher cadence = shorter, quicker steps = less impact force and a more efficient stride at race speed.

---

## Beat Pattern

```
Beat:    1       2       3       4 ↑
         tick    tick    tick    TICK  (higher pitch)
         tick    tick    tick    TICK
         ...
```

The 4th-beat accent gives you an easy anchor point — every time you hear the high note, you know you're completing a 4-step cycle.

---

## Requirements

**Python 3.7+**

| Package | Role | Install |
|---|---|---|
| `numpy` | Audio generation | `pip install numpy` |
| `pydub` | MP3 export | `pip install pydub` |
| `ffmpeg` | MP3 encoding backend | see below |

> Without `pydub`/`ffmpeg` the script falls back to **WAV output** — everything still works, the file is just larger.

### Installing ffmpeg

| Platform | Command |
|---|---|
| macOS | `brew install ffmpeg` |
| Ubuntu / Debian | `sudo apt install ffmpeg` |
| Windows | Download from [ffmpeg.org](https://ffmpeg.org/download.html), add to PATH |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/dxxmngo/runner-cadence-calculator.git
cd runner-cadence-calculator

# 2. Install dependencies
pip install numpy pydub

# 3. Run
python3 cadence_metronome.py
```

The script will prompt you for two values:

```
Average race pace (MM:SS /km, e.g. 5:30): 5:30
Total race distance in km (e.g. 10 or 21.1): 10
```

---

## Example Session

```
╔══════════════════════════════════════════╗
║   Running Cadence Metronome Generator    ║
╚══════════════════════════════════════════╝

Average race pace (MM:SS /km, e.g. 5:30): 5:30
Total race distance in km (e.g. 10 or 21.1): 10

── Race summary ─────────────────────────────────────
  Distance      : 10 km
  Average pace  : 5:30 /km
  Start pace    : ~6:03 /km  (first km)
  Finish pace   : ~4:57 /km  (last km)
  Total time    : 55m 00s
  Cadence       : 165 → 180 SPM  (linear progression)
  Beat pattern  : 4/4 — beat 4 is higher-pitch accent  (1760 Hz)

── Cadence milestones ───────────────────────────────
      KM     Pace    Cadence
     0.0    6:03     165 SPM
     1.0    5:57     167 SPM
     2.0    5:51     168 SPM
     ...
    10.0    4:57     180 SPM

  Beats to render : 9,468

Generating audio…
  [████████████████████████████████████████] 100.0%
  WAV : cadence_run_10km_5m30sperkm_20260613_1015.wav  (138.3 MB)
Converting to MP3…
  MP3 : cadence_run_10km_5m30sperkm_20260613_1015.mp3  (5.1 MB)

All done! Load the file onto your device and run strong.
```

---

## Output File

The MP3 filename encodes all the key details so you always know what's in it:

```
cadence_run_10km_5m30sperkm_20260613_1015.mp3
             ↑     ↑              ↑
          distance pace      date + time
```

Typical file sizes at 128 kbps:

| Race | Example pace | File size |
|---|---|---|
| 5 km | 5:30 /km | ~2.5 MB |
| 10 km | 5:30 /km | ~5 MB |
| Half marathon | 5:30 /km | ~11 MB |
| Full marathon | 5:30 /km | ~22 MB |

---

## Technical Details

| Parameter | Value |
|---|---|
| Sample rate | 22,050 Hz |
| Bit depth | 16-bit mono |
| Regular beat | 880 Hz (A5) — sine wave + exponential decay |
| Accent beat (4) | 1,760 Hz (A6) — same shape, one octave up |
| Click duration | 45 ms |
| MP3 bitrate | 128 kbps |
| RAM usage | Capped — audio is rendered in 60-second chunks |

---

## Tips for Race Day

- **Load it before the race** — no internet needed once it's on your device
- **Use earbuds with ambient sound mode** so you can still hear your surroundings
- **Don't fight the beat** — if you feel your stride drifting, consciously sync one foot to each click for a few seconds
- **The high note on beat 4 is your reset cue** — use it to check your form every measure

---

## License

MIT
