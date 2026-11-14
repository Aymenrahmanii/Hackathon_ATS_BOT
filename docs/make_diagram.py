"""Render docs/loop.svg: an animated diagram of the bot's decision loop.

    uv run python -m docs.make_diagram
"""

from __future__ import annotations

from pathlib import Path

OUT = Path(__file__).with_name("loop.svg")
W, H = 1000, 340
LOOP_S = 3.2
PHASES = [(0.0, 0.55), (0.55, 0.7), (0.7, 0.85), (0.85, 1.0)]  # wait, refresh, choose, act
RULES = ["Burst", "Defend me", "Defend teammate", "Attack a threat", "Claim", "Discover", "Attack (idle)"]
LOOPS = [  # (rule index, what the Act box shows, why)
    (4, "claim countVowels x3", "Nothing urgent: claim the best-paying nugget (coefficient x success rate)."),
    (1, "defend Rival1x", "An attack landed during the wait: throttle is now 4000 ms, so defend first."),
    (4, "claim countVowels x3", "Back to 3000 ms: claiming again."),
    (0, "burst (-3 points)", "Three attackers while claiming x3: one burst beats three defends."),
]
TOTAL = LOOP_S * len(LOOPS)
INK, DIM, LINE, CARD, ACCENT = "#c9d1d9", "#8b949e", "#30363d", "#161b22", "#58a6ff"
CHIP_COLORS = ["#ffa657", "#79c0ff", "#79c0ff", "#ff7b72", "#7ee787", "#c9d1d9", "#ff7b72"]


def pct(seconds: float) -> str:
    return f"{100 * seconds / TOTAL:.3f}%"


def blink(name: str, spans: list[tuple[float, float]], on: str = "opacity:1", off: str = "opacity:0") -> str:
    """Keyframes that switch a property on during each (start, end) span, in seconds."""
    frames = [f"0%{{{off}}}"]
    for start, end in spans:
        frames += [f"{pct(max(0, start - 0.02))}{{{off}}}", f"{pct(start)},{pct(end)}{{{on}}}",
                   f"{pct(min(TOTAL, end + 0.02))}{{{off}}}"]
    frames.append(f"100%{{{off}}}")
    return f"@keyframes {name}{{{''.join(frames)}}}.{name}{{animation:{name} {TOTAL}s linear infinite}}"


def phase_spans(phase: int) -> list[tuple[float, float]]:
    start, end = PHASES[phase]
    return [(i * LOOP_S + start * LOOP_S, i * LOOP_S + end * LOOP_S) for i in range(len(LOOPS))]


def render() -> str:
    styles: list[str] = []
    parts: list[str] = []
    box_w, box_h, gap, top = 215, 92, 25, 58
    titles = [
        ("1  Wait", "3000 ms + margin"),
        ("2  Refresh (free)", "/auth/me  /users  /teams"),
        ("3  Choose", "first rule that applies"),
        ("4  Act", ""),
    ]
    for i, (title, sub) in enumerate(titles):
        x = 25 + i * (box_w + gap)
        parts.append(f'<rect x="{x}" y="{top}" width="{box_w}" height="{box_h}" rx="10" fill="{CARD}" stroke="{LINE}"/>')
        parts.append(f'<rect class="box{i}" x="{x}" y="{top}" width="{box_w}" height="{box_h}" rx="10" fill="none" stroke="{ACCENT}" stroke-width="2.5"/>')
        parts.append(f'<text x="{x + 16}" y="{top + 30}" class="h">{title}</text>')
        if sub:
            parts.append(f'<text x="{x + 16}" y="{top + 52}" class="s">{sub}</text>')
        styles.append(blink(f"box{i}", phase_spans(i)))
        if i < 3:
            ax = x + box_w + 3
            parts.append(f'<path d="M{ax} {top + 46} h{gap - 8}" stroke="{DIM}" stroke-width="2" marker-end="url(#arrow)"/>')
    # throttle bar fills during each wait
    bar_x, bar_y = 41, top + 66
    parts.append(f'<rect x="{bar_x}" y="{bar_y}" width="183" height="9" rx="4.5" fill="{LINE}"/>')
    parts.append(f'<rect class="fill" x="{bar_x}" y="{bar_y}" width="183" height="9" rx="4.5" fill="{ACCENT}"/>')
    fill = ["0%{transform:scaleX(0)}"]
    for start, end in phase_spans(0):
        fill += [f"{pct(start)}{{transform:scaleX(0)}}", f"{pct(end)}{{transform:scaleX(1)}}",
                 f"{pct(end + LOOP_S * 0.44)}{{transform:scaleX(1)}}"]
    styles.append(f"@keyframes fill{{{''.join(fill)}}}.fill{{transform-box:fill-box;transform-origin:left;"
                  f"animation:fill {TOTAL}s linear infinite}}")
    # the Act box shows this loop's action
    act_x = 25 + 3 * (box_w + gap) + 16
    for n, (rule, action, _) in enumerate(LOOPS):
        start = n * LOOP_S + PHASES[3][0] * LOOP_S
        parts.append(f'<text class="act{n}" x="{act_x}" y="{top + 58}" fill="{CHIP_COLORS[rule]}" '
                     f'style="font:600 15px ui-monospace,Consolas,monospace">{action}</text>')
        styles.append(blink(f"act{n}", [(start, n * LOOP_S + LOOP_S + PHASES[3][0] * LOOP_S - 0.05)]))
    # loop-back arrow
    parts.append(f'<path d="M{25 + 3 * (box_w + gap) + box_w / 2} {top + box_h + 4} v16 H{25 + box_w / 2} v-12" '
                 f'fill="none" stroke="{DIM}" stroke-width="2" stroke-dasharray="5 5" marker-end="url(#arrow)"/>')
    parts.append(f'<text x="{W / 2}" y="{top + box_h + 34}" text-anchor="middle" class="s">one throttled call per slot, forever</text>')
    # the rule ladder
    chip_top, chip_w, chip_gap = 222, 130, 8
    parts.append(f'<text x="25" y="{chip_top - 14}" class="s">Choose: the first rule that applies wins the slot</text>')
    for i, rule in enumerate(RULES):
        x = 25 + i * (chip_w + chip_gap)
        parts.append(f'<rect x="{x}" y="{chip_top}" width="{chip_w}" height="38" rx="19" fill="{CARD}" stroke="{LINE}"/>')
        spans = [(n * LOOP_S + PHASES[2][0] * LOOP_S, (n + 1) * LOOP_S - 0.05) for n, (r, _, _) in enumerate(LOOPS) if r == i]
        if spans:
            parts.append(f'<rect class="chip{i}" x="{x}" y="{chip_top}" width="{chip_w}" height="38" rx="19" '
                         f'fill="{CHIP_COLORS[i]}" fill-opacity="0.18" stroke="{CHIP_COLORS[i]}" stroke-width="2"/>')
            styles.append(blink(f"chip{i}", spans))
        parts.append(f'<text x="{x + chip_w / 2}" y="{chip_top + 24}" text-anchor="middle" class="c" fill="{CHIP_COLORS[i]}">{i + 1}  {rule}</text>')
    # why this rule won
    for n, (_, _, why) in enumerate(LOOPS):
        parts.append(f'<text class="why{n}" x="25" y="{chip_top + 76}" fill="{INK}" '
                     f'style="font:14px system-ui,-apple-system,Segoe UI,sans-serif">{why}</text>')
        styles.append(blink(f"why{n}", [(n * LOOP_S + PHASES[2][0] * LOOP_S, (n + 1) * LOOP_S - 0.05)]))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="The bot's loop: wait out the throttle, refresh the game state for free, choose the first rule that applies, make one throttled call">
<style>
.h{{font:600 16px system-ui,-apple-system,"Segoe UI",sans-serif;fill:{INK}}}
.s{{font:13px system-ui,-apple-system,"Segoe UI",sans-serif;fill:{DIM}}}
.c{{font:600 13px system-ui,-apple-system,"Segoe UI",sans-serif}}
{''.join(styles)}
@media (prefers-reduced-motion: reduce){{*{{animation:none!important}}}}
</style>
<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto"><path d="M0 0L10 5L0 10z" fill="{DIM}"/></marker></defs>
<rect width="{W}" height="{H}" rx="12" fill="#0d1117"/>
<text x="25" y="36" style="font:700 18px system-ui,-apple-system,'Segoe UI',sans-serif" fill="{INK}">How each bot spends its slots</text>
{chr(10).join(parts)}
</svg>
"""


def main() -> None:
    OUT.write_text(render(), encoding="utf-8")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
