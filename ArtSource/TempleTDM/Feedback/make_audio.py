"""Generate the arena carbine's short mechanical cycle and its two-tone HUD confirmation."""
from array import array
from math import exp, pi, sin
from pathlib import Path
from random import Random
import wave

ROOT = Path(__file__).resolve().parent
RATE = 48000


def save(name, signal):
    peak = max(abs(value) for value in signal) or 1.0
    pcm = array("h", (round(value * 26000 / peak) for value in signal))
    with wave.open(str(ROOT / (name + ".wav")), "wb") as output:
        output.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
        output.writeframes(pcm.tobytes())


def cycle():
    rng = Random(419)
    signal = [0.0] * int(RATE * 1.91)
    for onset, pitch, decay, level in [(0.04, 610, .039, .77), (.19, 240, .072, .55),
                                      (.78, 350, .055, .62), (1.12, 405, .067, .91),
                                      (1.56, 285, .095, 1.0), (1.67, 710, .045, .55)]:
        filtered = 0
        for index in range(int(decay * 3.5 * RATE)):
            t = index / RATE
            filtered = .68 * filtered + .32 * rng.uniform(-1, 1)
            shape = min(1, t / .0016) * exp(-t / decay)
            strike = sin(2*pi*(pitch - 145*t)*t)*.33 + sin(2*pi*3.27*pitch*t)*.12
            signal[round(onset * RATE) + index] += level * shape * (filtered + strike)
    save("S_CarbineCycle", signal)


def confirmation():
    signal = []
    for index in range(int(RATE * .104)):
        t = index / RATE
        first = min(1, t / .0015) * exp(-t / .020) * sin(2*pi*1175*t)
        tau = max(0., t - .019)
        second = min(1, tau / .002) * exp(-tau / .020) * sin(2*pi*1690*tau)
        signal.append(first * .55 + second * .75)
    save("S_TagConfirm", signal)


if __name__ == "__main__":
    cycle()
    confirmation()
