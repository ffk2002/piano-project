#!/usr/bin/env python3
"""
Read the "amplitude,db,freq_hz" CSV written by audio::processer_thread
(readings.csv, created in the directory `cargo run` is invoked from) and
render a self-contained HTML chart with three panels: amplitude over time,
dB level over time, and dominant frequency over time.

Usage:
    cargo run --release      # writes readings.csv as it captures
    python3 scripts/plot_readings.py readings.csv -o chart.html

No third-party dependencies (stdlib only) - the output is a single HTML
file with the data inlined, viewable directly in a browser.
"""

import argparse
import csv
import json
import sys

CHART_TEMPLATE = """<title>Mic Capture Readings</title>
<style>
.viz-root {{
  color-scheme: light;
  --surface-1:      #fcfcfb;
  --page:           #f9f9f7;
  --text-primary:   #0b0b0b;
  --text-secondary: #52514e;
  --text-muted:     #898781;
  --grid:           #e1e0d9;
  --baseline:       #c3c2b7;
  --series-1:       #2a78d6;
  --border:         rgba(11,11,11,0.10);
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) .viz-root {{
    color-scheme: dark;
    --surface-1:      #1a1a19;
    --page:           #0d0d0d;
    --text-primary:   #ffffff;
    --text-secondary: #c3c2b7;
    --text-muted:     #898781;
    --grid:           #2c2c2a;
    --baseline:       #383835;
    --series-1:       #3987e5;
    --border:         rgba(255,255,255,0.10);
  }}
}}
:root[data-theme="dark"] .viz-root {{
  color-scheme: dark;
  --surface-1:      #1a1a19;
  --page:           #0d0d0d;
  --text-primary:   #ffffff;
  --text-secondary: #c3c2b7;
  --text-muted:     #898781;
  --grid:           #2c2c2a;
  --baseline:       #383835;
  --series-1:       #3987e5;
  --border:         rgba(255,255,255,0.10);
}}

* {{ box-sizing: border-box; }}
body {{ margin: 0; }}
.viz-root {{
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  background: var(--page);
  color: var(--text-primary);
  padding: 32px 24px;
  min-height: 100vh;
}}
.wrap {{ max-width: 900px; margin: 0 auto; }}
h1 {{ font-size: 20px; font-weight: 600; margin: 0 0 4px; }}
.subtitle {{ font-size: 13px; color: var(--text-secondary); margin: 0 0 24px; }}
.panel {{
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 18px 20px 14px;
  margin-bottom: 20px;
}}
.panel h2 {{ font-size: 14px; font-weight: 600; margin: 0 0 2px; }}
.panel .desc {{ font-size: 12px; color: var(--text-muted); margin: 0 0 12px; }}
svg {{ display: block; width: 100%; height: auto; overflow: visible; }}
.axis-label {{ font-size: 10px; fill: var(--text-muted); }}
.gridline {{ stroke: var(--grid); stroke-width: 1; shape-rendering: crispEdges; }}
.baseline {{ stroke: var(--baseline); stroke-width: 1; shape-rendering: crispEdges; }}
.series-line {{ fill: none; stroke: var(--series-1); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }}
.hover-line {{ stroke: var(--text-muted); stroke-width: 1; opacity: 0; pointer-events: none; }}
.hover-dot {{ fill: var(--series-1); stroke: var(--surface-1); stroke-width: 2; opacity: 0; pointer-events: none; }}
.hit-rect {{ fill: transparent; cursor: crosshair; }}
.tooltip {{
  position: absolute;
  pointer-events: none;
  background: var(--surface-1);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 12px;
  color: var(--text-primary);
  box-shadow: 0 2px 8px rgba(0,0,0,0.15);
  opacity: 0;
  transform: translate(-50%, -100%);
  white-space: nowrap;
}}
.tooltip .row {{ display: flex; gap: 8px; justify-content: space-between; }}
.tooltip .label {{ color: var(--text-muted); }}
.footer-note {{ font-size: 11px; color: var(--text-muted); margin-top: 4px; }}
</style>

<div class="viz-root">
  <div class="wrap">
    <h1>Microphone capture readings</h1>
    <p class="subtitle">{n_total:,} rows parsed from {source} &middot; showing every {step}th row ({n_plotted:,} points plotted)</p>

    <div class="panel">
      <h2>Amplitude</h2>
      <p class="desc">Raw sample value, range &minus;1.0 to 1.0</p>
      <div class="chart-container" data-chart="amp"></div>
    </div>

    <div class="panel">
      <h2>Level (dB)</h2>
      <p class="desc">20 &times; log10(|amplitude|), dBFS &mdash; 0 dB = full scale</p>
      <div class="chart-container" data-chart="db"></div>
    </div>

    <div class="panel">
      <h2>Dominant frequency</h2>
      <p class="desc">Peak FFT bin per completed 2048-sample window &mdash; points appear only on rows where a window finished ({n_freq_points:,} of {n_total:,} rows), so the line connects real readings with visible gaps in between rather than interpolating every row.</p>
      <div class="chart-container" data-chart="freq"></div>
    </div>

    <p class="footer-note">Source: parsed "amplitude,db,freq_hz" rows from readings.csv, written by audio::processer_thread.</p>
  </div>
</div>
<div class="tooltip" id="tooltip"></div>

<script>
const AMP_POINTS = {amp_points_js};
const DB_POINTS = {db_points_js};
const FREQ_POINTS = {freq_points_js};

function niceTicks(min, max, count) {{
  const range = max - min || 1;
  const rawStep = range / count;
  const mag = Math.pow(10, Math.floor(Math.log10(rawStep)));
  const norm = rawStep / mag;
  let niceStep;
  if (norm < 1.5) niceStep = 1 * mag;
  else if (norm < 3) niceStep = 2 * mag;
  else if (norm < 7) niceStep = 5 * mag;
  else niceStep = 10 * mag;
  const ticks = [];
  const start = Math.ceil(min / niceStep) * niceStep;
  for (let v = start; v <= max + 1e-9; v += niceStep) ticks.push(Math.round(v * 1e6) / 1e6);
  return ticks;
}}

// points: array of [x, y] pairs, x strictly increasing but not necessarily
// evenly spaced (dense for amplitude/db, sparse for frequency).
function renderChart(container, points, opts) {{
  const W = 820, H = 220;
  const marginL = 46, marginR = 12, marginT = 10, marginB = 26;
  const plotW = W - marginL - marginR;
  const plotH = H - marginT - marginB;

  const xs = points.map(p => p[0]);
  const ys = points.map(p => p[1]);
  const xMin = xs[0], xMax = xs[xs.length - 1];
  const dataMin = Math.min(...ys);
  const dataMax = Math.max(...ys);
  const pad = (dataMax - dataMin) * 0.08 || 1;
  const yMin = opts.yFloor !== undefined ? Math.max(opts.yFloor, dataMin - pad) : dataMin - pad;
  const yMax = dataMax + pad;

  const xFor = x => marginL + ((x - xMin) / ((xMax - xMin) || 1)) * plotW;
  const yFor = v => marginT + plotH - ((v - yMin) / (yMax - yMin)) * plotH;

  const yTicks = niceTicks(yMin, yMax, 5);
  const xTickCount = 6;
  const xTicks = [];
  for (let k = 0; k <= xTickCount; k++) xTicks.push(Math.round(xMin + (k / xTickCount) * (xMax - xMin)));

  let path = "";
  points.forEach(([x, y], i) => {{
    const px = xFor(x), py = yFor(y);
    path += (i === 0 ? "M" : "L") + px.toFixed(2) + "," + py.toFixed(2) + " ";
  }});

  const svgNS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(svgNS, "svg");
  svg.setAttribute("viewBox", `0 0 ${{W}} ${{H}}`);

  for (const t of yTicks) {{
    const y = yFor(t);
    const line = document.createElementNS(svgNS, "line");
    line.setAttribute("class", "gridline");
    line.setAttribute("x1", marginL); line.setAttribute("x2", W - marginR);
    line.setAttribute("y1", y); line.setAttribute("y2", y);
    svg.appendChild(line);
    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("class", "axis-label");
    label.setAttribute("x", marginL - 8);
    label.setAttribute("y", y + 3);
    label.setAttribute("text-anchor", "end");
    label.textContent = opts.fmtY ? opts.fmtY(t) : t;
    svg.appendChild(label);
  }}

  const baseline = document.createElementNS(svgNS, "line");
  baseline.setAttribute("class", "baseline");
  baseline.setAttribute("x1", marginL); baseline.setAttribute("x2", W - marginR);
  baseline.setAttribute("y1", marginT + plotH); baseline.setAttribute("y2", marginT + plotH);
  svg.appendChild(baseline);

  for (const xVal of xTicks) {{
    const x = xFor(xVal);
    const label = document.createElementNS(svgNS, "text");
    label.setAttribute("class", "axis-label");
    label.setAttribute("x", x);
    label.setAttribute("y", H - 6);
    label.setAttribute("text-anchor", xVal === xMin ? "start" : (xVal === xMax ? "end" : "middle"));
    label.textContent = "#" + xVal;
    svg.appendChild(label);
  }}

  const linePath = document.createElementNS(svgNS, "path");
  linePath.setAttribute("class", "series-line");
  linePath.setAttribute("d", path);
  svg.appendChild(linePath);

  const hoverLine = document.createElementNS(svgNS, "line");
  hoverLine.setAttribute("class", "hover-line");
  hoverLine.setAttribute("y1", marginT); hoverLine.setAttribute("y2", marginT + plotH);
  svg.appendChild(hoverLine);

  const hoverDot = document.createElementNS(svgNS, "circle");
  hoverDot.setAttribute("class", "hover-dot");
  hoverDot.setAttribute("r", 4);
  svg.appendChild(hoverDot);

  const hitRect = document.createElementNS(svgNS, "rect");
  hitRect.setAttribute("class", "hit-rect");
  hitRect.setAttribute("x", marginL); hitRect.setAttribute("y", marginT);
  hitRect.setAttribute("width", plotW); hitRect.setAttribute("height", plotH);
  svg.appendChild(hitRect);

  container.appendChild(svg);

  const tooltip = document.getElementById("tooltip");
  hitRect.addEventListener("mousemove", (ev) => {{
    const rect = svg.getBoundingClientRect();
    const scale = W / rect.width;
    const mx = (ev.clientX - rect.left) * scale;
    const targetX = xMin + ((mx - marginL) / plotW) * (xMax - xMin);
    // nearest point by x, since points aren't necessarily evenly spaced
    let nearest = 0;
    let best = Infinity;
    for (let i = 0; i < points.length; i++) {{
      const d = Math.abs(points[i][0] - targetX);
      if (d < best) {{ best = d; nearest = i; }}
    }}
    const [px, py] = points[nearest];
    const sx = xFor(px), sy = yFor(py);
    hoverLine.setAttribute("x1", sx); hoverLine.setAttribute("x2", sx);
    hoverLine.setAttribute("opacity", 1);
    hoverDot.setAttribute("cx", sx); hoverDot.setAttribute("cy", sy);
    hoverDot.setAttribute("opacity", 1);
    tooltip.style.opacity = 1;
    tooltip.style.left = ev.clientX + "px";
    tooltip.style.top = (ev.clientY - 12) + "px";
    tooltip.innerHTML = `<div class="row"><span class="label">row</span><span>#${{px}}</span></div>` +
      `<div class="row"><span class="label">${{opts.label}}</span><span>${{opts.fmtY ? opts.fmtY(py) : py}}</span></div>`;
  }});
  hitRect.addEventListener("mouseleave", () => {{
    hoverLine.setAttribute("opacity", 0);
    hoverDot.setAttribute("opacity", 0);
    tooltip.style.opacity = 0;
  }});
}}

renderChart(document.querySelector('[data-chart="amp"]'), AMP_POINTS, {{
  label: "amplitude",
  fmtY: v => v.toFixed(3),
}});
renderChart(document.querySelector('[data-chart="db"]'), DB_POINTS, {{
  label: "level",
  fmtY: v => v.toFixed(1) + " dB",
}});
renderChart(document.querySelector('[data-chart="freq"]'), FREQ_POINTS, {{
  label: "frequency",
  fmtY: v => v.toFixed(1) + " Hz",
}});
</script>
"""


def parse_readings(path):
    amps, dbs, freq_points = [], [], []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            amps.append(float(row["amplitude"]))
            dbs.append(float(row["db"]))
            raw_freq = (row.get("freq_hz") or "").strip()
            if raw_freq:
                freq_points.append((i, float(raw_freq)))

    freq_points=freq_points[1:]
    return amps, dbs, freq_points


def downsample(values, max_points):
    step = max(1, len(values) // max_points)
    return values[::step], step


def downsample_points(points, max_points):
    step = max(1, len(points) // max_points)
    return points[::step]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="path to readings.csv written by audio::processer_thread")
    parser.add_argument("-o", "--output", default="chart.html", help="output HTML file path")
    parser.add_argument("--max-points", type=int, default=3000, help="max points to plot per series")
    args = parser.parse_args()

    amps, dbs, freq_points = parse_readings(args.input)
    if not amps:
        sys.exit(f"no rows found in {args.input}")

    ds_amps, step = downsample(amps, args.max_points)
    ds_dbs, _ = downsample(dbs, args.max_points)
    ds_freq_points = downsample_points(freq_points, args.max_points)

    amp_points = [[i, v] for i, v in enumerate(ds_amps)]
    db_points = [[i, v] for i, v in enumerate(ds_dbs)]

    if not ds_freq_points:
        sys.exit(f"no freq_hz readings found in {args.input} (no FFT window completed during capture)")

    html = CHART_TEMPLATE.format(
        n_total=len(amps),
        source=args.input,
        step=step,
        n_plotted=len(ds_amps),
        n_freq_points=len(freq_points),
        amp_points_js=json.dumps(amp_points),
        db_points_js=json.dumps(db_points),
        freq_points_js=json.dumps(ds_freq_points),
    )

    with open(args.output, "w") as f:
        f.write(html)

    print(f"parsed {len(amps):,} rows from {args.input} ({len(freq_points):,} with a frequency reading)")
    print(f"plotted {len(ds_amps):,} amplitude/db points and {len(ds_freq_points):,} frequency points to {args.output}")


if __name__ == "__main__":
    main()
