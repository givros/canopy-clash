"""Make the mono spatial edit from the project's Epic First Person Template sound."""
import argparse
from pathlib import Path
import numpy as np
from scipy.io.wavfile import read, write


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("template_wav", type=Path, help="WAV exported from /Game/Weapons/GrenadeLauncher/Audio/FirstPersonTemplateWeaponFire02")
    args = parser.parse_args()
    rate, audio = read(args.template_wav)
    mono = audio.astype(float).mean(axis=1)
    mono *= .93 * 32767 / np.abs(mono).max()
    write(Path(__file__).with_name("S_CanopyReport.wav"), rate, mono.astype(np.int16))
