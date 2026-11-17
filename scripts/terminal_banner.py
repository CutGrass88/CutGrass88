#!/usr/bin/env python3
"""Draws assets/terminal.svg, the animated terminal banner at the top of the README.

Edit SESSION below, then run:  python3 scripts/terminal_banner.py

The SVG has no scripts and loads nothing from outside, so GitHub shows it as a
normal image. The typing is CSS animation only. Anyone who has asked their
system for reduced motion gets the finished text with no animation.
"""

from pathlib import Path
from xml.sax.saxutils import escape

# Each entry is one command and the output it prints.
# Output is a list of (text, colour) pieces. Colours: text, dim, green, blue, yellow.
SESSION = [
    ("whoami", [
        ("cs student @ durham university", "text"), ("  ·  ", "dim"),
        ("security and backend engineering", "text"),
    ]),
    ("cat focus.txt", [
        ("detection rules", "text"), (" · ", "dim"), ("log analysis", "text"), (" · ", "dim"),
        ("packet analysis", "text"), (" · ", "dim"), ("network enumeration", "text"),
    ]),
    ("ls labs/", [
        ("hackthebox/", "blue"), ("   ", "text"), ("overthewire/", "blue"), ("   ", "text"),
        ("ctfs/", "blue"),
    ]),
    ("./mow.sh --lawn contributions", "BAR"),
]

USER, HOST = "cutgrass", "durham"
BAR_CELLS = 24
BAR_DONE = [("100%", "green"), ("  lawn trimmed", "dim")]

# Layout, in pixels.
WIDTH = 720
CHAR = 8.4            # width of one monospace character at this font size
FONT = 14
LEFT = 24             # left edge of the text
FIRST_LINE = 72       # baseline of the first line
LINE = 24             # distance between lines
TITLE_BAR = 36

# Timing, in seconds.
START = 0.7
PER_CHAR = 0.055
AFTER_COMMAND = 0.35
AFTER_OUTPUT = 0.55
BAR_TIME = 1.3

COLOURS = {
    "bg": "#0d1117", "bar": "#161b22", "edge": "#30363d",
    "text": "#c9d1d9", "dim": "#8b949e", "green": "#3fb950",
    "blue": "#58a6ff", "yellow": "#d29922",
}

PROMPT = [(f"{USER}@{HOST}", "green"), (":", "text"), ("~", "blue"), ("$", "text")]
PROMPT_CHARS = sum(len(t) for t, _ in PROMPT) + 1  # plus the space after "$"


def n(value):
    """Short number for SVG attributes: 12.60 -> 12.6, 24.00 -> 24."""
    return f"{value:.2f}".rstrip("0").rstrip(".")


def pieces(parts, col, y):
    """Coloured text pieces starting at character column `col`. Returns (svg, next column)."""
    out = []
    for text, colour in parts:
        if text.strip():
            # textLength pins the width, so every font lines up on the same grid.
            out.append(
                f'<text x="{n(LEFT + col * CHAR)}" y="{y}" class="{colour}" '
                f'textLength="{n(len(text) * CHAR)}" xml:space="preserve">{escape(text)}</text>'
            )
        col += len(text)
    return "".join(out), col


def show(at):
    return f'style="animation:show .01s linear {n(at)}s both"'


def cover(col, chars, y, at, duration):
    """A background-coloured block that shrinks to the right, uncovering one character at a time."""
    return (
        f'<rect class="cover" x="{n(LEFT + col * CHAR - 0.5)}" y="{y - 14}" '
        f'width="{n(chars * CHAR + 1)}" height="20" '
        f'style="animation:type {n(duration)}s steps({chars},end) {n(at)}s both"/>'
    )


def build():
    body = []
    t = START
    y = FIRST_LINE

    for command, output in SESSION:
        typing = len(command) * PER_CHAR
        done = t + typing + AFTER_COMMAND

        prompt_svg, col = pieces(PROMPT, 0, y)
        command_svg, _ = pieces([(command, "text")], PROMPT_CHARS, y)
        cursor = (
            f'<rect class="cursor typing" x="{n(LEFT + PROMPT_CHARS * CHAR)}" y="{y - 13}" '
            f'width="{n(CHAR)}" height="17" '
            f'style="--w:{n(len(command) * CHAR)}px;animation:show .01s linear {n(t)}s both,'
            f'move {n(typing)}s steps({len(command)},end) {n(t)}s both,'
            f'hide .01s linear {n(done)}s forwards"/>'
        )
        body.append(
            f'<g {show(t)}>{prompt_svg}{command_svg}'
            f'{cover(PROMPT_CHARS, len(command), y, t, typing)}{cursor}</g>'
        )
        t = done
        y += LINE

        if output == "BAR":
            bar_svg, col = pieces([("[", "dim"), ("#" * BAR_CELLS, "green"), ("]", "dim")], 0, y)
            done_svg, _ = pieces(BAR_DONE, col + 1, y)
            body.append(
                f'<g {show(t)}>{bar_svg}{cover(1, BAR_CELLS, y, t, BAR_TIME)}</g>'
                f'<g {show(t + BAR_TIME + 0.1)}>{done_svg}</g>'
            )
            t += BAR_TIME + 0.1
        else:
            output_svg, _ = pieces(output, 0, y)
            body.append(f'<g {show(t)}>{output_svg}</g>')
        t += AFTER_OUTPUT
        y += LINE

    # The last prompt, waiting with a blinking cursor.
    prompt_svg, _ = pieces(PROMPT, 0, y)
    body.append(
        f'<g {show(t)}>{prompt_svg}'
        f'<rect class="cursor" x="{n(LEFT + PROMPT_CHARS * CHAR)}" y="{y - 13}" '
        f'width="{n(CHAR)}" height="17" '
        f'style="animation:blink 1.1s steps(1,end) {n(t)}s infinite"/></g>'
    )

    height = y + 26
    c = COLOURS
    title = f"{USER}@{HOST}: ~"
    summary = "Terminal session: " + "; ".join(
        f"{command}: " + ("lawn trimmed" if out == "BAR" else "".join(p for p, _ in out))
        for command, out in SESSION
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" width="{WIDTH}" height="{height}" role="img" aria-label="{escape(summary)}">
<title>{escape(title)}</title>
<style>
text{{font:{FONT}px ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace}}
.text{{fill:{c["text"]}}}.dim{{fill:{c["dim"]}}}.green{{fill:{c["green"]}}}.blue{{fill:{c["blue"]}}}.yellow{{fill:{c["yellow"]}}}
.cover{{fill:{c["bg"]};transform-box:fill-box;transform-origin:right center;transform:scaleX(0)}}
.cursor{{fill:{c["text"]}}}.typing{{opacity:0}}
@keyframes show{{from{{opacity:0}}to{{opacity:1}}}}
@keyframes hide{{from{{opacity:0}}to{{opacity:0}}}}
@keyframes type{{from{{transform:scaleX(1)}}to{{transform:scaleX(0)}}}}
@keyframes move{{from{{transform:translateX(0)}}to{{transform:translateX(var(--w))}}}}
@keyframes blink{{0%{{opacity:1}}50%{{opacity:0}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<rect x=".5" y=".5" width="{WIDTH - 1}" height="{height - 1}" rx="10" fill="{c["bg"]}" stroke="{c["edge"]}"/>
<path d="M.5 {TITLE_BAR}V10.5a10 10 0 0 1 10-10h{WIDTH - 21}a10 10 0 0 1 10 10V{TITLE_BAR}z" fill="{c["bar"]}" stroke="{c["edge"]}"/>
<circle cx="22" cy="18" r="6" fill="#ff5f57"/><circle cx="42" cy="18" r="6" fill="#febc2e"/><circle cx="62" cy="18" r="6" fill="#28c840"/>
<text x="{WIDTH / 2:.0f}" y="23" text-anchor="middle" class="dim">{escape(title)}</text>
{chr(10).join(body)}
</svg>
'''


if __name__ == "__main__":
    target = Path(__file__).resolve().parent.parent / "assets" / "terminal.svg"
    target.write_text(build(), encoding="utf-8")
    print(f"wrote {target}")
