# DIY Diffraction-Grating Spectrometer — Complete Guide

A full beginner's walkthrough of the project: physics, parts list, build,
software, calibration, and explanation of every important line of code.

---

## 1. What you are building

A spectrometer is an instrument that splits light into its individual
wavelengths (colours) and measures how bright each one is. Commercial
units cost hundreds to thousands of dollars. Yours will cost under $5
and produce a real, calibrated spectrum that can identify a fluorescent
lamp's mercury lines, an LED's emission peak, or the absorption bands of
a coloured liquid.

How it works in one sentence: a piece of CD/DVD acts as a *diffraction
grating* that bends each colour by a different angle, your webcam
photographs the rainbow, and the Python script converts pixels into
wavelengths.

---

## 2. The physics — diffraction grating equation

A diffraction grating is a surface with thousands of parallel grooves.
When light hits it, each groove acts as a tiny slit. The waves from
neighbouring grooves interfere; the result is constructive only at
certain angles given by the grating equation:

```
d · sin(θ) = m · λ
```

| symbol | meaning                                       |
| ------ | --------------------------------------------- |
| d      | distance between two grooves (the *pitch*)    |
| θ      | the angle at which the colour appears         |
| m      | diffraction order (m = 1 for first-order)     |
| λ      | wavelength of light                           |

So longer wavelengths (red) bend more than shorter wavelengths (blue) —
that is what causes the rainbow.

### Why CDs and DVDs work as gratings

Their data tracks are equally-spaced concentric rings. Stripped of the
top reflective layer, the transparent polycarbonate becomes a transmission
grating with:

| medium | groove pitch d | grooves per mm |
| ------ | -------------- | -------------- |
| CD     | 1600 nm        | 625            |
| DVD    | 740 nm         | 1350           |

A DVD's denser grooves spread the colours further apart, giving better
resolution — preferred for this project.

---

## 3. Bill of materials

| item                         | source / cost                |
| ---------------------------- | ---------------------------- |
| 1 blank/discarded DVD        | free                         |
| 1 USB webcam (or smartphone) | $5 – $10 (or you already have one) |
| 1 small cardboard box        | recycled — shoe box works    |
| 2 single-edge razor blades   | hardware store, ~$1          |
| Black tape / black paint     | ~$1                          |

Optional but useful:

* a CFL or fluorescent bulb (great calibration source — has known mercury lines)
* a red, green, and blue LED (~$1 set)
* a cheap laser pointer (650 nm red, or 532 nm green)

---

## 4. Build steps (hardware)

1. **Cut a 2 cm square from the DVD.** Carefully peel off the silver
   reflective layer with sticky tape — what remains is the transparent
   diffraction grating. Hold it up to a light: you should see rainbows.
2. **Make the slit.** Tape two razor blades onto a piece of cardboard
   so their sharp edges almost touch, leaving a vertical gap of about
   0.2 mm. This is your entrance slit.
3. **Assemble the box.**
   * Cut a window for the slit at one end.
   * Cut another window 90° from the slit (on the side) for the camera.
   * Tape the DVD piece *inside* the box, opposite the slit, tilted ~45°
     toward the camera window.
   * Paint or line the inside black so stray light doesn't fog the image.
4. **Aim the camera through the side window** at the DVD. Light enters
   the slit, hits the DVD, and gets dispersed into a horizontal rainbow
   on your camera sensor.

ASCII layout (top view):

```
          light source
              │
              ▼
        ┌────slit────┐
        │            │
        │            │
        │       DVD ◤│  ←── tilted ~45°
        │            │
        └──[camera]──┘     looks at the dispersed
                          rainbow on the DVD
```

That is all the hardware. The rest is software.

---

## 5. Software — install and run

```bash
pip install numpy matplotlib scipy opencv-python
```

The script offers three modes:

```bash
# 1) Demo (no hardware) — generates a synthetic CFL spectrum and analyses it
python spectrometer.py --mode demo

# 2) From a saved photograph
python spectrometer.py --mode image --file my_spectrum.jpg

# 3) Direct webcam capture
python spectrometer.py --mode capture --cam 0
```

Run the demo first to confirm everything works. The output:

* `spectrum.png` — the plot
* `calibration.json` — the saved pixel → wavelength polynomial

---

## 6. The pipeline — what the code does, step by step

The script breaks the analysis into five clear stages.

### Step 1 — Acquire the image

Three sources are supported:

* `synthetic_cfl_image()` builds a realistic CFL fluorescent spectrum
  with the six brightest mercury and phosphor lines. Used by `--mode demo`
  so you can run everything end-to-end without any hardware.
* `load_image(path)` reads a saved photograph with OpenCV.
* `capture_image_from_webcam()` grabs a live frame, after a 10-frame
  warm-up so the camera has time to auto-expose.

### Step 2 — Collapse 2-D image to 1-D intensity profile

```python
strip = img[y0:y1].astype(np.float32)
intensity = strip.mean(axis=(0, 2))
```

The spectrum looks like a horizontal coloured band. We crop a horizontal
strip (the central 40% of rows by default) and average vertically — this
turns each *column* of pixels into a single intensity value. The reason
we average vertically instead of taking just one row is **noise**: 50
rows averaged together has ~7× lower noise than a single row.

We also average the three RGB channels because the camera's colour
filters distort the relative intensities of close wavelengths; the sum
of the channels gives a much more faithful "how much light is here"
estimate.

A Savitzky-Golay filter (`savgol_filter`) is then applied. This is a
smoothing technique that **preserves peak shape** much better than a
simple moving average — important because we will later fit Gaussians
to those peaks to find their true centre.

### Step 3 — Calibrate pixel → wavelength

This is the heart of the whole project. Without calibration the x-axis
of your plot is just "pixel column 0…1200" — meaningless. We fix this
by *anchoring* known peaks to known wavelengths.

```python
def calibrate(pixel_positions, wavelengths_nm, degree=1):
    return np.polyfit(pixel_positions, wavelengths_nm, deg=degree)
```

`np.polyfit` performs a least-squares fit of a polynomial. For two
calibration points we use a straight line (`degree=1`); with three or
more we use a quadratic (`degree=2`), which corrects for the slight
non-linearity of `sin(θ)` versus pixel position.

#### Where do we get the reference wavelengths?

A **CFL or fluorescent tube** is the perfect calibration source because
the mercury vapour inside emits a handful of very narrow, very precisely
known lines:

| line          | wavelength (nm) |
| ------------- | --------------- |
| Hg violet     | 404.7           |
| Hg blue       | 435.8           |
| Hg green      | 546.1           |
| Hg yellow-1   | 577.0           |
| Hg yellow-2   | 579.1           |
| Tb red        | 611.6           |

Photograph a CFL once, run the auto-calibration, and the result is
saved to `calibration.json`. Every later measurement reuses it.

### Step 4 — Find peaks and refine to sub-pixel precision

```python
peaks_px, props = find_peaks(intensity, prominence=0.05, distance=8)
```

`scipy.signal.find_peaks` returns the integer column indices of all
local maxima that are tall enough (`prominence ≥ 0.05`) and far enough
apart (`distance ≥ 8 px`). `prominence` is the height of the peak above
its surrounding baseline — a much better criterion than absolute height.

The integer index is then refined using `refine_peak()`, which fits a
Gaussian to a small window around each peak:

```python
popt, _ = curve_fit(_gauss, x, y,
                    p0=[y.max()-y.min(), idx, 3.0, y.min()])
```

The fit returns the peak centre to within ~0.1 pixel — much better than
the integer position. With a 1 nm/pixel calibration that is 0.1 nm of
wavelength accuracy.

### Step 5 — Display

The result figure has two parts:

* **Top panel**: the original 2-D image, so you can visually verify
  what was measured.
* **Bottom panel**: the 1-D intensity vs. wavelength plot. Dotted red
  vertical lines mark every detected peak with its wavelength.

---

## 7. Detailed walkthrough of the trickiest bits

### Why `prominence` and not `height`?

`height` filters peaks by their absolute value. That fails when the
spectrum has a slowly-varying background (e.g. phosphor glow): every
point above the background is "tall", so you'd get hundreds of false
peaks. `prominence` measures how much a peak sticks out *above its
local surroundings*, which works regardless of the baseline level.

### Why a Gaussian fit on top of the integer-pixel peak?

A real spectral line has a well-defined centre but the camera samples
it on a coarse pixel grid. The integer peak is whichever pixel happens
to fall closest to the true centre — accurate only to ±0.5 px. Fitting
a Gaussian to a small window of pixels around that peak interpolates
between samples and recovers the underlying continuous centre to
sub-pixel precision. This is called **centroiding** and is standard in
astronomy and spectroscopy.

### Why fit a polynomial pixel → wavelength rather than use the grating equation directly?

The grating equation `d·sin(θ)=mλ` *is* the underlying physics, but it
needs the exact distance from the slit to the sensor and the exact
tilt of the grating, which are hard to measure to within a millimetre
in a cardboard box. A two-point polynomial calibration absorbs all
those geometric uncertainties into two fitted numbers and works
reliably even if you bump the box.

### Why save and reuse the calibration?

The pixel-to-wavelength mapping depends on the *geometry* of your box
and camera, not on the light source. As long as you don't move the
camera or the grating, the calibration from a CFL applies to every
subsequent measurement (LED, sun, candle flame, …). The script writes
`calibration.json` after the first successful auto-calibration and
reads it on later runs.

---

## 8. What the demo output looks like

Running `python spectrometer.py --mode demo` prints something like:

```
[1] Acquiring image  (mode = demo)
    image shape = (120, 1200, 3)
[3] Extracting 1-D intensity, detecting peaks…
Auto-calibrated using 5 peaks (degree-2 fit):
   pixel    87.1  →   404.7 nm
   pixel   196.8  →   435.8 nm
   pixel   585.8  →   546.1 nm
   pixel   698.3  →   577.0 nm
   pixel   816.7  →   611.6 nm
[4] Peaks found:
      pixel    87.1  →   404.8 nm
      pixel   196.8  →   435.7 nm
      pixel   585.8  →   545.7 nm
      pixel   698.3  →   577.7 nm
      pixel   816.7  →   611.3 nm
Saved plot → spectrum.png
```

The recovered wavelengths agree with the inputs to 0.5 nm — the entire
pipeline (calibration + peak finding + sub-pixel refinement) works.

---

## 9. Real-world experiments you can now do

Once your hardware works and you have a saved calibration:

1. **Compare LED emission spectra** — measure red, green, blue, white
   LEDs; find the peak wavelength of each and verify it matches the
   datasheet.
2. **Fluorescent vs. incandescent vs. LED bulbs** — you'll see line
   spectra (CFL) versus continuous black-body spectra (incandescent)
   versus broad blue + phosphor humps (white LED). A great teaching
   demo.
3. **Beer-Lambert absorption** — illuminate a vial of food colouring
   with a white LED, see which wavelengths are absorbed. Makes a quick
   colorimeter.
4. **Sunlight** — look for the dark Fraunhofer lines (sodium D-line at
   589 nm is the easiest to spot). Tells you what gases are in the
   sun's atmosphere.

---

## 10. Troubleshooting

| Symptom                                | Likely cause / fix                                                   |
| -------------------------------------- | -------------------------------------------------------------------- |
| Spectrum looks blurry                  | Slit too wide → narrow it to <0.3 mm                                 |
| No peaks detected                      | Camera over-exposed (signal saturated) → reduce exposure / lower brightness |
| Calibration gives non-monotonic λ      | Peaks were matched in the wrong order → calibrate manually with `--mode image` and pass known wavelengths |
| Webcam grabs a black frame             | Wrong camera index → try `--cam 1` or `--cam 2`                      |
| "opencv-python is required" error      | `pip install opencv-python`                                          |

---

## 11. File summary

| file                | purpose                                                         |
| ------------------- | --------------------------------------------------------------- |
| `spectrometer.py`   | the analysis script (this is what you run)                      |
| `calibration.json`  | created automatically; stores your pixel→wavelength polynomial  |
| `spectrum.png`      | output plot                                                     |

That's it. Run the demo, then build the cardboard box, then point it
at light sources around your house. Have fun.
