"""Generate the original Canopy footfall foley, entirely from seeded synthesis."""
from pathlib import Path
import numpy as np
from scipy.io.wavfile import write
from scipy.signal import butter, sosfilt


RATE = 48_000
OUT = Path(__file__).resolve().parent


def contact(forest, variation):
    rng = np.random.default_rng(16801 + variation + 100 * forest)
    duration = (0.29 if forest else 0.245) + variation * 0.009
    time = np.arange(round(duration * RATE)) / RATE

    def band(lo, hi):
        sos = butter(2, [lo, hi], btype="bandpass", fs=RATE, output="sos")
        noise = sosfilt(sos, rng.normal(size=time.size))
        return noise / np.std(noise)

    def envelope(start, rise, decay):
        t = np.maximum(0, time - start)
        return (1 - np.exp(-t / rise)) * np.exp(-t / decay)

    heel = envelope(.006, .007 if forest else .0025, .031 if forest else .022)
    toe = envelope(.043 + .006 * variation, .008, .033)
    result = (heel + 0.44 * toe) * band(60, 250 if forest else 390)
    result += (heel * .30 + toe * .27) * band(260, 1000 if forest else 1900)
    drag = envelope(.058 + .003 * variation, .014, .038)
    result += drag * band(600, 2650 if forest else 1480) * (.50 if forest else .23)
    # Small, irregular granules: dry leaf edges over soft earth, or grit under the sole.
    for start in sorted(rng.uniform(.010, .14, 13 if forest else 5)):
        grain = envelope(start, rng.uniform(.0005, .0015), rng.uniform(.0018, .006))
        result += grain * band(1000, 5200 if forest else 3100) * rng.uniform(.09, .23)
    result *= np.clip((duration - time) / .034, 0, 1)
    result *= .76 / np.abs(result).max()
    return np.asarray(result * 32767, dtype=np.int16)


if __name__ == "__main__":
    for forest, label in ((False, "Stone"), (True, "Forest")):
        for index in range(3):
            write(OUT / f"S_Step{label}{index + 1:02d}.wav", RATE, contact(forest, index))
