"""Original, self-contained visual stimuli used by the UCATify question bank.

The database stores stable ``[[VISUAL:name]]`` markers instead of large HTML
fragments.  The app resolves only names from this trusted registry, keeping the
seed data readable while allowing genuine diagram and chart questions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class QuestionVisual:
    html: str
    height: int
    label: str


VISUAL_MARKER_RE = re.compile(r"\[\[VISUAL:([a-z0-9_]+)\]\]")


def split_visual_markers(text: str) -> tuple[str, list[str]]:
    """Return display text and the ordered visual ids embedded in it."""
    visual_ids = VISUAL_MARKER_RE.findall(text or "")
    cleaned = VISUAL_MARKER_RE.sub("", text or "")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, visual_ids


def _document(title: str, svg: str, view_box: str, *, background: str = "#fbfaf7") -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box}}html,body{{margin:0;background:transparent;color:#20201e;
font-family:Inter,Arial,sans-serif}}.frame{{width:100%;padding:10px;border:1px solid #d8d5ce;
border-radius:12px;background:{background};overflow:hidden}}svg{{display:block;width:100%;height:auto}}
.title{{font-size:18px;font-weight:700;fill:#20201e}}.sub{{font-size:12px;fill:#68645d}}
.axis{{font-size:11px;fill:#5f5b55}}.value{{font-size:12px;font-weight:700;fill:#20201e}}
.label{{font-size:13px;font-weight:600;fill:#20201e}}.grid{{stroke:#ddd9d1;stroke-width:1}}
</style></head><body><div class="frame"><svg role="img" aria-label="{title}" viewBox="{view_box}">
{svg}</svg></div></body></html>"""


def _dm_region_map() -> QuestionVisual:
    svg = """
<text x="20" y="28" class="title">Community skills programme</text>
<text x="20" y="47" class="sub">Each outline represents one workshop. Letters mark participant groups.</text>
<g fill="none" stroke-width="2.5">
  <rect x="35" y="85" width="235" height="150" rx="3" stroke="#315f7d"/>
  <ellipse cx="290" cy="160" rx="150" ry="95" stroke="#b85c44"/>
  <polygon points="240,35 430,285 90,285" stroke="#47815f"/>
  <polygon points="310,70 420,70 480,160 420,250 310,250 250,160" stroke="#8a6cac"/>
  <polygon points="55,65 205,55 300,260 160,270" stroke="#c28a32"/>
  <polygon points="380,35 450,160 380,285 310,160" stroke="#2f8985"/>
</g>
<g font-size="18" font-weight="800" text-anchor="middle" fill="#171716">
  <circle cx="120" cy="205" r="16" fill="#fff" stroke="#9d978d"/><text x="120" y="211">G</text>
  <circle cx="250" cy="160" r="16" fill="#fff" stroke="#9d978d"/><text x="250" y="166">M</text>
  <circle cx="330" cy="140" r="16" fill="#fff" stroke="#9d978d"/><text x="330" y="146">R</text>
  <circle cx="220" cy="265" r="16" fill="#fff" stroke="#9d978d"/><text x="220" y="271">P</text>
</g>
<g transform="translate(505,45) scale(0.82)">
  <text x="0" y="0" class="label">Key</text>
  <rect x="0" y="16" width="34" height="22" fill="none" stroke="#315f7d" stroke-width="2"/>
  <text x="48" y="33" class="axis">robotics</text>
  <ellipse cx="17" cy="62" rx="20" ry="12" fill="none" stroke="#b85c44" stroke-width="2"/>
  <text x="48" y="67" class="axis">orchestra</text>
  <polygon points="17,82 35,110 -1,110" fill="none" stroke="#47815f" stroke-width="2"/>
  <text x="48" y="103" class="axis">debating</text>
  <polygon points="5,128 29,128 40,145 29,162 5,162 -6,145" fill="none" stroke="#8a6cac" stroke-width="2"/>
  <text x="48" y="150" class="axis">athletics</text>
  <polygon points="0,180 28,177 38,198 9,202" fill="none" stroke="#c28a32" stroke-width="2"/>
  <text x="48" y="194" class="axis">photography</text>
  <polygon points="17,218 31,237 17,256 3,237" fill="none" stroke="#2f8985" stroke-width="2"/>
  <text x="48" y="242" class="axis">gardening</text>
</g>
"""
    return QuestionVisual(
        _document("Six overlapping workshop outlines with labelled regions G, M, R and P", svg, "0 0 700 340"),
        410,
        "Workshop overlap diagram",
    )


def _venn_option(label: str, *, left: int, overlap: int, right: int, separate: int,
                 outside: int, separate_overlaps: bool = False) -> QuestionVisual:
    separate_x = 164 if separate_overlaps else 190
    svg = f"""
<rect x="12" y="8" width="226" height="126" rx="4" fill="#fff" stroke="#8f8a82"/>
<circle cx="80" cy="64" r="39" fill="#77a6c7" fill-opacity=".16" stroke="#315f7d" stroke-width="2"/>
<circle cx="126" cy="64" r="39" fill="#dc8b76" fill-opacity=".16" stroke="#b85c44" stroke-width="2"/>
<circle cx="{separate_x}" cy="83" r="26" fill="#79ad89" fill-opacity=".16" stroke="#47815f" stroke-width="2"/>
<g text-anchor="middle" class="value"><text x="64" y="69">{left}</text><text x="103" y="69">{overlap}</text>
<text x="142" y="69">{right}</text><text x="{separate_x}" y="88">{separate}</text></g>
<text x="25" y="125" class="value">{outside}</text>
"""
    overlap_note = "; the third circle overlaps another set" if separate_overlaps else "; the third circle is separate"
    return QuestionVisual(
        _document(f"Diagram {label}: two overlapping circles{overlap_note}", svg, "0 0 250 145"),
        260,
        f"Diagram {label}",
    )


def _water_line_chart() -> QuestionVisual:
    values = {"A": [18, 22, 31], "B": [12, 17, 24], "C": [26, 29, 35], "D": [15, 20, 28]}
    colors = {"A": "#315f7d", "B": "#b85c44", "C": "#47815f", "D": "#8a6cac"}
    xs = [145, 365, 585]
    def y(v: int) -> float:
        return 315 - (v - 10) * 9.2
    parts = [
        '<text x="20" y="28" class="title">Monthly household water use</text>',
        '<text x="20" y="47" class="sub">Values are cubic metres (m³)</text>',
    ]
    for tick in (10, 15, 20, 25, 30, 35):
        yy = y(tick)
        parts.append(f'<line x1="80" y1="{yy:.1f}" x2="650" y2="{yy:.1f}" class="grid"/>')
        parts.append(f'<text x="67" y="{yy+4:.1f}" text-anchor="end" class="axis">{tick}</text>')
    for xpos, month in zip(xs, ("April", "May", "June")):
        parts.append(f'<text x="{xpos}" y="340" text-anchor="middle" class="label">{month}</text>')
    for i, (name, series) in enumerate(values.items()):
        points = " ".join(f"{x},{y(v):.1f}" for x, v in zip(xs, series))
        parts.append(f'<polyline points="{points}" fill="none" stroke="{colors[name]}" stroke-width="3"/>')
        for x, v in zip(xs, series):
            yy = y(v)
            parts.append(f'<circle cx="{x}" cy="{yy:.1f}" r="5" fill="{colors[name]}"/>')
            parts.append(f'<text x="{x}" y="{yy-9:.1f}" text-anchor="middle" class="value">{v}</text>')
        lx = 680
        ly = 90 + i * 48
        parts.append(f'<line x1="{lx}" y1="{ly}" x2="{lx+25}" y2="{ly}" stroke="{colors[name]}" stroke-width="4"/>')
        parts.append(f'<text x="{lx+34}" y="{ly+4}" class="axis">Household {name}</text>')
    return QuestionVisual(_document("Line graph of monthly water use for four households", "\n".join(parts), "0 0 800 365"), 410, "Monthly water-use line graph")


def _exchange_rate_chart() -> QuestionVisual:
    rows = [
        ("Euro (€)", 1.16, "1.5% of sterling deducted before conversion", "#315f7d"),
        ("Polish zloty (zł)", 5.02, "£6 added to sterling cost", "#b85c44"),
        ("Danish krone (kr)", 13.40, "2% of converted krone deducted", "#47815f"),
    ]
    parts = [
        '<text x="20" y="28" class="title">Currency received per £1 exchanged</text>',
        '<text x="20" y="47" class="sub">Apply the charge shown for each currency</text>',
    ]
    for i, (name, rate, charge, color) in enumerate(rows):
        yy = 82 + i * 82
        width = rate / 13.4 * 430
        parts.append(f'<text x="18" y="{yy+4}" class="label">{name}</text>')
        parts.append(f'<rect x="175" y="{yy-18}" width="430" height="27" rx="5" fill="#ece9e2"/>')
        parts.append(f'<rect x="175" y="{yy-18}" width="{width:.1f}" height="27" rx="5" fill="{color}"/>')
        parts.append(f'<text x="{max(220, 185+width):.1f}" y="{yy+2}" class="value">{rate:.2f}</text>')
        parts.append(f'<text x="175" y="{yy+28}" class="axis">Charge: {charge}</text>')
    parts.append('<rect x="18" y="318" width="650" height="38" rx="8" fill="#f0ece3"/>')
    parts.append('<text x="34" y="342" class="label">Unused euros: £0.82 per €1, then deduct a £4 return fee</text>')
    return QuestionVisual(_document("Horizontal bar chart of exchange rates and charges", "\n".join(parts), "0 0 720 375"), 430, "Exchange-rate bar chart")


def _printer_chart() -> QuestionVisual:
    printers = [("A", 38, 12, 4, ".031"), ("B", 52, 18, 7, ".028"), ("C", 44, 8, 5, ".030"), ("D", 40, 6, 3, ".032")]
    colors = ["#315f7d", "#b85c44", "#47815f", "#8a6cac"]
    parts = ['<text x="20" y="28" class="title">Printer performance</text>',
             '<text x="20" y="47" class="sub">Setup occurs once per job; waste is the unusable share of printed sheets</text>',
             '<text x="80" y="82" class="label">Speed (sheets/min)</text>',
             '<text x="445" y="82" class="label">Setup time (min)</text>']
    for i, ((name, speed, setup, waste, cost), color) in enumerate(zip(printers, colors)):
        yy = 112 + i * 53
        parts.append(f'<text x="40" y="{yy+16}" class="label">{name}</text>')
        parts.append(f'<rect x="80" y="{yy}" width="{speed*4.8}" height="24" rx="4" fill="{color}"/>')
        parts.append(f'<text x="{90+speed*4.8}" y="{yy+17}" class="value">{speed}</text>')
        parts.append(f'<rect x="445" y="{yy}" width="{setup*8.5}" height="24" rx="4" fill="{color}" opacity=".78"/>')
        parts.append(f'<text x="{455+setup*8.5}" y="{yy+17}" class="value">{setup}</text>')
        parts.append(f'<rect x="40" y="{335+i*38}" width="660" height="30" rx="5" fill="{color}" opacity=".10"/>')
        parts.append(f'<text x="55" y="{355+i*38}" class="label">Printer {name}</text>')
        parts.append(f'<text x="250" y="{355+i*38}" class="axis">Waste {waste}%</text>')
        parts.append(f'<text x="430" y="{355+i*38}" class="axis">Paper cost £0{cost} per printed sheet</text>')
    return QuestionVisual(_document("Bar charts of printer speed and setup time with waste and cost data", "\n".join(parts), "0 0 740 510"), 560, "Printer performance charts")


def _fundraising_chart() -> QuestionVisual:
    rows = [("Walk", 320, 12.00, 3.20, 650, "#315f7d"), ("Quiz", 180, 18.00, 5.00, 900, "#b85c44"), ("Concert", 240, 25.00, 9.50, 1800, "#47815f")]
    parts = ['<text x="20" y="28" class="title">Fundraising event data</text>',
             '<text x="20" y="47" class="sub">Bar height represents attendees; exact values are shown</text>']
    for tick in (0, 100, 200, 300):
        yy = 285 - tick * .62
        parts.append(f'<line x1="70" y1="{yy:.1f}" x2="690" y2="{yy:.1f}" class="grid"/>')
        parts.append(f'<text x="58" y="{yy+4:.1f}" text-anchor="end" class="axis">{tick}</text>')
    for i, (name, attendees, ticket, variable, fixed, color) in enumerate(rows):
        x = 135 + i * 210
        h = attendees * .62
        parts.append(f'<rect x="{x}" y="{285-h:.1f}" width="86" height="{h:.1f}" rx="6" fill="{color}"/>')
        parts.append(f'<text x="{x+43}" y="{276-h:.1f}" text-anchor="middle" class="value">{attendees}</text>')
        parts.append(f'<text x="{x+43}" y="310" text-anchor="middle" class="label">{name}</text>')
        parts.append(f'<rect x="{x-30}" y="330" width="146" height="86" rx="8" fill="{color}" opacity=".10"/>')
        parts.append(f'<text x="{x-18}" y="352" class="axis">Ticket: £{ticket:.2f}</text>')
        parts.append(f'<text x="{x-18}" y="375" class="axis">Variable: £{variable:.2f}/person</text>')
        parts.append(f'<text x="{x-18}" y="398" class="axis">Fixed: £{fixed:,}</text>')
    return QuestionVisual(_document("Bar chart of fundraising attendees with price and cost annotations", "\n".join(parts), "0 0 740 440"), 490, "Fundraising event bar chart")


def _solar_chart() -> QuestionVisual:
    sites = [("A", 80, 22, 8, 6), ("B", 120, 18, 10, 8), ("C", 95, 20, 9, 5)]
    parts = ['<text x="20" y="28" class="title">Solar-site capacity factors</text>',
             '<rect x="510" y="18" width="18" height="12" fill="#d7923b"/><text x="535" y="29" class="axis">Summer</text>',
             '<rect x="610" y="18" width="18" height="12" fill="#477b9f"/><text x="635" y="29" class="axis">Winter</text>']
    for tick in (0, 5, 10, 15, 20, 25):
        yy = 285 - tick * 8.5
        parts.append(f'<line x1="75" y1="{yy:.1f}" x2="690" y2="{yy:.1f}" class="grid"/>')
        parts.append(f'<text x="62" y="{yy+4:.1f}" text-anchor="end" class="axis">{tick}%</text>')
    for i, (name, capacity, summer, winter, loss) in enumerate(sites):
        x = 145 + i * 195
        parts.append(f'<rect x="{x}" y="{285-summer*8.5:.1f}" width="54" height="{summer*8.5:.1f}" rx="4" fill="#d7923b"/>')
        parts.append(f'<rect x="{x+62}" y="{285-winter*8.5:.1f}" width="54" height="{winter*8.5:.1f}" rx="4" fill="#477b9f"/>')
        parts.append(f'<text x="{x+27}" y="{276-summer*8.5:.1f}" text-anchor="middle" class="value">{summer}%</text>')
        parts.append(f'<text x="{x+89}" y="{276-winter*8.5:.1f}" text-anchor="middle" class="value">{winter}%</text>')
        parts.append(f'<text x="{x+58}" y="312" text-anchor="middle" class="label">Site {name}</text>')
        parts.append(f'<text x="{x+58}" y="335" text-anchor="middle" class="axis">{capacity} kW installed</text>')
        parts.append(f'<text x="{x+58}" y="355" text-anchor="middle" class="axis">{loss}% system loss</text>')
    return QuestionVisual(_document("Grouped bar chart of summer and winter solar capacity factors", "\n".join(parts), "0 0 740 380"), 430, "Solar capacity-factor chart")


VISUALS: dict[str, QuestionVisual] = {
    "dm_workshop_regions": _dm_region_map(),
    "dm_venn_a": _venn_option("A", left=11, overlap=5, right=14, separate=8, outside=6),
    "dm_venn_b": _venn_option("B", left=6, overlap=5, right=9, separate=6, outside=8),
    "dm_venn_c": _venn_option("C", left=6, overlap=5, right=9, separate=8, outside=6, separate_overlaps=True),
    "dm_venn_d": _venn_option("D", left=6, overlap=5, right=9, separate=8, outside=6),
    "qr_water_use": _water_line_chart(),
    "qr_exchange_rates": _exchange_rate_chart(),
    "qr_printer_performance": _printer_chart(),
    "qr_fundraising": _fundraising_chart(),
    "qr_solar_factors": _solar_chart(),
}
