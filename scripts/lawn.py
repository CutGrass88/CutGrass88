#!/usr/bin/env python3
"""Draws the lawn in the README: my last three months of GitHub contributions as a meadow.

Each day is a clump of grass, and more contributions make taller grass. While I keep
contributing, a mower drives across, cuts the lot and it grows back. If I stop, the
mower falls asleep, dandelions come up and the newest patch grows wild.

    python3 scripts/lawn.py --user CutGrass88 --out dist     (needs GITHUB_TOKEN)
    python3 scripts/lawn.py --data calendar.json --out dist  (use saved data instead)
    python3 scripts/lawn.py --data calendar.json --out dist --idle 9   (preview neglect)

Writes lawn.svg (light theme) and lawn-dark.svg (dark theme). The images contain no
scripts and load nothing from outside. Only the Python standard library is used.
"""

import argparse
import json
import math
import os
import random
import sys
import urllib.request
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

DAYS = 91                 # how many days the lawn covers
WIDTH, HEIGHT = 840, 280
GROUND = 196              # y of the soil line
LEFT, RIGHT = 78, 738     # the days are drawn between these x positions
DAY = (RIGHT - LEFT) / DAYS
TALLEST = 112             # height of the tallest grass, in pixels
STUBBLE = 6               # height grass is cut down to
PARKED = 30               # x of the mower when it is not driving
MOWER_SCALE = 1.3
DECK = 17 * MOWER_SCALE   # distance from the mower's back wheel to the middle of its deck
DRIVE = 830               # how far the mower drives, in pixels
CYCLE = 26                # seconds for one mow-and-regrow loop
DRIVE_FROM, DRIVE_TO = 0.04, 0.40   # the part of the loop the mower spends driving

MONO = 'ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace'

THEMES = {
    "lawn.svg": {
        "dark": False,
        "sky": ("#cfe8ff", "#f6fbff"), "edge": "#d0d7de",
        "text": "#1f2328", "dim": "#59636e", "accent": "#1a7f37",
        "greens": ["#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "stubble": "#7bd88f", "weed": "#9a8f1f",
        "ground": "#2f8f4e", "stripe": "#3fa55f", "soil": "#216e39", "puff": "#6e7781",
    },
    "lawn-dark.svg": {
        "dark": True,
        "sky": ("#0d1117", "#101c2c"), "edge": "#30363d",
        "text": "#c9d1d9", "dim": "#8b949e", "accent": "#3fb950",
        "greens": ["#0e4429", "#006d32", "#26a641", "#39d353"],
        "stubble": "#12512f", "weed": "#8a8a2b",
        "ground": "#0f3320", "stripe": "#15472c", "soil": "#0b2616", "puff": "#ffffff",
    },
}

QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar { weeks { contributionDays { date contributionCount } } }
    }
  }
}"""


def n(value):
    """Short number for SVG: 12.60 -> 12.6, 24.00 -> 24."""
    return f"{value:.1f}".rstrip("0").rstrip(".")


# ----------------------------------------------------------------------------- data

def fetch(login, token):
    request = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "User-Agent": "lawn-drawing-script"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def read_days(payload):
    """Turn GitHub's answer into [(date, count), ...] for the past year, oldest first."""
    if payload.get("errors"):
        raise SystemExit(f"GitHub returned an error: {payload['errors']}")
    weeks = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    days = [
        (date.fromisoformat(d["date"]), int(d["contributionCount"]))
        for week in weeks for d in week["contributionDays"]
    ]
    days.sort()
    if len(days) < DAYS:
        raise SystemExit(f"expected at least {DAYS} days of data, got {len(days)}")
    return days


def pretend_idle(days, idle):
    """For previews: slide the history back so the last contribution was `idle` days ago."""
    counts = [count for _, count in days]
    while counts and not counts[-1]:
        counts.pop()
    counts = ([0] * len(days) + counts + [0] * idle)[-len(days):]
    return [(day, count) for (day, _), count in zip(days, counts)]


def summarise(days):
    counts = [count for _, count in days]
    idle = next((i for i, count in enumerate(reversed(counts)) if count), DAYS)

    # A streak may still be alive if today has nothing yet but yesterday did.
    end = len(counts) - (1 if counts[-1] else 2)
    streak = 0
    while end - streak >= 0 and counts[end - streak]:
        streak += 1

    best = max(range(len(counts)), key=lambda i: counts[i])
    return {
        "idle": idle,                       # days since the last contribution
        "streak": streak,
        "week": sum(counts[-7:]),
        "best": best if counts[best] else None,
        "cap": max(max(counts), 30),        # keeps a quiet month from looking huge
    }


# -------------------------------------------------------------------------- drawing

def blade(x, height, lean, width, css):
    half, mid = width / 2, GROUND - height * 0.55
    return (
        f'<path class="{css}" d="M{n(x - half)} {GROUND}Q{n(x - half + lean * .35)} {n(mid)} '
        f'{n(x + lean)} {n(GROUND - height)}Q{n(x + half + lean * .35)} {n(mid)} {n(x + half)} {GROUND}z"/>'
    )


def clump(x, height, rng, classes):
    """Three blades of grass for one day."""
    out = []
    for offset, scale in ((-2.6, rng.uniform(.62, .85)), (2.6, rng.uniform(.62, .85)), (0, 1)):
        h = height * scale
        out.append(blade(x + offset + rng.uniform(-.6, .6), h, rng.uniform(-.13, .13) * h,
                         3.6, rng.choice(classes)))
    return "".join(out)


def day_x(i):
    return LEFT + (i + 0.5) * DAY


def grass(days, info, theme, rng):
    """All the grass, plus the number above the busiest day."""
    counts = [count for _, count in days]
    mowing = info["idle"] < 3
    last_active = DAYS - 1 - info["idle"]
    out = []

    for i, count in enumerate(counts):
        x = day_x(i)
        sway = f'style="animation-delay:-{n((i * 0.11) % 3.2)}s"'

        if count:
            height = 10 + (TALLEST - 10) * math.log1p(count) / math.log1p(info["cap"])
            level = min(3, int(4 * height / (TALLEST + 1)))
            blades = clump(x, height, rng, [f"g{level}", f"g{max(level - 1, 0)}"])
        elif i > last_active and not mowing:
            # Nothing has been cut here for a while: wild grass, tallest where it is oldest.
            age = DAYS - i
            height = min(5 + age * 2.4 + rng.uniform(0, 5), 52)
            blades = clump(x, height, rng, ["weed", "g0"])
        else:
            height = rng.uniform(4, 7)
            blades = clump(x, height, rng, ["stub"])

        inner = f'<g class="s" {sway}>{blades}</g>'
        if mowing and height > STUBBLE + 2:
            # Time this clump's cut to the moment the mower's deck reaches it.
            at = CYCLE * (DRIVE_FROM + (DRIVE_TO - DRIVE_FROM) * (x - PARKED - DECK) / DRIVE)
            out.append(f'<g class="cut" style="--k:{STUBBLE / height:.3f};'
                       f'animation-delay:{n(at)}s">{inner}</g>')
        else:
            out.append(inner)

    if info["best"] is not None:
        i = info["best"]
        height = 10 + (TALLEST - 10) * math.log1p(counts[i]) / math.log1p(info["cap"])
        x = min(max(day_x(i), LEFT + 10), RIGHT - 10)
        at = CYCLE * (DRIVE_FROM + (DRIVE_TO - DRIVE_FROM) * (day_x(i) - PARKED - DECK) / DRIVE)
        label = (f'<text x="{n(x)}" y="{n(GROUND - height - 7)}" text-anchor="middle" '
                 f'class="peak">{counts[i]}</text>')
        out.append(f'<g class="peakfade" style="animation-delay:{n(at)}s">{label}</g>'
                   if mowing else label)
    return "".join(out)


def dandelions(info, rng):
    idle = info["idle"]
    if idle < 3:
        return ""
    total = (idle - 1) * 2 if idle < 7 else min(6 + idle, 26)
    out = []
    for _ in range(total):
        x, height = rng.uniform(LEFT + 4, RIGHT - 4), rng.uniform(14, 34)
        top = GROUND - height
        gone_to_seed = idle >= 7 and rng.random() < min(0.25 + idle / 40, 0.8)
        if gone_to_seed:
            head = (f'<circle cx="{n(x)}" cy="{n(top)}" r="4" class="puff"/>'
                    f'<circle cx="{n(x)}" cy="{n(top)}" r="1.2" class="seed" '
                    f'style="animation-delay:-{n(rng.uniform(0, 7))}s"/>')
        else:
            head = (f'<circle cx="{n(x)}" cy="{n(top)}" r="3.2" class="flower"/>'
                    f'<circle cx="{n(x)}" cy="{n(top)}" r="1.3" class="heart"/>')
        out.append(f'<g class="s" style="animation-delay:-{n(rng.uniform(0, 3))}s">'
                   f'<path class="stem" d="M{n(x)} {GROUND}V{n(top)}"/>{head}</g>')
    return "".join(out)


def sky(theme, rng):
    if theme["dark"]:
        stars = "".join(
            f'<circle cx="{n(rng.uniform(16, WIDTH - 16))}" cy="{n(rng.uniform(12, 118))}" '
            f'r="{n(rng.uniform(.6, 1.4))}" class="star" '
            f'style="animation-duration:{n(rng.uniform(2.5, 6))}s;animation-delay:-{n(rng.uniform(0, 6))}s"/>'
            for _ in range(34)
        )
        moon = (f'<circle cx="786" cy="44" r="14" fill="#e6edf3"/>'
                f'<circle cx="792" cy="39" r="12" fill="{theme["sky"][0]}"/>')
        return stars + moon

    def cloud(x, y, scale, seconds):
        return (f'<g class="cloud" style="animation-duration:{seconds}s">'
                f'<g transform="translate({x} {y}) scale({scale})">'
                '<ellipse cx="0" cy="0" rx="26" ry="10"/><ellipse cx="-12" cy="-7" rx="13" ry="9"/>'
                '<ellipse cx="8" cy="-10" rx="16" ry="11"/></g></g>')

    sun = ('<circle cx="786" cy="44" r="27" fill="#f9c513" opacity=".22" class="halo"/>'
           '<circle cx="786" cy="44" r="16" fill="#f9c513"/>')
    return sun + cloud(150, 52, 1, 38) + cloud(452, 34, .8, 52) + cloud(640, 70, .6, 44)


def ground(info, theme):
    band = f'<rect x="0" y="{GROUND}" width="{WIDTH}" height="13" fill="{theme["ground"]}"/>'
    if info["idle"] < 3:  # fresh mowing stripes
        band += "".join(
            f'<path d="M{x} {GROUND}h22l-6 13h-22z" fill="{theme["stripe"]}"/>'
            for x in range(-10, WIDTH, 44)
        )
    return band + f'<rect x="0" y="{GROUND + 13}" width="{WIDTH}" height="3" fill="{theme["soil"]}"/>'


def months(days):
    out = []
    for i, (day, _) in enumerate(days):
        if day.day == 1 or i == 0:
            if i == 0 and days[0][0].day > 20:
                continue  # too little of this month is showing to label it
            x = day_x(i) - DAY / 2
            out.append(f'<path class="tick" d="M{n(x)} {GROUND + 20}v6"/>'
                       f'<text x="{n(x + 5)}" y="{GROUND + 27}" class="small">{day:%b}</text>')
    return "".join(out)


def sign(info):
    idle = info["idle"]
    if idle >= 7:
        top, bottom = "NEEDS MOWING", f"{idle} days"
    else:
        top = "LAST MOWED"
        bottom = "today" if idle == 0 else "yesterday" if idle == 1 else f"{idle} days ago"
    return (
        f'<rect x="783" y="150" width="6" height="{GROUND - 150}" fill="#5b3d1e"/>'
        '<rect x="744" y="118" width="84" height="38" rx="3" fill="#7a5230" stroke="#4a3018"/>'
        f'<text x="786" y="132" text-anchor="middle" class="signtop">{top}</text>'
        f'<text x="786" y="148" text-anchor="middle" class="signbottom">{escape(bottom)}</text>'
    )


def mower(info, theme):
    running = info["idle"] < 3
    wheel = ('<g class="{spin}"><circle r="{r}" fill="#21262d" stroke="#8b949e"/>'
             '<path d="M-{h} 0h{d}M0 -{h}v{d}" stroke="#8b949e"/></g>')

    def wheel_at(x, r):
        spin = "spin" if running else ""
        return (f'<g transform="translate({x} {-r - 0.5})">'
                + wheel.format(spin=spin, r=r, h=r - 1.5, d=2 * r - 3) + "</g>")

    lamp = ""
    if theme["dark"] and running:
        lamp = ('<path d="M35 -11L74 -19V-1z" fill="#f2cc60" opacity=".16"/>'
                '<circle cx="35" cy="-11" r="1.9" fill="#f2cc60"/>')
    clippings = "".join(
        f'<rect x="1" y="-11" width="2.4" height="2.4" rx=".6" class="clip" '
        f'style="animation-delay:-{n(i * 0.14)}s"/>' for i in range(5)
    ) if running else ""
    sleeping = "" if running else "".join(
        f'<text x="{12 + i * 7}" y="{-30 - i * 10}" class="zzz" '
        f'style="font-size:{9 + i * 2}px;animation-delay:{n(i * .6)}s">z</text>' for i in range(3)
    )
    body = (
        '<path d="M2 -12L-22 -36" stroke="#8b949e" stroke-width="2.6" stroke-linecap="round"/>'
        '<path d="M-27 -36h10" stroke="#c9d1d9" stroke-width="3.2" stroke-linecap="round"/>'
        f'{lamp}'
        '<rect x="0" y="-15" width="35" height="10" rx="3.5" fill="#da3633"/>'
        '<rect x="0" y="-9" width="35" height="4" rx="2" fill="#a40e26"/>'
        f'<g class="{"engine" if running else ""}"><rect x="10" y="-23" width="15" height="9" rx="2" fill="#30363d"/>'
        '<rect x="14" y="-26" width="7" height="3.5" rx="1" fill="#8b949e"/></g>'
        f'{wheel_at(5, 5.5)}{wheel_at(30, 4.5)}{clippings}{sleeping}'
    )
    return (f'<g transform="translate({PARKED} {GROUND})">'
            f'<g class="{"drive" if running else ""}"><g transform="scale({MOWER_SCALE})">{body}</g></g></g>')


def stats(days, info, theme):
    parts = [("this week ", "dim"), (str(info["week"]), "num"), ("   ·   ", "dim"),
             ("streak ", "dim"), (f'{info["streak"]} day{"" if info["streak"] == 1 else "s"}', "num")]
    if info["best"] is not None:
        best_day, best_count = days[info["best"]]
        parts += [("   ·   ", "dim"), ("busiest ", "dim"),
                  (f"{best_day.day} {best_day:%b} ({best_count})", "num")]
    spans = "".join(f'<tspan class="{css}">{escape(text)}</tspan>' for text, css in parts)
    return (f'<text x="{WIDTH / 2:.0f}" y="{HEIGHT - 18}" text-anchor="middle" class="stats" '
            f'xml:space="preserve">{spans}</text>')


def css(theme):
    g = theme["greens"]
    f1, f2 = DRIVE_FROM * 100, DRIVE_TO * 100
    return f"""
text{{font-family:{MONO}}}
.g0{{fill:{g[0]}}}.g1{{fill:{g[1]}}}.g2{{fill:{g[2]}}}.g3{{fill:{g[3]}}}
.stub{{fill:{theme["stubble"]}}}.weed{{fill:{theme["weed"]}}}
.stem{{stroke:{g[1]};stroke-width:1.2}}.flower{{fill:#f2cc60}}.heart{{fill:#d29922}}
.puff{{fill:#fff;fill-opacity:.8;stroke:{theme["puff"]};stroke-dasharray:1 1.6}}
.seed{{fill:{theme["puff"]};animation:seed 7s linear infinite}}
.star{{fill:#c9d1d9;animation:twinkle 4s ease-in-out infinite alternate}}
.cloud{{fill:#fff;fill-opacity:.9;animation:drift 40s ease-in-out infinite alternate}}
.halo{{transform-box:fill-box;transform-origin:center;animation:halo 5s ease-in-out infinite alternate}}
.small{{font-size:10px;fill:{theme["dim"]}}}.tick{{stroke:{theme["dim"]};stroke-opacity:.6}}
.stats{{font-size:12px}}.dim{{fill:{theme["dim"]}}}.num{{fill:{theme["accent"]};font-weight:600}}
.peak{{font-size:10px;font-weight:700;fill:{theme["accent"]}}}
.signtop{{font-size:7.5px;letter-spacing:.6px;fill:#e8d9bf}}.signbottom{{font-size:11.5px;font-weight:700;fill:#fff6e5}}
.zzz{{fill:{theme["dim"]};font-weight:700;opacity:0;animation:zzz 3s ease-in-out infinite}}
.s,.cut{{transform-box:fill-box;transform-origin:50% 100%}}
.s{{animation:sway 3.2s ease-in-out infinite alternate}}
.cut{{animation:cut {CYCLE}s linear infinite}}
.peakfade{{animation:peakfade {CYCLE}s linear infinite}}
.drive{{animation:drive {CYCLE}s linear infinite}}
.engine{{animation:engine .12s linear infinite alternate}}
.spin{{animation:spin .5s linear infinite}}
.clip{{fill:{g[2]};animation:clip .7s ease-out infinite}}
@keyframes sway{{from{{transform:skewX(-3.5deg)}}to{{transform:skewX(3.5deg)}}}}
@keyframes cut{{0%{{transform:scaleY(1)}}.6%{{transform:scaleY(var(--k))}}46%{{transform:scaleY(var(--k));animation-timing-function:cubic-bezier(.2,.8,.3,1)}}60%,100%{{transform:scaleY(1)}}}}
@keyframes peakfade{{0%{{opacity:1}}.6%,56%{{opacity:0}}62%,100%{{opacity:1}}}}
@keyframes drive{{0%,{n(f1)}%{{transform:translateX(0);opacity:1}}{n(f2)}%{{transform:translateX({DRIVE}px);opacity:1}}{n(f2 + .1)}%,90%{{transform:translateX({DRIVE}px);opacity:0}}90.1%{{transform:translateX(0);opacity:0}}96%,100%{{transform:translateX(0);opacity:1}}}}
@keyframes engine{{to{{transform:translateY(-.7px)}}}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
@keyframes clip{{from{{transform:translate(0,0);opacity:1}}to{{transform:translate(-20px,-17px) rotate(140deg);opacity:0}}}}
@keyframes twinkle{{from{{opacity:.2}}to{{opacity:1}}}}
@keyframes drift{{from{{transform:translateX(-18px)}}to{{transform:translateX(18px)}}}}
@keyframes halo{{from{{transform:scale(.9)}}to{{transform:scale(1.12)}}}}
@keyframes seed{{0%{{transform:translate(0,0);opacity:0}}10%{{opacity:.9}}100%{{transform:translate(70px,-46px);opacity:0}}}}
@keyframes zzz{{0%{{opacity:0;transform:translateY(4px)}}40%{{opacity:1}}100%{{opacity:0;transform:translateY(-7px)}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
"""


def draw(days, info, theme):
    # The same seed every run for the same data, so the picture only changes when the data does.
    rng = random.Random(f"{days[0][0]}:{days[-1][0]}:{info['idle']}")
    if info["idle"] >= 7:
        mowed = f"needs mowing, {info['idle']} days since the last contribution"
    else:
        mowed = "last mowed " + ("today" if info["idle"] == 0 else
                                 "yesterday" if info["idle"] == 1 else f"{info['idle']} days ago")
    label = (f"My last {DAYS} days of GitHub contributions drawn as grass, taller for busier days. "
             f"Lawn {mowed}. This week {info['week']}, streak {info['streak']} days.")
    top, bottom = theme["sky"]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" width="{WIDTH}" height="{HEIGHT}" role="img" aria-label="{escape(label)}">
<title>{escape(label)}</title>
<style>{css(theme)}</style>
<defs>
<linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{top}"/><stop offset=".72" stop-color="{bottom}"/></linearGradient>
<clipPath id="card"><rect x=".5" y=".5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="10"/></clipPath>
</defs>
<g clip-path="url(#card)">
<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#sky)"/>
{sky(theme, rng)}
{sign(info)}
{grass(days, info, theme, rng)}
{dandelions(info, rng)}
{ground(info, theme)}
{mower(info, theme)}
{months(days)}
{stats(days, info, theme)}
</g>
<rect x=".5" y=".5" width="{WIDTH - 1}" height="{HEIGHT - 1}" rx="10" fill="none" stroke="{theme["edge"]}"/>
</svg>
'''


# ----------------------------------------------------------------------------- main

def main():
    parser = argparse.ArgumentParser(description="Draw the README lawn.")
    parser.add_argument("--user", default=os.environ.get("GITHUB_REPOSITORY_OWNER"))
    parser.add_argument("--data", type=Path, help="saved GitHub answer to use instead of fetching")
    parser.add_argument("--out", type=Path, default=Path("dist"))
    parser.add_argument("--idle", type=int, help="preview: pretend the last contribution was N days ago")
    args = parser.parse_args()

    if args.data:
        payload = json.loads(args.data.read_text(encoding="utf-8"))
    else:
        token = os.environ.get("GITHUB_TOKEN")
        if not (args.user and token):
            sys.exit("need --user and the GITHUB_TOKEN environment variable, or --data")
        payload = fetch(args.user, token)

    days = read_days(payload)
    if args.idle is not None:
        days = pretend_idle(days, args.idle)
    days = days[-DAYS:]
    info = summarise(days)

    args.out.mkdir(parents=True, exist_ok=True)
    for name, theme in THEMES.items():
        (args.out / name).write_text(draw(days, info, theme), encoding="utf-8")
    print(f"drew {DAYS} days up to {days[-1][0]}: idle {info['idle']}, "
          f"streak {info['streak']}, this week {info['week']}")


if __name__ == "__main__":
    main()
