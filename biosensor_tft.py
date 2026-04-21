"""
Fabrication and Characterization of a Metal-Oxide TFT-Based Flexible
Biosensor for Real-Time Sweat Analyte Detection
---------------------------------------------------------------------
This module models an IGZO (Indium-Gallium-Zinc-Oxide) thin-film
transistor (TFT) functionalised as an extended-gate biosensor for
detecting glucose and lactate in human sweat.

It provides:
    * A physics-based TFT compact model (above/below threshold).
    * Transfer (Id-Vgs) and output (Id-Vds) curve generators.
    * An enzymatic (GOx / LOx) surface potential model that couples
      analyte concentration to the TFT gate voltage via the Nernst
      and Michaelis-Menten equations.
    * A calibration / sensitivity analysis routine.
    * A real-time sweat-stream detection simulator with noise.
    * Matplotlib plotting utilities that save the four standard
      characterisation figures used in the accompanying PDF report.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import matplotlib.pyplot as plt


# ---------------------------------------------------------------------------
# Physical constants
# ---------------------------------------------------------------------------
Q_ELEM = 1.602176634e-19          # C, elementary charge
K_B = 1.380649e-23                # J/K, Boltzmann constant
EPS_0 = 8.8541878128e-12          # F/m, vacuum permittivity


# ---------------------------------------------------------------------------
# Device description
# ---------------------------------------------------------------------------
@dataclass
class TFTParams:
    """Geometrical and electrical parameters of the IGZO TFT."""
    W: float = 200e-6             # channel width (m)
    L: float = 20e-6              # channel length (m)
    t_ox: float = 100e-9          # Al2O3 gate-dielectric thickness (m)
    eps_r: float = 9.0            # relative permittivity of Al2O3
    mu: float = 12.0e-4           # field-effect mobility (m^2/V/s) ~12 cm2/Vs
    Vth: float = 0.6              # threshold voltage (V)
    SS: float = 0.15              # subthreshold slope (V/dec)
    Ioff: float = 1e-12           # off-state current (A)
    T: float = 303.0              # operating temperature (K, ~30 C skin)

    @property
    def Cox(self) -> float:
        """Gate capacitance per unit area (F/m^2)."""
        return self.eps_r * EPS_0 / self.t_ox


@dataclass
class EnzymeParams:
    """Michaelis-Menten parameters for an immobilised oxidase film."""
    name: str
    Km: float                     # Michaelis constant (mM)
    S_nernst: float               # Nernstian-like sensitivity (V/decade)
    V0: float                     # surface potential at 1 mM (V)


GLUCOSE_OXIDASE = EnzymeParams(name="GOx / glucose",
                               Km=8.0, S_nernst=0.052, V0=0.00)
LACTATE_OXIDASE = EnzymeParams(name="LOx / lactate",
                               Km=5.0, S_nernst=0.048, V0=-0.01)


# ---------------------------------------------------------------------------
# TFT compact model
# ---------------------------------------------------------------------------
def tft_drain_current(Vgs: np.ndarray, Vds: np.ndarray,
                      p: TFTParams) -> np.ndarray:
    """Unified above/below-threshold Id model for an n-type MOS-TFT."""
    Vgs = np.asarray(Vgs, dtype=float)
    Vds = np.asarray(Vds, dtype=float)
    Vt = K_B * p.T / Q_ELEM                         # thermal voltage
    n = p.SS / (math.log(10.0) * Vt)                # ideality factor

    # Smooth threshold: Vov = n*Vt * ln(1 + exp((Vgs - Vth)/(n*Vt)))
    arg = (Vgs - p.Vth) / (n * Vt)
    Vov = n * Vt * np.log1p(np.exp(np.clip(arg, -60.0, 60.0)))

    Vds_eff = np.minimum(Vds, Vov)                  # triode/saturation kink
    beta = p.mu * p.Cox * p.W / p.L
    Id = beta * (Vov * Vds_eff - 0.5 * Vds_eff**2)
    return Id + p.Ioff


def transfer_curve(p: TFTParams, Vds: float = 1.0,
                   Vgs_range=(-1.0, 3.0), n: int = 401):
    Vgs = np.linspace(*Vgs_range, n)
    Id = tft_drain_current(Vgs, np.full_like(Vgs, Vds), p)
    return Vgs, Id


def output_curves(p: TFTParams,
                  Vgs_list=(1.0, 1.5, 2.0, 2.5, 3.0),
                  Vds_range=(0.0, 3.0), n: int = 301):
    Vds = np.linspace(*Vds_range, n)
    curves = {vg: tft_drain_current(np.full_like(Vds, vg), Vds, p)
              for vg in Vgs_list}
    return Vds, curves


# ---------------------------------------------------------------------------
# Biosensing: enzyme surface potential -> gate shift
# ---------------------------------------------------------------------------
def surface_potential(conc_mM: np.ndarray, enz: EnzymeParams) -> np.ndarray:
    """
    Enzymatic surface-potential shift coupling an oxidase-generated
    H2O2 flux to the TFT gate.  At C << Km the response is Nernstian
    (linear in log10(C)); at C >> Km it saturates as C/(Km+C).
    """
    c = np.asarray(conc_mM, dtype=float)
    c_safe = np.clip(c, 1e-4, None)
    saturation = c_safe / (enz.Km + c_safe)
    nernst = enz.S_nernst * np.log10(1.0 + c_safe / 0.1)
    return enz.V0 + nernst * saturation / (1.0 / (1.0 + 0.1 / enz.Km))


def biosensor_current(conc_mM: np.ndarray, enz: EnzymeParams,
                      p: TFTParams, Vgs_bias: float = 1.5,
                      Vds: float = 1.0) -> np.ndarray:
    """Drain current vs analyte concentration at a fixed bias point."""
    dV = surface_potential(conc_mM, enz)
    Vgs_eff = Vgs_bias + dV
    return tft_drain_current(Vgs_eff, np.full_like(Vgs_eff, Vds), p)


def sensitivity(conc_mM: np.ndarray, current: np.ndarray) -> float:
    """Sensitivity as d(log10 Id)/d(log10 C) in the linear region."""
    mask = (conc_mM >= 0.1) & (conc_mM <= 5.0)
    x = np.log10(conc_mM[mask])
    y = np.log10(current[mask])
    slope, _ = np.polyfit(x, y, 1)
    return float(slope)


# ---------------------------------------------------------------------------
# Real-time sweat stream
# ---------------------------------------------------------------------------
def simulate_realtime(duration_s: float = 600.0, dt: float = 1.0,
                      enz: EnzymeParams = GLUCOSE_OXIDASE,
                      p: TFTParams | None = None,
                      seed: int = 7) -> tuple[np.ndarray, np.ndarray,
                                              np.ndarray]:
    """
    Generate a 10-minute sweat glucose trace with two stimulus spikes
    and measure the corresponding TFT drain current.
    """
    p = p or TFTParams()
    rng = np.random.default_rng(seed)
    t = np.arange(0.0, duration_s, dt)

    baseline = 0.2                                   # mM resting sweat glucose
    conc = np.full_like(t, baseline)
    conc += 1.5 * np.exp(-((t - 150.0) / 25.0) ** 2)  # meal spike
    conc += 0.8 * np.exp(-((t - 420.0) / 40.0) ** 2)  # exercise spike
    conc += rng.normal(0.0, 0.02, size=t.shape)       # biological noise
    conc = np.clip(conc, 0.01, None)

    Id = biosensor_current(conc, enz, p, Vgs_bias=1.5, Vds=1.0)
    Id *= 1.0 + rng.normal(0.0, 0.01, size=Id.shape)  # 1% electrical noise
    return t, conc, Id


# ---------------------------------------------------------------------------
# Plotting helpers (used by generate_report.py)
# ---------------------------------------------------------------------------
def _style():
    plt.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.grid": True,
        "grid.alpha": 0.3,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 140,
    })


def plot_transfer(p: TFTParams, path: str) -> None:
    _style()
    Vgs, Id = transfer_curve(p)
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    ax.semilogy(Vgs, Id, color="#1f4e79", lw=1.6)
    ax.set_xlabel("Vgs (V)")
    ax.set_ylabel("Id (A)")
    ax.set_title("Transfer characteristic  (Vds = 1 V)")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_output(p: TFTParams, path: str) -> None:
    _style()
    Vds, curves = output_curves(p)
    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    for vg, Id in curves.items():
        ax.plot(Vds, Id * 1e6, lw=1.4, label=f"Vgs = {vg:.1f} V")
    ax.set_xlabel("Vds (V)")
    ax.set_ylabel("Id (µA)")
    ax.set_title("Output characteristics")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def plot_calibration(p: TFTParams, path: str) -> None:
    _style()
    conc = np.logspace(-2, 1.3, 80)                  # 0.01 - ~20 mM
    Id_g = biosensor_current(conc, GLUCOSE_OXIDASE, p)
    Id_l = biosensor_current(conc, LACTATE_OXIDASE, p)

    fig, ax = plt.subplots(figsize=(4.2, 3.0))
    ax.loglog(conc, Id_g * 1e6, "o-", color="#c0392b",
              ms=3, lw=1.2, label="Glucose (GOx)")
    ax.loglog(conc, Id_l * 1e6, "s-", color="#27ae60",
              ms=3, lw=1.2, label="Lactate (LOx)")
    ax.set_xlabel("Analyte concentration (mM)")
    ax.set_ylabel("Id (µA)")
    ax.set_title("Biosensor calibration")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)

    s_g = sensitivity(conc, Id_g)
    s_l = sensitivity(conc, Id_l)
    print(f"[calibration] glucose sensitivity  = {s_g:.3f} dec/dec")
    print(f"[calibration] lactate  sensitivity = {s_l:.3f} dec/dec")


def plot_realtime(p: TFTParams, path: str) -> None:
    _style()
    t, conc, Id = simulate_realtime(p=p)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(4.6, 3.8), sharex=True)
    ax1.plot(t, conc, color="#8e44ad", lw=1.2)
    ax1.set_ylabel("Glucose (mM)")
    ax1.set_title("Real-time sweat monitoring  (10 min)")
    ax2.plot(t, Id * 1e6, color="#1f4e79", lw=1.2)
    ax2.set_ylabel("Id (µA)")
    ax2.set_xlabel("Time (s)")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import os
    os.makedirs("figures", exist_ok=True)
    p = TFTParams()
    print(f"Cox = {p.Cox*1e3:.2f} mF/m^2,  "
          f"W/L = {p.W/p.L:.0f},  "
          f"mu = {p.mu*1e4:.1f} cm^2/Vs")

    plot_transfer(p, "figures/fig_transfer.png")
    plot_output(p, "figures/fig_output.png")
    plot_calibration(p, "figures/fig_calibration.png")
    plot_realtime(p, "figures/fig_realtime.png")
    print("Figures written to ./figures/")
