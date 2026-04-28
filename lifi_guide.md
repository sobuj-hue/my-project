# Li-Fi (Visible Light Communication) — Complete Guide

A beginner-friendly walkthrough of a working Li-Fi system: send a text
message by blinking an LED thousands of times per second, and recover
it from a photodiode at the other end. The same Python code drives
three escalating versions of the project:

1. **Pure software simulation** — runs on any computer, shows the full
   transmit-channel-receive pipeline with plots. No hardware needed.
2. **WAV-file round trip** — generate a `.wav` file containing the
   modulated signal; decode it later. Useful as a self-test.
3. **Real hardware** — laptop sound card → audio amplifier → LED → air →
   photodiode → mic input → laptop. Send messages across a room over
   a beam of light.

---

## 1. What is Li-Fi?

Li-Fi (Light Fidelity) is wireless data transmission using visible
light instead of radio waves. The concept is dead simple: switch an
LED on and off very quickly to encode bits. A photodiode at the
receiver converts the changing light back into an electrical signal,
which is decoded into the original message.

Real commercial Li-Fi systems run at hundreds of Mbps. Ours runs at
**100 bits per second** — slow, but reliable, audible-band, and works
through a $5 sound card.

---

## 2. Why use a 4 kHz audio carrier instead of just on/off?

If you simply switched the LED on for "1" and off for "0" at 100 Hz,
the receiver's sound card would never see those bits — every audio
input is **AC-coupled** (a series capacitor blocks any DC component
and any signal below ~20 Hz). Slow on/off transitions look like DC
to the sound card and disappear.

The fix is to put a **carrier** in the middle of the audio band.
We pick 4 000 Hz. The LED still goes on/off at 100 Hz, but while it
is "on" we drive it with a 4 kHz sine wave; while it is "off" we
drive it with zero volts. The carrier passes through the sound card's
AC coupling untouched. This scheme is called **OOK** (on-off keying)
or **ASK** (amplitude shift keying).

```
bit stream:    1   0   1   1   0   1   0
                _      _   _      _
LED current:  / \    / \ / \    / \      ← 4 kHz sine bursts
              \_/    \_/ \_/    \_/
```

---

## 3. The frame format

Just sending raw bits doesn't work — the receiver has to know where the
message starts, how long it is, and whether it arrived intact. We wrap
the data in a small protocol:

```
┌──────────┬──────┬─────┬───────────┬──────────┐
│ Preamble │ Sync │ Len │  Payload  │ Checksum │
│ 16 bits  │ 8 b  │ 8 b │  8·N b    │ 8 bits   │
└──────────┴──────┴─────┴───────────┴──────────┘
  10101010   0x7E   N    "Hello..."   XOR
  10101010
```

| field    | purpose                                                           |
| -------- | ----------------------------------------------------------------- |
| Preamble | pure square wave for clock recovery (the receiver locks onto it)  |
| Sync     | 0x7E — a known marker so we know where the data begins            |
| Length   | how many payload bytes follow (1–255)                             |
| Payload  | the ASCII / UTF-8 message itself                                  |
| Checksum | XOR of all payload bytes — catches single-bit errors              |

This is essentially the same idea as Ethernet, USB, or Wi-Fi frames,
just smaller and slower.

---

## 4. Install and run

```bash
pip install numpy matplotlib scipy sounddevice
```

`sounddevice` is only needed for the real-audio modes. The simulation
and WAV modes work without it.

### a) Pure simulation (try this first)

```bash
python lifi.py simulate "Hello, light!"
```

You'll see something like:

```
[TX] message  : 'Hello, light!'
[TX] frame    : 144 bits = 101010101010101001111110...
[CH] SNR      : 20.0 dB
[RX] decoding…
[RX] length   : 13 bytes
[RX] checksum : recv=0x11  calc=0x11  OK
[RX] message  : 'Hello, light!'
Saved plot → lifi_pipeline.png
```

The plot has four panels showing every stage: the modulated
transmitter waveform, the noisy received signal, the demodulated
envelope with bit-decision points, and the preamble correlation peak.

Try lowering the SNR to see the system's noise tolerance:

```bash
python lifi.py simulate "Hello!" --snr 5
```

### b) WAV round trip

```bash
python lifi.py wav-tx "Test 123" --out test.wav
python lifi.py wav-rx --in  test.wav
```

You can play `test.wav` through your speakers and record it with your
phone to verify end-to-end audio works. (Don't expect it to decode
when recorded by a phone — sound-card-to-sound-card is best.)

### c) Real hardware (optional)

In one terminal, listening on the microphone input:

```bash
python lifi.py audio-rx --seconds 6
```

In another terminal, transmitting through the speakers (or, with
hardware below, the LED):

```bash
python lifi.py audio-tx "Hello over light!"
```

---

## 5. Hardware build (for the optional real mode)

You can do the entire project without hardware. If you want to actually
shoot data across a room with light, here is the minimum circuit.

### 5.1 Transmitter

The PC's audio output drives an LED through a small NPN transistor:

```
  +5 V
   │
   ▼
  ┌─┐ R1 = 220 Ω           LED (white, high-brightness)
  │ │                      ┌─┐
  │ │                      │ │
  └┬┘                      └┬┘
   │                        │
   ├────────────────────────┤
   │       ┌─── collector
   │       │
audio out ── R2 (1 kΩ) ── base
                         │
                        emitter
                         │
                        GND
                                  R2 limits base current.
                                  R1 limits LED current.
                                  Use any small NPN: 2N3904, BC547, S8050…
```

The audio output of your PC's headphone jack is enough to drive the
base of the transistor. Don't drive the LED directly from the audio
jack — there isn't enough current.

### 5.2 Receiver

A photodiode (BPW34 is the standard cheap choice) feeds a single
op-amp transimpedance amplifier:

```
        +V
         │
  photodiode (reverse-biased to ground via 1 MΩ)
         │
         ├───────┐                +V
         │       │                 │
         │       │             ┌───┴───┐
         │       └────────────│− OP   │── audio in (mic)
         │                    │       │
         └────────── Rf=1MΩ ──│+      │── GND through 10 kΩ
                              └───────┘
```

Any rail-to-rail single-supply op-amp works (e.g. MCP6002, LM358 in a
pinch). You want bandwidth of at least 20 kHz, gain of about 10⁶ V/A.

### 5.3 Coupling to the PC

Plug the op-amp output into the **microphone input** of the laptop
through a 1 µF series capacitor (the laptop input is AC-coupled and
the cap protects against DC). Do not plug it into the line-in if your
laptop only has a TRRS combo jack — that one expects an electret-mic
DC bias and may need a different connection.

---

## 6. The code, explained section by section

The file `lifi.py` has six clear blocks. Read them in this order.

### 6.1  `text_to_bits` and `build_frame` — encoding

```python
def text_to_bits(text):
    return "".join(f"{b:08b}" for b in text.encode("utf-8"))
```

`text.encode("utf-8")` converts the string to bytes. The
`f"{b:08b}"` format spec turns each byte into eight binary digits
(padded with zeros on the left). The whole thing is joined into one
long bit string.

`build_frame` then prepends the preamble + sync, the length, and
appends an XOR checksum. The function returns a string like
`"1010...01111110...11010100"` ready to be modulated.

### 6.2  `modulate` — bits → audio waveform

```python
envelope     = np.repeat([int(b) for b in bits], samples_per_bit)
carrier_wave = amplitude * np.cos(2π · f · t)
output       = envelope * carrier_wave
```

The trick is the **multiplication**. The envelope is a square pulse
that's 1 during a "1" bit and 0 during a "0" bit. Multiplying it by
the carrier turns each "1" bit into a 4 kHz tone and each "0" bit
into silence. That is the textbook definition of OOK.

The hard switch from 0 → 1 makes audible "clicks" and creates broad
sideband noise that swamps the bandpass filter. To stop that, the
envelope is convolved with a 1-millisecond Hanning window — gentle
ramps at every transition.

### 6.3  `add_channel_effects` — simulation only

Adds Gaussian noise at a chosen SNR, a small DC offset, and an
unknown leading delay so the receiver actually has to find the
frame instead of assuming it starts at sample zero.

### 6.4  `bandpass` and `envelope_detect` — receiver front end

```python
b, a = butter(order=4, [low/nyq, high/nyq], btype="band")
filt = filtfilt(b, a, x)
```

A 4th-order Butterworth bandpass keeps everything in **[2.5 kHz,
5.5 kHz]** and throws away the rest. This rejects power-line hum
(50/60 Hz), low-frequency room noise, and any other audio signal that
isn't our carrier. `filtfilt` runs the filter forward then backward
to give zero phase distortion.

```python
env = np.abs(hilbert(x))
```

`hilbert(x)` returns the *analytic signal* — a complex-valued version
of `x` whose magnitude is the **envelope** (the slowly-varying outline
that wraps around the carrier). For OOK-modulated signals this
recovers the original on/off pattern in one line. Mathematically
equivalent to "rectify + lowpass", but cleaner.

### 6.5  `find_preamble` — clock recovery

The receiver doesn't know when the frame starts. The trick is to
generate the *expected* envelope of the preamble (a 16-bit square
wave) and slide it along the received envelope, multiplying point-by-
point and summing. At every position where the two patterns line up,
the sum is large; everywhere else, the sum is small. The peak of
this **cross-correlation** is the start of the frame. Two lines:

```python
template = np.repeat([1,0,1,0, …], samples_per_bit)   # 16-bit alternating
corr     = np.correlate(envelope - mean, template - mean, mode="valid")
start    = np.argmax(corr)
```

This is how every digital radio in existence — Wi-Fi, GPS, your car
keyfob — synchronises to a frame.

### 6.6  `slice_bits` — sampling decisions

Once we know where the frame begins, we sample the envelope at the
**centre** of every bit interval (most stable point of the curve) and
decide each bit by comparing to the midpoint between the brightest
and darkest sample. This is called **bit slicing**.

Sampling at the centre, not the edge, is critical: the gentle
on/off ramps mean the value at the edges is somewhere between 0 and 1
and would give random bits.

---

## 7. The output plot

After `simulate` finishes, `lifi_pipeline.png` shows four time-domain
panels:

1. **Transmitted waveform** — the actual audio that would drive the
   LED. You can clearly see bursts of 4 kHz carrier (a "1") separated
   by silence (a "0").
2. **Received waveform** — the same with noise added and a leading
   delay. Looks much messier.
3. **Demodulated envelope** — after bandpass + Hilbert. Clean square-
   wave-like signal. Red dots mark where the receiver decided to
   sample each bit; the dotted black line is the threshold.
4. **Preamble correlation** — slides the known preamble across the
   envelope. The huge peak shows where the frame starts.

Looking at these four panels in order is the best way to understand
what's happening at every stage.

---

## 8. Things to try / explore

* **Reduce SNR** until decoding fails — find the minimum SNR your
  protocol survives. Add an FEC code (Hamming(7,4) is famous and easy)
  and watch the threshold drop by ~3 dB.
* **Increase the bit rate** — change `BIT_RATE = 100` to `200` or
  `400`. Find the rate at which decoding starts to fail with your
  particular sound card / LED / photodiode.
* **Change the modulation** — try Manchester encoding (each bit becomes
  two half-bits with opposite values; provides perfect DC balance and
  built-in clock recovery).
* **Real LED** — build the transmitter circuit and shine it on the
  photodiode. Measure the bit error rate vs. distance. Plot it.
* **Multiple channels** — use red, green, blue LEDs on different
  carriers (e.g. 2, 4, 6 kHz) to triple the data rate. This is called
  **WDM** (wavelength-division multiplexing) and is exactly what
  fiber-optic backbones do.

---

## 9. Troubleshooting

| Symptom                                  | Likely cause / fix                                           |
| ---------------------------------------- | ------------------------------------------------------------ |
| `sync word not found` in simulate mode   | SNR too low → raise `--snr` to 15–20 dB                      |
| `audio-tx` / `audio-rx` errors           | sounddevice can't open default audio device → list with `python -m sounddevice` and pass the right index |
| Real-hardware decoding fails             | usually photodiode amplifier saturates or is too dim → adjust gain, room lighting, or LED current |
| Garbled text but checksum reports OK     | impossible — checksum being OK guarantees byte integrity. If you see this, the script's checksum logic is being bypassed; check you're running the latest `lifi.py` |
| Long messages don't fit                  | hard limit is 255 bytes per frame. Split into multiple frames or use a 16-bit length field |

---

## 10. Files in this project

| file                   | purpose                                                       |
| ---------------------- | ------------------------------------------------------------- |
| `lifi.py`              | the script — TX, channel, RX, plots, all five commands        |
| `lifi_pipeline.png`    | output plot from `simulate`                                   |
| `lifi_tx.wav`          | audio file generated by `wav-tx` (default name)               |

Run the simulate mode first. Once that works on your machine, build
the cardboard amplifier, plug an LED into your headphone jack, and
send your first message over a beam of light. Welcome to the future.
