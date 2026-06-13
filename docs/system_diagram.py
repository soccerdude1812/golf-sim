#!/usr/bin/env python3
"""Generate the system diagram (physical layout + wiring) as a PNG.

Produces docs/system_diagram.png: a top view and side view of the two-camera
rig around the hitting area, plus a wiring/block diagram of the electronics.
Run:  python docs/system_diagram.py
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import (Rectangle, Circle, FancyBboxPatch,
                                FancyArrowPatch, Wedge, Polygon)
import numpy as np

C_BALL = "#f2f2f2"
C_CAM = "#2c6fbb"
C_CAMB = "#7e3ff2"
C_NET = "#444"
C_STROBE = "#d6181f"
C_GOLF = "#1f9e57"
C_ZONE = "#ffd24d"
C_PI = "#c51a4a"
C_PICO = "#111"
C_BOX = "#eef2f7"

fig = plt.figure(figsize=(15, 10))
fig.suptitle("Two-Camera DIY Golf Launch Monitor — System Layout & Wiring",
             fontsize=17, fontweight="bold", y=0.98)

# ----------------------------------------------------------------- TOP VIEW
ax = fig.add_subplot(2, 2, 1)
ax.set_title("TOP VIEW  (looking down)", fontweight="bold")
# target line / corridor
ax.annotate("", xy=(1.9, 0), xytext=(0, 0),
            arrowprops=dict(arrowstyle="-|>", color="#888", lw=1.5, ls="--"))
ax.text(1.55, 0.08, "target line  (+X)", color="#888", fontsize=9)
# measurement corridor
ax.add_patch(Rectangle((0, -0.18), 0.4, 0.36, color=C_ZONE, alpha=0.55, zorder=0))
ax.text(0.2, 0.27, "measured\nzone ~0.3 m", ha="center", fontsize=8, color="#9a7d00")
# net
ax.add_patch(Rectangle((1.78, -0.8), 0.06, 1.6, color=C_NET))
ax.text(1.81, 0.9, "NET\n(≥ 0.7 m away)", ha="center", fontsize=9, color=C_NET)
# ball
ax.add_patch(Circle((0, 0), 0.05, color=C_BALL, ec="k", zorder=5))
ax.text(0, -0.16, "ball", ha="center", fontsize=8)
# golfer
ax.add_patch(Circle((-0.05, -0.55), 0.16, color=C_GOLF, alpha=0.85))
ax.text(-0.05, -0.55, "golfer", ha="center", va="center", fontsize=7, color="white")
# Camera A face-on side (0.20,-1.25)
ax.add_patch(Rectangle((0.13, -1.32), 0.14, 0.14, color=C_CAM, zorder=5))
ax.text(0.45, -1.25, "CAM A\nface-on / side\n(0.20, -1.25)", fontsize=8, color=C_CAM, va="center")
ax.add_patch(Wedge((0.20, -1.25), 1.0, 70, 110, color=C_CAM, alpha=0.10))
ax.annotate("", xy=(0.20, -0.1), xytext=(0.20, -1.18),
            arrowprops=dict(arrowstyle="-|>", color=C_CAM, lw=1.2, alpha=0.7))
# Camera B behind-high (-1.1,-0.9) projected
ax.add_patch(Rectangle((-1.17, -0.97), 0.14, 0.14, color=C_CAMB, zorder=5))
ax.text(-1.1, -1.18, "CAM B  behind-high\n(-1.1, -0.9, z=1.7 m)", fontsize=8,
        color=C_CAMB, ha="center")
ax.annotate("", xy=(0.12, -0.05), xytext=(-1.0, -0.85),
            arrowprops=dict(arrowstyle="-|>", color=C_CAMB, lw=1.2, alpha=0.7))
# IR strobe near cam A
ax.add_patch(Rectangle((0.30, -1.05), 0.1, 0.1, color=C_STROBE, zorder=5))
ax.text(0.55, -0.95, "IR strobe", fontsize=8, color=C_STROBE)
ax.set_xlim(-1.5, 2.2); ax.set_ylim(-1.5, 1.1)
ax.set_aspect("equal"); ax.set_xlabel("X  (m, toward net)"); ax.set_ylabel("Y  (m)")
ax.grid(alpha=0.15)

# ----------------------------------------------------------------- SIDE VIEW
ax2 = fig.add_subplot(2, 2, 3)
ax2.set_title("SIDE VIEW  (along the target line)", fontweight="bold")
# ground
ax2.add_patch(Rectangle((-1.6, -0.05), 4.0, 0.05, color="#8a6d3b"))
# net
ax2.add_patch(Rectangle((1.78, 0), 0.06, 2.1, color=C_NET))
ax2.text(1.81, 2.18, "NET", ha="center", fontsize=9, color=C_NET)
# measured zone + ball flight dots
ax2.add_patch(Rectangle((0, 0), 0.4, 0.5, color=C_ZONE, alpha=0.5))
for i in range(5):
    x = i * 0.075; z = 0.06 + i * 0.016
    ax2.add_patch(Circle((x, z), 0.022, color=C_BALL, ec="k", zorder=6))
ax2.text(0.2, 0.6, "5 strobe images\n(first ~0.3 m)", ha="center", fontsize=8, color="#9a7d00")
# golfer + swing-arc keep-out
ax2.add_patch(Rectangle((-0.18, 0), 0.18, 0.95, color=C_GOLF, alpha=0.85))
ax2.text(-0.09, 1.0, "golfer", ha="center", fontsize=7, color=C_GOLF)
arc = Wedge((-0.1, 0.95), 1.15, 200, 360, width=0.02, color="#cc0000", alpha=0.35)
ax2.add_patch(arc)
ax2.text(-0.95, 1.55, "club swing arc\n(KEEP-OUT)", color="#cc0000", fontsize=8, ha="center")
# Camera A low
ax2.add_patch(Rectangle((0.14, 0.22), 0.13, 0.12, color=C_CAM, zorder=5))
ax2.text(0.33, 0.30, "CAM A  (~0.3 m high, low tripod)", fontsize=8, color=C_CAM, va="center")
# Camera B high
ax2.add_patch(Rectangle((-1.16, 1.65), 0.13, 0.12, color=C_CAMB, zorder=5))
ax2.text(-1.05, 1.88, "CAM B  (~1.7 m high — above the swing)", fontsize=8, color=C_CAMB)
ax2.annotate("", xy=(0.15, 0.12), xytext=(-1.0, 1.65),
             arrowprops=dict(arrowstyle="-|>", color=C_CAMB, lw=1.2, alpha=0.6))
ax2.annotate("", xy=(0.2, 0.08), xytext=(0.2, 0.22),
             arrowprops=dict(arrowstyle="-|>", color=C_CAM, lw=1.2, alpha=0.6))
ax2.set_xlim(-1.6, 2.3); ax2.set_ylim(-0.1, 2.4)
ax2.set_aspect("equal"); ax2.set_xlabel("X  (m, toward net)"); ax2.set_ylabel("Z  (m, up)")
ax2.grid(alpha=0.15)

# ----------------------------------------------------------------- WIRING
ax3 = fig.add_subplot(1, 2, 2)
ax3.set_title("WIRING / SIGNAL FLOW", fontweight="bold")
ax3.set_xlim(0, 10); ax3.set_ylim(0, 12); ax3.axis("off")


def box(x, y, w, h, label, fc=C_BOX, ec="#333", tc="#111", fs=9, bold=True):
    ax3.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                                 fc=fc, ec=ec, lw=1.5))
    ax3.text(x + w / 2, y + h / 2, label, ha="center", va="center",
             fontsize=fs, color=tc, fontweight="bold" if bold else "normal")


def wire(p1, p2, color="#333", label="", ls="-", lw=1.8, off=0.12):
    ax3.add_patch(FancyArrowPatch(p1, p2, arrowstyle="-|>", mutation_scale=12,
                                  color=color, lw=lw, ls=ls,
                                  shrinkA=2, shrinkB=2))
    if label:
        mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
        ax3.text(mx, my + off, label, fontsize=7.5, color=color, ha="center")


# nodes
box(3.6, 10.2, 2.8, 1.2, "Raspberry Pi 5\n(8 GB) — vision", fc="#f7d4df", ec=C_PI, tc=C_PI)
box(0.4, 7.6, 2.4, 1.1, "CAM A\nGlobal Shutter", fc="#dce8f7", ec=C_CAM, tc=C_CAM)
box(7.2, 7.6, 2.4, 1.1, "CAM B\nGlobal Shutter", fc="#eadcff", ec=C_CAMB, tc=C_CAMB)
box(3.6, 6.4, 2.8, 1.2, "Raspberry Pi Pico\n(timing sequencer)", fc="#e6e6e6", ec=C_PICO, tc=C_PICO)
box(3.7, 3.9, 2.6, 1.0, "IRLZ44N MOSFET", fc="#f3f3f3")
box(3.4, 1.7, 3.2, 1.1, "850 nm IR LED array\n(strobe)", fc="#fde0e0", ec=C_STROBE, tc=C_STROBE)
box(0.3, 3.9, 2.6, 1.0, "Impact sensor\n(piezo / mic)", fc="#eaf7ee", ec=C_GOLF, tc=C_GOLF)
box(7.3, 3.9, 2.4, 1.0, "12 V supply\n(LEDs)", fc="#f3f3f3")
box(7.3, 6.5, 2.4, 0.9, "5 V USB-C\n(Pi)", fc="#f3f3f3")

# wires
wire((1.6, 8.7), (4.2, 10.2), C_CAM, "CSI (CAM0)", off=0.15)
wire((8.4, 8.7), (5.8, 10.2), C_CAMB, "CSI (CAM1)", off=0.15)
wire((3.6, 7.2), (1.6, 7.6), C_PICO, "XTR trig\n(1.8V div)", off=0.18)   # pico->camA
wire((6.4, 7.2), (8.4, 7.6), C_PICO, "XTR trig\n(1.8V div)", off=0.18)   # pico->camB
wire((5.0, 6.4), (5.0, 4.9), C_PICO, "gate pulse", off=0.0)              # pico->mosfet
wire((5.0, 3.9), (5.0, 2.8), C_STROBE, "switch", off=0.0)                # mosfet->LED
wire((7.3, 4.4), (6.6, 2.6), "#333", "12V", off=0.0)                     # 12V->LED
wire((1.6, 4.9), (3.9, 6.4), C_GOLF, "strike\ntrigger", off=0.1)        # sensor->pico
wire((7.3, 6.95), (6.4, 10.6), "#333", "5V", off=0.0)                    # 5V->pi
ax3.text(5.0, 0.7, "One Pico clock fires BOTH shutters + the 5 strobe pulses\n"
         "→ flash k in CAM A == flash k in CAM B (enables pairing)",
         ha="center", fontsize=8.5, style="italic", color="#444")

plt.tight_layout(rect=[0, 0, 1, 0.96])
out = "docs/system_diagram.png"
plt.savefig(out, dpi=130, bbox_inches="tight")
print("wrote", out)
