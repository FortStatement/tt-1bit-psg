import json
import re
import sys
from collections import Counter, deque

RUN = "runs/wokwi/final"
CELLS_JSON = "runs/cells.json"
OUT_SVG = "runs/layout_annotated.svg"
OUT_PNG = "runs/layout_annotated.png"

RING_FIELDS = [
    (35, 46, "voice state: freq"),
    (32, 34, "voice state: octave"),
    (24, 31, "voice state: wave/duty/vol"),
    (4, 23, "voice state: phase acc"),
    (0, 3, "voice state: noise S&H"),
]


def register_block(net):
    name = net.replace("\\", "").strip()
    m = re.match(r"ring\[(\d+)\]\[(\d+)\]", name)
    if m:
        bit = int(m.group(2))
        for lo, hi, block in RING_FIELDS:
            if lo <= bit <= hi:
                return block
    if name.startswith("head_oct"):
        return "voice state: octave"
    if name.startswith(("sd_acc", "audio")):
        return "sigma-delta"
    if name.startswith("lfsr"):
        return "noise LFSR"
    if name.startswith(("rot", "slot")):
        return "ring slot / octave prescaler"
    if name.startswith(("freq_lo", "wr_sync", "we")):
        return "register bus"
    if name.startswith("uo_out"):
        return "pulse outputs"
    return "other"


def extract():
    import odb

    db = odb.dbDatabase.create()
    odb.read_db(db, f"{RUN}/odb/tt_um_fortstatement_onebit_psg.odb")
    block = db.getChip().getBlock()
    die = block.getDieArea()
    dbu = block.getDbUnitsPerMicron()

    cells = {}
    drives = {}
    for inst in block.getInsts():
        master = inst.getMaster().getName()
        box = inst.getBBox()
        cell = {
            "master": master,
            "box": [box.xMin() / dbu, box.yMin() / dbu, box.xMax() / dbu, box.yMax() / dbu],
            "block": None,
        }
        name = inst.getName()
        sinks = []
        for it in inst.getITerms():
            net = it.getNet()
            if net is None or not it.isOutputSignal():
                continue
            if "__df" in master and it.getMTerm().getName() == "Q":
                cell["block"] = register_block(net.getName())
            for sink in net.getITerms():
                if sink.isInputSignal() and sink.getInst().getName() != name:
                    sinks.append(sink.getInst().getName())
        if master.startswith(("sky130_fd_sc_hd__clkbuf", "sky130_fd_sc_hd__clkinv")) and "clknet" in "".join(
            it.getNet().getName() for it in inst.getITerms() if it.getNet() is not None
        ):
            cell["block"] = "clock tree"
        elif re.search(r"__(fill|decap|tapvpwrvgnd|diode)", master):
            cell["block"] = "filler / tap / decap"
        cells[name] = cell
        drives[name] = sinks

    for name, cell in cells.items():
        if cell["block"] is not None:
            continue
        seen = {name}
        queue = deque(drives[name])
        found = Counter()
        while queue and sum(found.values()) < 8:
            n = queue.popleft()
            if n in seen:
                continue
            seen.add(n)
            c = cells[n]
            if "__df" in c["master"]:
                found[c["block"]] += 1
            else:
                queue.extend(drives[n])
        if found:
            cell["block"] = "logic → " + found.most_common(1)[0][0]
        else:
            cell["block"] = "logic → pins"

    with open(CELLS_JSON, "w") as f:
        json.dump({"die": [die.xMin() / dbu, die.yMin() / dbu, die.xMax() / dbu, die.yMax() / dbu],
                   "cells": list(cells.values())}, f)


GROUPS = [
    ("Voice ring: phase accumulators", "#e6194b", ["voice state: phase acc"]),
    ("Voice ring: freq + octave", "#f58231", ["voice state: freq", "voice state: octave"]),
    ("Voice ring: wave/duty/vol", "#ffe119", ["voice state: wave/duty/vol"]),
    ("Voice ring: noise sample", "#bfef45", ["voice state: noise S&H"]),
    ("Shared voice logic (adder, write muxes, reset)", "#ff9fb0",
     ["logic → voice state: phase acc", "logic → voice state: freq", "logic → voice state: octave",
      "logic → voice state: wave/duty/vol", "logic → voice state: noise S&H"]),
    ("Waveform × volume + sigma-delta", "#4363d8", ["sigma-delta", "logic → sigma-delta"]),
    ("Noise LFSR", "#3cb44b", ["noise LFSR", "logic → noise LFSR"]),
    ("Ring slot / octave prescaler", "#911eb4", ["ring slot / octave prescaler", "logic → ring slot / octave prescaler"]),
    ("Register bus", "#42d4f4", ["register bus", "logic → register bus"]),
    ("Pulse outputs + pin buffers", "#f032e6", ["pulse outputs", "logic → pulse outputs", "logic → pins"]),
    ("Clock tree", "#ffffff", ["clock tree"]),
]


def draw():
    data = json.load(open(CELLS_JSON))
    x0, y0, x1, y1 = data["die"]
    colour = {}
    for label, c, blocks in GROUPS:
        for b in blocks:
            colour[b] = (label, c)

    px_per_um = 8
    w, h = (x1 - x0) * px_per_um, (y1 - y0) * px_per_um
    pad, legend_h = 24, 150
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w + 2 * pad:.0f}" height="{h + 2 * pad + legend_h + 40:.0f}" '
        f'font-family="DejaVu Sans, sans-serif">',
        '<rect width="100%" height="100%" fill="#14213d"/>',
        f'<text x="{pad}" y="{pad + 8}" fill="#fff" font-size="20">tt_um_fortstatement_onebit_psg — SKY130 1x1 tile '
        f'({x1 - x0:.0f} × {y1 - y0:.0f} µm), cells by function</text>',
        f'<g transform="translate({pad},{pad + 30})">',
        f'<rect width="{w:.1f}" height="{h:.1f}" fill="#1d2b4f" stroke="#c9d1e6"/>',
    ]
    area = Counter()
    for cell in data["cells"]:
        bx0, by0, bx1, by1 = cell["box"]
        label, c = colour.get(cell["block"], (None, "#555b6e"))
        if label:
            area[label] += (bx1 - bx0) * (by1 - by0)
        out.append(
            f'<rect x="{(bx0 - x0) * px_per_um:.1f}" y="{(y1 - by1) * px_per_um:.1f}" '
            f'width="{(bx1 - bx0) * px_per_um:.1f}" height="{(by1 - by0) * px_per_um:.1f}" fill="{c}" '
            f'fill-opacity="{0.95 if label else 0.35}" stroke="#14213d" stroke-width="0.4"/>'
        )
    out.append("</g>")

    entries = [(f"{label} ({area[label]:.0f} µm²)", c, 1) for label, c, _ in GROUPS if area[label]]
    entries.append(("Filler / tap / decap", "#555b6e", 0.35))
    col_w = (w + 2 * pad) / 3
    for i, (text, c, op) in enumerate(entries):
        x = pad + (i % 3) * col_w
        y = pad + 30 + h + 24 + (i // 3) * 26
        out.append(f'<rect x="{x:.0f}" y="{y:.0f}" width="16" height="16" fill="{c}" fill-opacity="{op}"/>')
        out.append(f'<text x="{x + 24:.0f}" y="{y + 13:.0f}" fill="#e8ecf6" font-size="14">{text}</text>')
    out.append("</svg>")
    with open(OUT_SVG, "w") as f:
        f.write("\n".join(out))

    import cairosvg

    cairosvg.svg2png(url=OUT_SVG, write_to=OUT_PNG)


if __name__ == "__main__":
    {"extract": extract, "draw": draw}[sys.argv[-1]]()
