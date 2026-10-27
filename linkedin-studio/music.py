"""Royalty-free backing track, synthesised from scratch with numpy.

make_track(seconds, path, bpm=112, seed=0) writes a 48 kHz stereo 16-bit WAV:
soft four-on-the-floor kick, off-beat hats, claps on 2 and 4, a bass line and
a warm pad over Am F C G, with a quiet arpeggio after the intro. The level is
kept low (about -18 dBFS RMS) so it sits under a talking-head-free video.
Nothing here is sampled, so there are no licensing questions.
"""
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, sosfilt

SR = 48000
PROG = [  # (bass root, pad voicing) in MIDI notes, one chord per bar
    (45, (57, 60, 64)),  # Am
    (41, (57, 60, 65)),  # F
    (48, (55, 60, 64)),  # C
    (43, (55, 59, 62)),  # G
]


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def saw(f, t, ph=0.0):
    x = (f * t + ph) % 1.0
    return 2 * x - 1


def env_ad(n, a, d):
    """Attack/decay envelope over n samples (a, d in seconds)."""
    t = np.arange(n) / SR
    e = np.minimum(1.0, t / max(a, 1e-4)) * np.exp(-np.maximum(0, t - a) / max(d, 1e-4))
    return e


def lp(x, fc, order=2):
    sos = butter(order, fc, 'low', fs=SR, output='sos')
    return sosfilt(sos, x)


def hp(x, fc, order=2):
    sos = butter(order, fc, 'high', fs=SR, output='sos')
    return sosfilt(sos, x)


def bp(x, lo, hi, order=2):
    sos = butter(order, [lo, hi], 'band', fs=SR, output='sos')
    return sosfilt(sos, x)


def add(buf, start, sig, gain=1.0):
    i = int(start * SR)
    if i >= len(buf):
        return
    j = min(len(buf), i + len(sig))
    buf[i:j] += sig[: j - i] * gain


def make_track(seconds, path, bpm=112, seed=0):
    rng = np.random.default_rng(seed)
    n = int((seconds + 0.5) * SR)
    beat = 60.0 / bpm
    bar = 4 * beat
    L = np.zeros(n)
    R = np.zeros(n)
    drums = np.zeros(n)
    kick_times = []

    # ---- drums
    kt = np.arange(int(0.42 * SR)) / SR
    kick = np.sin(2 * np.pi * np.cumsum(48 + 75 * np.exp(-kt * 32)) / SR) * np.exp(-kt * 8.5)
    kick += 0.25 * np.sin(2 * np.pi * 95 * kt) * np.exp(-kt * 40)
    hat_n = int(0.05 * SR)
    clap_n = int(0.2 * SR)
    nbars = int(np.ceil(seconds / bar)) + 1
    for b in range(nbars):
        for q in range(4):
            t0 = b * bar + q * beat
            if t0 > seconds:
                break
            if b >= 2:  # kick enters after a two-bar intro
                add(drums, t0, kick, 0.9)
                kick_times.append(t0)
            # off-beat hat
            h = hp(rng.standard_normal(hat_n), 7000) * env_ad(hat_n, 0.001, 0.025)
            add(drums, t0 + beat / 2, h, 0.22 if b >= 1 else 0.12)
            if b >= 4:  # quiet 16th hats later on
                h2 = hp(rng.standard_normal(hat_n), 9000) * env_ad(hat_n, 0.001, 0.012)
                add(drums, t0 + beat / 4, h2, 0.07)
                add(drums, t0 + 3 * beat / 4, h2, 0.07)
            if b >= 2 and q in (1, 3):  # clap on 2 and 4
                c = bp(rng.standard_normal(clap_n), 900, 5000) * env_ad(clap_n, 0.002, 0.07)
                tt = np.arange(clap_n) / SR
                c += 0.3 * np.sin(2 * np.pi * 190 * tt) * np.exp(-tt * 30)
                add(drums, t0, c, 0.32)

    # ---- sidechain envelope from the kick
    duck = np.ones(n)
    for t0 in kick_times:
        i = int(t0 * SR)
        m = min(n - i, int(0.35 * SR))
        tt = np.arange(m) / SR
        duck[i:i + m] = np.minimum(duck[i:i + m], 1 - 0.55 * np.exp(-tt * 9))

    # ---- pad, bass, arpeggio
    for b in range(nbars):
        t0 = b * bar
        if t0 > seconds:
            break
        root, voicing = PROG[b % 4]
        m = int(bar * SR) + int(0.3 * SR)
        tt = np.arange(m) / SR
        pad_l = np.zeros(m)
        pad_r = np.zeros(m)
        for k, note in enumerate(voicing):
            f = hz(note)
            pad_l += saw(f * 2 ** (-6 / 1200), tt, 0.1 * k) + 0.6 * saw(f * 2 ** (5 / 1200), tt, 0.37)
            pad_r += saw(f * 2 ** (6 / 1200), tt, 0.2 * k) + 0.6 * saw(f * 2 ** (-4 / 1200), tt, 0.71)
        e = np.minimum(1, tt / 0.35) * np.clip((bar + 0.3 - tt) / 0.3, 0, 1)
        pad_l = lp(pad_l * e, 1500)
        pad_r = lp(pad_r * e, 1500)
        add(L, t0, pad_l, 0.05)
        add(R, t0, pad_r, 0.05)
        if b >= 1:  # bass in eighths
            for e8 in range(8):
                bt = t0 + e8 * beat / 2
                bn = int(beat / 2 * SR)
                bt_ = np.arange(bn) / SR
                f = hz(root - 12 if e8 % 2 == 0 else root)
                s = np.sin(2 * np.pi * f * bt_) + 0.35 * np.sin(2 * np.pi * 2 * f * bt_)
                s = np.tanh(1.6 * s) * env_ad(bn, 0.004, 0.16)
                add(L, bt, s, 0.20)
                add(R, bt, s, 0.20)
        if b >= 4:  # quiet arpeggio
            pattern = [0, 1, 2, 1, 2, 0, 1, 2]
            for s16 in range(8):
                at = t0 + s16 * beat / 2
                note = voicing[pattern[s16]] + 12
                an = int(0.3 * SR)
                a_t = np.arange(an) / SR
                tri = 2 * np.abs(saw(hz(note), a_t)) - 1
                s = lp(tri * env_ad(an, 0.003, 0.11), 3500)
                add(L, at, s, 0.06)
                add(R, at, s, 0.035)

    L = L * duck + drums
    R = R * duck + drums * 0.92
    mix = np.stack([L, R], axis=1)
    mix = hp(mix.T, 30).T
    mix = np.tanh(mix * 1.1) / 1.1
    rms = np.sqrt(np.mean(mix ** 2)) + 1e-9
    mix *= (10 ** (-18 / 20)) / rms
    peak = np.max(np.abs(mix))
    if peak > 0.89:
        mix *= 0.89 / peak
    # fade in 0.6 s, fade out 2 s, trim to length
    total = int(seconds * SR)
    mix = mix[:total]
    fi = int(0.6 * SR)
    fo = int(min(2.0, seconds / 4) * SR)
    mix[:fi] *= np.linspace(0, 1, fi)[:, None]
    mix[-fo:] *= np.linspace(1, 0, fo)[:, None]
    wavfile.write(path, SR, (mix * 32767).astype(np.int16))
    return path


if __name__ == '__main__':
    import sys
    make_track(float(sys.argv[1]) if len(sys.argv) > 1 else 30, sys.argv[2] if len(sys.argv) > 2 else 'music.wav')
    print('ok')
