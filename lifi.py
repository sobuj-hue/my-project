#!/usr/bin/env python3
"""
Visible Light Communication (Li-Fi) — text over modulated light
================================================================
Send a short text message by switching an LED on and off thousands of
times per second; recover the message at the receiver from the photo-
diode signal. The same software pipeline is used for both:
  - a pure-software simulation (no hardware needed),
  - a WAV-file round trip (generate audio, decode audio),
  - real hardware (PC sound card → audio amp → LED, photodiode amp → mic).

Modulation : OOK (on-off keying) of a 4 kHz audio carrier — also known
             as Amplitude-Shift Keying. The carrier is required because
             every PC sound card is AC-coupled and would block a plain
             on/off baseband signal.

Frame      : preamble │ sync │ length │ payload │ checksum
             16 bits    8 b    8 b      8·N b     8 b

Run modes:
    python lifi.py simulate "Hello, light!"
    python lifi.py wav-tx   "Hello, light!" --out tx.wav
    python lifi.py wav-rx   --in tx.wav
    python lifi.py audio-tx "Hello, light!"     # needs sounddevice + speaker
    python lifi.py audio-rx --seconds 5         # needs sounddevice + mic

Install once:
    pip install numpy matplotlib scipy sounddevice
"""

import argparse
import sys
import wave
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import butter, filtfilt, hilbert

# Optional: only required for real-time audio I/O
try:
    import sounddevice as sd
    HAS_SD = True
except (ImportError, OSError):
    HAS_SD = False

# ──────────────────────────────────────────────────────────
#  Protocol constants
# ──────────────────────────────────────────────────────────
SAMPLE_RATE   = 44_100        # Hz, standard sound-card rate
CARRIER_HZ    = 4_000         # carrier frequency
BIT_RATE      = 100           # bits per second  (10 ms per bit)
SAMPLES_PER_BIT = SAMPLE_RATE // BIT_RATE   # = 441

PREAMBLE = "1010101010101010"     # 16 bits — used to sync the clock
SYNC     = "01111110"             # 8-bit start-of-frame marker (0x7E)


# ══════════════════════════════════════════════════════════
#                    TRANSMITTER
# ══════════════════════════════════════════════════════════

def text_to_bits(text):
    """ASCII string → bit string of 8 bits per character (MSB first)."""
    return "".join(f"{b:08b}" for b in text.encode("utf-8"))


def bits_to_bytes(bits):
    """Bit string (length multiple of 8) → bytes object."""
    return bytes(int(bits[i:i+8], 2) for i in range(0, len(bits), 8))


def xor_checksum(data_bytes):
    cs = 0
    for b in data_bytes:
        cs ^= b
    return cs


def build_frame(text):
    """
    Wrap a message in our protocol:
        PREAMBLE | SYNC | LEN | PAYLOAD | CHECKSUM
    Returns a string of 0/1 characters.
    """
    payload_bytes = text.encode("utf-8")
    if len(payload_bytes) > 255:
        raise ValueError("Payload longer than 255 bytes is not supported.")
    length = len(payload_bytes)
    cs     = xor_checksum(payload_bytes)
    bits   = (PREAMBLE + SYNC
              + f"{length:08b}"
              + text_to_bits(text)
              + f"{cs:08b}")
    return bits


def modulate(bits, sample_rate=SAMPLE_RATE, carrier=CARRIER_HZ,
             samples_per_bit=SAMPLES_PER_BIT, amplitude=0.6):
    """
    Convert a bit string into an audio waveform using OOK on a sine carrier.
    Bit "1"  → carrier present     → cos(2π·f·t)
    Bit "0"  → carrier absent      → silence
    A short cosine ramp (1 ms) is added at every transition to suppress
    audible "clicks" caused by hard switching.
    """
    n = len(bits) * samples_per_bit
    t = np.arange(n) / sample_rate
    carrier_wave = amplitude * np.cos(2 * np.pi * carrier * t)

    # Build the on/off envelope and smooth it
    envelope = np.repeat(np.array([int(b) for b in bits], dtype=np.float32),
                         samples_per_bit)
    ramp_n = max(1, sample_rate // 1000)         # 1-millisecond ramp
    if ramp_n > 1:
        kernel = np.hanning(ramp_n)
        kernel /= kernel.sum()
        envelope = np.convolve(envelope, kernel, mode="same")

    return (envelope * carrier_wave).astype(np.float32)


# ══════════════════════════════════════════════════════════
#                    CHANNEL (simulation only)
# ══════════════════════════════════════════════════════════

def add_channel_effects(signal, snr_db=20, dc_offset=0.05, delay_samples=137):
    """
    Add realistic impairments: Gaussian noise, a small DC offset
    (sound cards block this anyway, but it tests the demodulator),
    and an unknown leading delay so the receiver has to find the frame.
    """
    rng = np.random.default_rng(0)
    sig_pwr   = np.mean(signal ** 2)
    noise_pwr = sig_pwr / (10 ** (snr_db / 10))
    noise     = rng.normal(0, np.sqrt(noise_pwr), signal.size + delay_samples)
    out       = noise.copy()
    out[delay_samples : delay_samples + signal.size] += signal
    out      += dc_offset
    return out.astype(np.float32)


# ══════════════════════════════════════════════════════════
#                    RECEIVER
# ══════════════════════════════════════════════════════════

def bandpass(x, low, high, fs=SAMPLE_RATE, order=4):
    """4th-order Butterworth bandpass filter, zero-phase via filtfilt."""
    nyq = 0.5 * fs
    b, a = butter(order, [low / nyq, high / nyq], btype="band")
    return filtfilt(b, a, x)


def envelope_detect(x):
    """Magnitude of the analytic signal — robust envelope of an AM/OOK signal."""
    return np.abs(hilbert(x))


def find_preamble(envelope, samples_per_bit=SAMPLES_PER_BIT):
    """
    Locate the start of the frame by cross-correlating the envelope with
    the ideal preamble waveform (16 bits of 10101010...). The peak of the
    correlation is the position where the preamble begins.
    """
    template = np.repeat(np.array([int(b) for b in PREAMBLE], dtype=np.float32),
                         samples_per_bit)
    template = template - template.mean()
    sig      = envelope - envelope.mean()

    corr = np.correlate(sig, template, mode="valid")
    return int(np.argmax(corr)), corr


def slice_bits(envelope, start_idx, n_bits, samples_per_bit=SAMPLES_PER_BIT):
    """
    Sample the envelope at the centre of every bit interval, then threshold
    using the midpoint between the highest and lowest sampled value.
    """
    centres = start_idx + (np.arange(n_bits) + 0.5) * samples_per_bit
    centres = centres.astype(int)
    centres = centres[centres < envelope.size]
    samples = envelope[centres]
    threshold = 0.5 * (samples.max() + samples.min())
    bits = "".join("1" if s > threshold else "0" for s in samples)
    return bits, samples, threshold, centres


def demodulate(signal, sample_rate=SAMPLE_RATE,
               carrier=CARRIER_HZ, samples_per_bit=SAMPLES_PER_BIT):
    """
    Full demod pipeline:
        bandpass → envelope → preamble correlation → bit slicing → frame parse.
    Returns the decoded text, plus a dict of intermediate signals so the
    caller can plot them.
    """
    # 1. Bandpass around the carrier to reject hum, room noise, music
    filt = bandpass(signal, carrier - 1500, carrier + 1500, fs=sample_rate)

    # 2. Envelope (AM demodulation)
    env = envelope_detect(filt)

    # smooth a little — averages out a few cycles of carrier residual
    win = max(3, samples_per_bit // 6)
    env = np.convolve(env, np.ones(win) / win, mode="same")

    # 3. Sync to the preamble
    start_idx, corr = find_preamble(env, samples_per_bit)

    # 4. Read the header (preamble already consumed → start at SYNC)
    header_offset = start_idx + len(PREAMBLE) * samples_per_bit
    header_bits, _, threshold, _ = slice_bits(
        env, header_offset, len(SYNC) + 8, samples_per_bit)

    sync_recv = header_bits[:len(SYNC)]
    if sync_recv != SYNC:
        # try ±1 bit slip
        for shift in (-1, 1):
            offset2 = header_offset + shift * samples_per_bit
            test, *_ = slice_bits(env, offset2, len(SYNC), samples_per_bit)
            if test == SYNC:
                header_offset = offset2
                header_bits, _, threshold, _ = slice_bits(
                    env, header_offset, len(SYNC) + 8, samples_per_bit)
                break
        else:
            return None, {"error": "sync word not found",
                          "filt": filt, "env": env, "corr": corr,
                          "start": start_idx}

    length = int(header_bits[len(SYNC):], 2)
    payload_offset = header_offset + (len(SYNC) + 8) * samples_per_bit
    payload_bits, samples_used, threshold, centres = slice_bits(
        env, payload_offset, length * 8 + 8, samples_per_bit)

    payload = bits_to_bytes(payload_bits[: length * 8])
    cs_recv = int(payload_bits[length * 8 : length * 8 + 8], 2)
    cs_calc = xor_checksum(payload)

    ok = cs_recv == cs_calc
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        text = payload.decode("utf-8", errors="replace")

    return text, {"filt": filt, "env": env, "corr": corr,
                  "start": start_idx, "centres": centres,
                  "samples": samples_used, "threshold": threshold,
                  "length": length, "ok": ok,
                  "cs_recv": cs_recv, "cs_calc": cs_calc}


# ══════════════════════════════════════════════════════════
#                    WAV file helpers
# ══════════════════════════════════════════════════════════

def write_wav(path, signal, fs=SAMPLE_RATE):
    pcm = np.clip(signal, -1, 1)
    pcm = (pcm * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(fs)
        w.writeframes(pcm.tobytes())


def read_wav(path):
    with wave.open(str(path), "rb") as w:
        fs = w.getframerate()
        n  = w.getnframes()
        data = w.readframes(n)
    pcm = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32767
    return pcm, fs


# ══════════════════════════════════════════════════════════
#                    Visualisation
# ══════════════════════════════════════════════════════════

def plot_pipeline(message_in, tx_signal, rx_signal, info, message_out,
                  save="lifi_pipeline.png"):
    fig, axes = plt.subplots(4, 1, figsize=(11, 8), sharex=False)
    fig.suptitle(f"Li-Fi transmission   |  in: '{message_in}'  →  "
                 f"out: '{message_out}'", fontsize=11, fontweight="bold")

    t_tx = np.arange(tx_signal.size) / SAMPLE_RATE * 1000   # ms
    t_rx = np.arange(rx_signal.size) / SAMPLE_RATE * 1000

    axes[0].plot(t_tx, tx_signal, lw=0.6, color="#2c5282")
    axes[0].set_title("1.  Transmitted waveform  (OOK on 4 kHz carrier)",
                      fontsize=9)
    axes[0].set_ylabel("amp")

    axes[1].plot(t_rx, rx_signal, lw=0.4, color="#718096")
    axes[1].set_title("2.  Received waveform with noise + delay",
                      fontsize=9)
    axes[1].set_ylabel("amp")

    axes[2].plot(t_rx, info["env"], color="#2f855a", lw=0.7)
    if "centres" in info:
        c_ms = info["centres"] / SAMPLE_RATE * 1000
        axes[2].plot(c_ms, info["samples"], "o", ms=3, color="crimson",
                     label="bit-centre samples")
        axes[2].axhline(info["threshold"], color="black", ls=":",
                        lw=0.7, label="threshold")
        axes[2].legend(fontsize=8)
    axes[2].set_title("3.  Envelope after bandpass + Hilbert demod",
                      fontsize=9)
    axes[2].set_ylabel("env")

    axes[3].plot(info["corr"], color="#b7791f", lw=0.7)
    axes[3].axvline(info["start"], color="crimson", ls="--", lw=0.8,
                    label=f"frame start (sample {info['start']})")
    axes[3].set_title("4.  Preamble correlation (peak = sync point)",
                      fontsize=9)
    axes[3].set_xlabel("sample index")
    axes[3].set_ylabel("corr")
    axes[3].legend(fontsize=8)

    for a in axes[:3]:
        a.set_xlabel("time (ms)")
        a.grid(alpha=0.25, ls="--")
    axes[3].grid(alpha=0.25, ls="--")

    plt.tight_layout(rect=[0, 0, 1, 0.97])
    plt.savefig(save, dpi=180, bbox_inches="tight")
    print(f"Saved plot → {save}")
    return fig


# ══════════════════════════════════════════════════════════
#                    Sub-commands
# ══════════════════════════════════════════════════════════

def cmd_simulate(args):
    print(f"[TX] message  : {args.message!r}")
    bits = build_frame(args.message)
    print(f"[TX] frame    : {len(bits)} bits = {bits}")

    tx = modulate(bits)
    rx = add_channel_effects(tx, snr_db=args.snr)

    print(f"[CH] SNR      : {args.snr} dB  (added Gaussian noise + delay)")
    print(f"[RX] decoding…")

    text, info = demodulate(rx)
    if text is None:
        print(f"[RX] FAILED — {info.get('error', 'unknown error')}")
        sys.exit(1)
    print(f"[RX] length   : {info['length']} bytes")
    print(f"[RX] checksum : recv=0x{info['cs_recv']:02x}  "
          f"calc=0x{info['cs_calc']:02x}  "
          f"{'OK' if info['ok'] else 'MISMATCH'}")
    print(f"[RX] message  : {text!r}")

    if not args.no_plot:
        plot_pipeline(args.message, tx, rx, info, text, save=args.plot)
        if not args.no_show:
            plt.show()


def cmd_wav_tx(args):
    bits = build_frame(args.message)
    tx   = modulate(bits)
    # 0.2 s of silence before & after — gives the receiver time to start
    pad  = np.zeros(int(SAMPLE_RATE * 0.2), dtype=np.float32)
    write_wav(args.out, np.concatenate([pad, tx, pad]))
    print(f"Wrote {args.out}  ({(tx.size + 2*pad.size)/SAMPLE_RATE:.2f} s, "
          f"{len(args.message)} chars)")


def cmd_wav_rx(args):
    pcm, fs = read_wav(args.inp)
    if fs != SAMPLE_RATE:
        sys.exit(f"WAV sample rate {fs} ≠ expected {SAMPLE_RATE}")
    text, info = demodulate(pcm)
    if text is None:
        print(f"FAILED — {info.get('error')}")
        sys.exit(1)
    print(f"Decoded {info['length']} bytes  "
          f"checksum {'OK' if info['ok'] else 'BAD'}:")
    print(f"  → {text!r}")


def cmd_audio_tx(args):
    if not HAS_SD:
        sys.exit("sounddevice not available — install with `pip install sounddevice`")
    bits = build_frame(args.message)
    tx   = modulate(bits)
    pad  = np.zeros(int(SAMPLE_RATE * 0.3), dtype=np.float32)
    waveform = np.concatenate([pad, tx, pad])
    print(f"Playing {len(args.message)}-char message "
          f"({waveform.size / SAMPLE_RATE:.2f} s)…")
    sd.play(waveform, SAMPLE_RATE)
    sd.wait()
    print("done.")


def cmd_audio_rx(args):
    if not HAS_SD:
        sys.exit("sounddevice not available — install with `pip install sounddevice`")
    print(f"Listening for {args.seconds} s …")
    rec = sd.rec(int(SAMPLE_RATE * args.seconds),
                 samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    pcm = rec.flatten()
    text, info = demodulate(pcm)
    if text is None:
        print(f"FAILED — {info.get('error')}")
        sys.exit(1)
    print(f"Decoded {info['length']} bytes  "
          f"checksum {'OK' if info['ok'] else 'BAD'}:")
    print(f"  → {text!r}")


# ══════════════════════════════════════════════════════════
#                    CLI
# ══════════════════════════════════════════════════════════

def main():
    p = argparse.ArgumentParser(description=__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("simulate", help="full TX+channel+RX in software, with plots")
    s.add_argument("message")
    s.add_argument("--snr",     type=float, default=20.0,
                   help="signal-to-noise ratio in dB (default 20)")
    s.add_argument("--plot",    default="lifi_pipeline.png")
    s.add_argument("--no-plot", action="store_true")
    s.add_argument("--no-show", action="store_true")
    s.set_defaults(fn=cmd_simulate)

    s = sub.add_parser("wav-tx", help="encode message to a WAV file")
    s.add_argument("message")
    s.add_argument("--out", default="lifi_tx.wav")
    s.set_defaults(fn=cmd_wav_tx)

    s = sub.add_parser("wav-rx", help="decode message from a WAV file")
    s.add_argument("--in", dest="inp", required=True)
    s.set_defaults(fn=cmd_wav_rx)

    s = sub.add_parser("audio-tx", help="play modulated message through speakers")
    s.add_argument("message")
    s.set_defaults(fn=cmd_audio_tx)

    s = sub.add_parser("audio-rx", help="record from microphone and decode")
    s.add_argument("--seconds", type=float, default=5.0)
    s.set_defaults(fn=cmd_audio_rx)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
