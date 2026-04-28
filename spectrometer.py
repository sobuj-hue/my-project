#!/usr/bin/env python3
"""
DIY Diffraction-Grating Spectrometer
====================================
Capture an image of a light source dispersed through a CD/DVD grating,
extract the 1-D intensity profile, calibrate pixels to wavelength, and
identify spectral peaks.

Three run modes:
    demo     - generate a synthetic CFL/fluorescent spectrum (no hardware)
    image    - load and analyse a saved photograph
    capture  - grab a frame from a connected USB webcam

Install once:
    pip install numpy matplotlib scipy opencv-python

Quick start (no hardware needed):
    python spectrometer.py --mode demo
"""

import argparse
import os
import sys
import json
from pathlib import Path

import numpy as np
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, savgol_filter
from scipy.optimize import curve_fit

# ──────────────────────────────────────────────────────────
#  Optional dependency: OpenCV (only needed for webcam/image modes)
# ──────────────────────────────────────────────────────────
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

# ──────────────────────────────────────────────────────────
#  Grating constants
# ──────────────────────────────────────────────────────────
GRATINGS = {
    "DVD": {"lines_per_mm": 1350, "pitch_nm": 740.0},   # d = 1/1350 mm = 740 nm
    "CD":  {"lines_per_mm":  625, "pitch_nm": 1600.0},  # d = 1/625  mm = 1600 nm
}

# ──────────────────────────────────────────────────────────
#  Reference spectral lines (nm)
#  Mercury lines from a fluorescent / CFL bulb — used for calibration.
# ──────────────────────────────────────────────────────────
HG_LINES = {
    "Hg violet":    404.7,
    "Hg blue":      435.8,
    "Hg green":     546.1,
    "Hg yellow-1":  577.0,
    "Hg yellow-2":  579.1,
    "Tb red":       611.6,    # red phosphor in modern CFLs
}

# Common LED peaks (rough, useful as a sanity check)
LED_PEAKS = {
    "Red LED":   650.0,
    "Green LED": 525.0,
    "Blue LED":  470.0,
}

# ──────────────────────────────────────────────────────────
#  STEP 1 — Acquire the spectrum image
# ──────────────────────────────────────────────────────────

def synthetic_cfl_image(width=1200, height=120):
    """
    Build a fake photograph of a CFL spectrum dispersed by a grating.
    Each Hg line becomes a vertical bright stripe; phosphor adds a dim
    background hump. Used by `--mode demo` so the pipeline runs without
    any hardware.
    """
    # Pretend pixel column 100 = 400 nm, column 1100 = 700 nm
    px = np.arange(width)
    wl = np.linspace(380, 720, width)             # ground-truth wavelength axis

    img = np.zeros((height, width, 3), dtype=np.float32)

    def add_line(centre_nm, intensity, sigma=2.0, color=(1, 1, 1)):
        prof = intensity * np.exp(-0.5 * ((wl - centre_nm) / sigma) ** 2)
        for ch in range(3):
            img[:, :, ch] += prof * color[ch]

    # Mercury lines (typical CFL)
    add_line(404.7, 0.55, 1.6, (0.6, 0.0, 1.0))   # violet
    add_line(435.8, 0.85, 1.6, (0.0, 0.4, 1.0))   # blue
    add_line(546.1, 1.00, 1.6, (0.1, 1.0, 0.2))   # green
    add_line(577.0, 0.65, 1.6, (1.0, 1.0, 0.0))   # yellow-1
    add_line(579.1, 0.65, 1.6, (1.0, 0.9, 0.0))   # yellow-2
    add_line(611.6, 0.55, 2.5, (1.0, 0.2, 0.1))   # red phosphor

    # broad phosphor background
    bg = 0.18 * np.exp(-0.5 * ((wl - 600) / 80) ** 2)
    for ch in range(3):
        img[:, :, ch] += bg * (0.9 if ch == 0 else 0.6)

    # noise + gentle vertical gradient (camera-like)
    rng = np.random.default_rng(7)
    img += 0.02 * rng.standard_normal(img.shape)
    grad = np.linspace(0.85, 1.15, height).reshape(-1, 1, 1)
    img *= grad
    img = np.clip(img, 0, 1)

    return (img * 255).astype(np.uint8), wl


def load_image(path):
    """Read an image file using OpenCV; convert BGR→RGB."""
    if not HAS_CV2:
        raise RuntimeError("opencv-python is required to load image files.")
    img_bgr = cv2.imread(str(path))
    if img_bgr is None:
        raise FileNotFoundError(f"Could not open image: {path}")
    return cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)


def capture_image_from_webcam(cam_index=0, warmup_frames=10):
    """Grab a single frame from the default USB webcam."""
    if not HAS_CV2:
        raise RuntimeError("opencv-python is required for webcam capture.")
    cap = cv2.VideoCapture(cam_index)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open webcam #{cam_index}.")
    # let the camera auto-expose
    for _ in range(warmup_frames):
        cap.read()
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError("Failed to grab frame.")
    return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)


# ──────────────────────────────────────────────────────────
#  STEP 2 — Extract 1-D intensity profile from the 2-D image
# ──────────────────────────────────────────────────────────

def extract_spectrum_1d(img, roi=None, smooth=True):
    """
    Collapse a 2-D image to a 1-D intensity vs. pixel-column array.

    img   - HxWx3 RGB uint8/float image
    roi   - (y0, y1) row range that contains the spectrum stripe.
            If None, the central 40% of rows are used.
    smooth - apply a gentle Savitzky-Golay filter to reduce sensor noise
    """
    H = img.shape[0]
    if roi is None:
        roi = (int(H * 0.30), int(H * 0.70))
    y0, y1 = roi
    strip = img[y0:y1].astype(np.float32)

    # Use the brightness channel (mean of R+G+B).  The eye/camera cannot
    # represent spectral colours faithfully, so summing channels gives the
    # most reliable intensity envelope.
    intensity = strip.mean(axis=(0, 2))      # length = image width

    if smooth and intensity.size > 11:
        intensity = savgol_filter(intensity, 11, 3)

    intensity -= intensity.min()
    if intensity.max() > 0:
        intensity /= intensity.max()
    return intensity


# ──────────────────────────────────────────────────────────
#  STEP 3 — Calibrate pixel → wavelength
# ──────────────────────────────────────────────────────────

def calibrate(pixel_positions, wavelengths_nm, degree=1):
    """
    Fit a polynomial λ(pixel) of given degree.
    Two points → linear, three+ → quadratic recommended.
    Returns the polynomial coefficients (highest degree first).
    """
    pixel_positions = np.asarray(pixel_positions, dtype=float)
    wavelengths_nm  = np.asarray(wavelengths_nm,  dtype=float)
    if pixel_positions.size < degree + 1:
        raise ValueError(f"Need at least {degree + 1} calibration points "
                         f"for degree-{degree} fit.")
    return np.polyfit(pixel_positions, wavelengths_nm, deg=degree)


def pixel_to_wavelength(pixels, coeffs):
    return np.polyval(coeffs, pixels)


def save_calibration(coeffs, path="calibration.json"):
    Path(path).write_text(json.dumps({"coeffs": coeffs.tolist()}, indent=2))


def load_calibration(path="calibration.json"):
    if not Path(path).exists():
        return None
    return np.array(json.loads(Path(path).read_text())["coeffs"])


# ──────────────────────────────────────────────────────────
#  STEP 4 — Find and label spectral peaks
# ──────────────────────────────────────────────────────────

def detect_peaks(intensity, prominence=0.05, distance=8):
    """Return pixel indices where intensity has a local maximum."""
    peaks, props = find_peaks(intensity, prominence=prominence, distance=distance)
    return peaks, props["prominences"]


def _gauss(x, a, mu, sigma, b):
    return a * np.exp(-0.5 * ((x - mu) / sigma) ** 2) + b


def refine_peak(intensity, idx, halfwidth=12):
    """Sub-pixel peak position via Gaussian fit around an integer index."""
    lo, hi = max(0, idx - halfwidth), min(intensity.size, idx + halfwidth + 1)
    x = np.arange(lo, hi)
    y = intensity[lo:hi]
    try:
        popt, _ = curve_fit(_gauss, x, y,
                            p0=[y.max() - y.min(), idx, 3.0, y.min()],
                            maxfev=4000)
        return popt[1]                  # sub-pixel centre
    except RuntimeError:
        return float(idx)


# ──────────────────────────────────────────────────────────
#  STEP 5 — Display + save the result
# ──────────────────────────────────────────────────────────

def plot_result(img, intensity, coeffs, peaks_px, save_path=None,
                title="Spectrum"):
    fig = plt.figure(figsize=(10, 6), constrained_layout=True)
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 2.5], hspace=0.05)

    # top: photograph of the spectrum band
    ax_img = fig.add_subplot(gs[0])
    ax_img.imshow(img, aspect="auto")
    ax_img.set_xticks([])
    ax_img.set_yticks([])
    ax_img.set_title(title, fontsize=11, fontweight="bold")

    # bottom: 1-D intensity vs wavelength
    ax = fig.add_subplot(gs[1])
    px = np.arange(intensity.size)
    wl = pixel_to_wavelength(px, coeffs) if coeffs is not None else px
    ax.plot(wl, intensity, color="#222", lw=1.2)
    ax.fill_between(wl, intensity, alpha=0.15, color="#3182ce")

    # label each detected peak
    for p in peaks_px:
        wl_p = pixel_to_wavelength(p, coeffs) if coeffs is not None else p
        ax.axvline(wl_p, color="crimson", ls=":", lw=0.8)
        ax.text(wl_p, intensity[int(p)] + 0.02,
                f"{wl_p:.0f}", ha="center", fontsize=8, color="crimson")

    ax.set_xlabel("Wavelength (nm)" if coeffs is not None else "Pixel column")
    ax.set_ylabel("Normalised intensity")
    ax.grid(alpha=0.25, ls="--")
    ax.set_ylim(-0.02, 1.10)

    if save_path:
        plt.savefig(save_path, dpi=180, bbox_inches="tight")
        print(f"Saved plot → {save_path}")
    return fig


# ──────────────────────────────────────────────────────────
#  HIGH-LEVEL ANALYSIS PIPELINE
# ──────────────────────────────────────────────────────────

def analyse(img, calibration=None, expected_lines_nm=None, title="Spectrum"):
    """
    Run the full pipeline on an image and return key results.
    expected_lines_nm: list of known reference wavelengths (sorted) used for
                      automatic calibration when the input image is a known
                      reference source (e.g. CFL).
    """
    intensity = extract_spectrum_1d(img)
    peaks_px, prominences = detect_peaks(intensity)

    # refine peak centres to sub-pixel precision
    refined = np.array([refine_peak(intensity, p) for p in peaks_px])

    coeffs = calibration
    if coeffs is None and expected_lines_nm is not None and refined.size >= 2:
        # Use the brightest peaks (by prominence), match them to the supplied
        # known wavelengths in left-to-right order.
        n_use = min(len(expected_lines_nm), refined.size)
        order = np.argsort(prominences)[::-1][:n_use]
        chosen_px = np.sort(refined[order])
        chosen_wl = np.sort(np.asarray(expected_lines_nm)[:n_use])
        deg = 2 if n_use >= 3 else 1
        coeffs = calibrate(chosen_px, chosen_wl, degree=deg)
        print(f"Auto-calibrated using {n_use} peaks "
              f"(degree-{deg} fit):")
        for px_i, wl_i in zip(chosen_px, chosen_wl):
            print(f"   pixel {px_i:7.1f}  →  {wl_i:6.1f} nm")

    return {
        "intensity": intensity,
        "peaks_px":  refined,
        "coeffs":    coeffs,
    }


# ──────────────────────────────────────────────────────────
#  COMMAND-LINE ENTRY POINT
# ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["demo", "image", "capture"],
                        default="demo",
                        help="demo: synthetic CFL spectrum (default) | "
                             "image: load --file | capture: webcam grab")
    parser.add_argument("--file", type=str,
                        help="path to image (used with --mode image)")
    parser.add_argument("--cam", type=int, default=0,
                        help="webcam index (used with --mode capture)")
    parser.add_argument("--out", type=str, default="spectrum.png",
                        help="output plot filename")
    parser.add_argument("--no-show", action="store_true",
                        help="don't open the matplotlib window")
    args = parser.parse_args()

    # ── 1.  acquire the image ────────────────────────────
    print(f"\n[1] Acquiring image  (mode = {args.mode})")
    if args.mode == "demo":
        img, _ = synthetic_cfl_image()
        title  = "Demo: synthetic CFL spectrum"
        # In demo mode we know the source is a CFL → seed the calibration
        expected_lines = [HG_LINES["Hg violet"], HG_LINES["Hg blue"],
                          HG_LINES["Hg green"],  HG_LINES["Hg yellow-1"],
                          HG_LINES["Tb red"]]
    elif args.mode == "image":
        if not args.file:
            sys.exit("--file is required when --mode image")
        img = load_image(args.file)
        title = f"Image: {os.path.basename(args.file)}"
        expected_lines = None
    else:  # capture
        img = capture_image_from_webcam(args.cam)
        title = "Webcam capture"
        expected_lines = None

    print(f"    image shape = {img.shape}")

    # ── 2.  use saved calibration if present ─────────────
    saved = load_calibration()
    if saved is not None:
        print(f"[2] Using saved calibration from calibration.json: "
              f"{saved.tolist()}")

    # ── 3.  run pipeline ─────────────────────────────────
    print("[3] Extracting 1-D intensity, detecting peaks…")
    result = analyse(img,
                     calibration=saved,
                     expected_lines_nm=expected_lines,
                     title=title)

    coeffs = result["coeffs"]
    if coeffs is not None and saved is None:
        save_calibration(coeffs)
        print(f"    Saved auto-calibration to calibration.json")

    # ── 4.  report peaks ─────────────────────────────────
    print("[4] Peaks found:")
    for p in result["peaks_px"]:
        if coeffs is not None:
            wl = pixel_to_wavelength(p, coeffs)
            print(f"      pixel {p:7.1f}  →  {wl:6.1f} nm")
        else:
            print(f"      pixel {p:7.1f}  (no calibration)")

    # ── 5.  plot ─────────────────────────────────────────
    plot_result(img, result["intensity"], coeffs,
                result["peaks_px"], save_path=args.out, title=title)
    if not args.no_show:
        plt.show()

    print("\nDone.\n")


if __name__ == "__main__":
    main()
