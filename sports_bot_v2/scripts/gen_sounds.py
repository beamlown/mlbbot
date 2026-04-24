"""Generate tiny 8-bit-style SFX as CC0 placeholders. Run once."""
import math
import struct
import wave
from pathlib import Path

RATE = 22050
OUT = Path(__file__).resolve().parent.parent / "dugout_dash" / "static" / "sounds"
OUT.mkdir(parents=True, exist_ok=True)


def square(freq: float, dur: float, vol: float = 0.4) -> bytes:
    n = int(RATE * dur)
    frames = bytearray()
    for i in range(n):
        t = i / RATE
        v = vol if math.sin(2 * math.pi * freq * t) > 0 else -vol
        env = max(0.0, 1.0 - i / n)
        sample = int(v * env * 32767)
        frames += struct.pack("<h", sample)
    return bytes(frames)


def write(name: str, data: bytes) -> None:
    with wave.open(str(OUT / name), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(RATE)
        w.writeframes(data)


def main():
    write("base_hit.wav", square(523, 0.08) + square(659, 0.08) + square(784, 0.12))
    write("strikeout.wav", square(440, 0.10) + square(220, 0.18))
    write("walkoff.wav", square(523, 0.08) + square(659, 0.08) + square(784, 0.08) + square(1046, 0.20))
    write("foul.wav", square(200, 0.12))
    print("generated", [p.name for p in OUT.glob("*.wav")])


if __name__ == "__main__":
    main()
