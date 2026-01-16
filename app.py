from flask import Flask, request, abort, render_template, url_for, redirect, Response
from datetime import date, timedelta
import json
import os
import random

app = Flask(__name__)

# -----------------------------
# Helpers
# -----------------------------
def format_nl_date(d: str) -> str:
    y, m, day = d.split("-")
    return f"{day}-{m}-{y}"

def format_nl_long(d: str) -> str:
    return f"Sudoku van {format_nl_date(d)}"

def build_archive(dates):
    archive = {}
    for d in dates:
        y = int(d[:4])
        m = int(d[5:7])
        archive.setdefault(y, {}).setdefault(m, []).append(d)
    return archive

def get_daily_or_404(d_iso: str):
    row = DAILY.get(d_iso)
    if not row:
        abort(404, f"Geen sudoku voor {d_iso}")
    return row

def is_future(d_iso: str) -> bool:
    return d_iso > TODAY_ISO

def render_solution_table(solution81: str) -> str:
    # eenvoudige tabel (solution.html kan dit mooier stylen)
    html = ["<table class='solution-grid'>"]
    for r in range(9):
        html.append("<tr>")
        for c in range(9):
            v = solution81[r * 9 + c]
            html.append(f"<td>{v}</td>")
        html.append("</tr>")
    html.append("</table>")
    return "\n".join(html)

def clamp_to_visible(d_iso: str):
    # zorg dat je nooit voorbij "vandaag" navigeert via knoppen
    if d_iso > LAST_VISIBLE:
        return LAST_VISIBLE
    if d_iso < ALL_DATES[0]:
        return ALL_DATES[0]
    return d_iso

def nav_links_daily(d_iso: str, size_key: str):
    # prev/next alleen binnen zichtbare set (<= vandaag)
    d_obj = date.fromisoformat(d_iso)
    prev_d = (d_obj - timedelta(days=1)).isoformat()
    next_d = (d_obj + timedelta(days=1)).isoformat()

    prev_url = url_for("sudoku", date=prev_d) if prev_d in DAILY else None
    next_url = url_for("sudoku", date=next_d) if next_d in VISIBLE_SET else None

    prev_big = url_for("groter", date=prev_d, size=size_key) if prev_d in DAILY else None
    next_big = url_for("groter", date=next_d, size=size_key) if next_d in VISIBLE_SET else None

    return prev_url, next_url, prev_big, next_big

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# -----------------------------
# Data laden: daily
# -----------------------------
DATA = load_json("daily.json")
DAILY = {row["date"]: row for row in DATA}
ALL_DATES = sorted(DAILY.keys())
if not ALL_DATES:
    raise RuntimeError("daily.json bevat geen puzzels.")

TODAY_ISO = date.today().isoformat()

VISIBLE_DATES = [d for d in ALL_DATES if d <= TODAY_ISO]
if not VISIBLE_DATES:
    VISIBLE_DATES = ALL_DATES[:]
VISIBLE_SET = set(VISIBLE_DATES)
LAST_VISIBLE = VISIBLE_DATES[-1]

ARCHIVE = build_archive(VISIBLE_DATES)
YEARS = sorted(ARCHIVE.keys())

# -----------------------------
# Data laden: packs
# -----------------------------
PACK_CATS = ["makkelijk", "gemiddeld", "moeilijk", "extreem"]
PACKS = {}
PACK_MAX_ID = {}

for cat in PACK_CATS:
    p = os.path.join("packs", f"{cat}.json")
    if os.path.exists(p):
        rows = load_json(p)
        # rows is list; we gebruiken 1-based index
        PACKS[cat] = rows
        PACK_MAX_ID[cat] = len(rows)
    else:
        PACKS[cat] = []
        PACK_MAX_ID[cat] = 0

# -----------------------------
# Labels & sizes
# -----------------------------
DIFF_LABEL = {
    "easy": "Makkelijk",
    "medium": "Gemiddeld",
    "hard": "Moeilijk",
}

PACK_LABEL = {
    "makkelijk": "Makkelijk",
    "gemiddeld": "Gemiddeld",
    "moeilijk": "Moeilijk",
    "extreem": "Extreem moeilijk",
}

SIZE_TO_CELL = {
    "klein": 24,
    "normaal": 34,
    "groot": 44,
    "extra": 56,
}

def norm_size(size_key: str, default="normaal"):
    s = (size_key or default).lower()
    return s if s in SIZE_TO_CELL else default

# template filter: {{ d|nl }}
@app.template_filter("nl")
def _nl_filter(d: str) -> str:
    return format_nl_date(d)

@app.context_processor
def inject_globals():
    return {"current_year": date.today().year}

# -----------------------------
# Render helpers
# -----------------------------
def render_daily(d: str, size_key: str, mode: str):
    d = clamp_to_visible(d)
    row = get_daily_or_404(d)

    size_key = norm_size(size_key, "normaal" if mode == "sudoku" else "groot")

    prev_url, next_url, prev_big, next_big = nav_links_daily(d, size_key=size_key)

    if mode == "groter":
        show_size_dropdown = True
        prev_url_use = prev_big
        next_url_use = next_big
    else:
        show_size_dropdown = False
        prev_url_use = prev_url
        next_url_use = next_url

    diff_text = DIFF_LABEL.get(row.get("difficulty", ""), row.get("difficulty", ""))

    return render_template(
        "sudoku_play.html",
        title=format_nl_long(d),
        iso_date=d,                 # daily iso
        nl_date=format_nl_date(d),
        mode=mode,
        is_future=is_future(d),

        puzzle=row["puzzle"],
        solution=row["solution"],
        diff_text=diff_text,
        clues=row.get("clues", ""),

        size_key=size_key,
        cell_px=SIZE_TO_CELL[size_key],
        sizes=list(SIZE_TO_CELL.keys()),
        show_size_dropdown=show_size_dropdown,

        prev_url=prev_url_use,
        next_url=next_url_use,
        today_url=None,

        archive_url=url_for("archief_jaren"),
        solution_url=url_for("oplossing", date=d),
        print_url=url_for("print_puzzle", date=d, size=size_key),
        bigger_url=url_for("groter", date=d, size="groot"),

        # ✅ belangrijk voor dropdown gedrag
        size_action_url=url_for("groter"),       # daily groter route
        size_back_url=url_for("sudoku", date=d), # terug naar daily

        show_more_block=True,
    )

def get_pack_row_or_404(cat: str, n: int):
    cat = (cat or "").lower()
    if cat not in PACKS or PACK_MAX_ID.get(cat, 0) == 0:
        abort(404, "Categorie bestaat niet (of pack ontbreekt).")

    if n < 1 or n > PACK_MAX_ID[cat]:
        abort(404, "Puzzelnummer bestaat niet.")

    return PACKS[cat][n - 1]

def render_pack(cat: str, n: int, size_key: str, mode: str):
    cat = cat.lower()
    row = get_pack_row_or_404(cat, n)

    size_key = norm_size(size_key, "normaal" if mode == "pack" else "groot")

    # prev/next ook op pack_groter, maar nooit voorbij de grenzen
    if mode in ("pack", "pack_groter"):
        prev_url = url_for("pack_view", cat=cat, n=n - 1) if n > 1 else None
        next_url = url_for("pack_view", cat=cat, n=n + 1) if n < PACK_MAX_ID[cat] else None
    else:
        prev_url = None
        next_url = None

    show_size_dropdown = (mode == "pack_groter")
    diff_text = PACK_LABEL.get(cat, cat)

    return render_template(
        "sudoku_play.html",
        title=f"Sudoku {diff_text} #{n}",
        iso_date=f"{cat}-{n}",      # pack id (geen echte datum)
        nl_date=f"{diff_text} #{n}",
        mode=mode,
        is_future=False,

        puzzle=row["puzzle"],
        solution=row["solution"],
        diff_text=diff_text,
        clues=row.get("clues", ""),

        size_key=size_key,
        cell_px=SIZE_TO_CELL[size_key],
        sizes=list(SIZE_TO_CELL.keys()),
        show_size_dropdown=show_size_dropdown,

        prev_url=prev_url,
        next_url=next_url,
        today_url=None,

        archive_url=url_for("archief_jaren"),
        solution_url=url_for("pack_oplossing", cat=cat, n=n),
        print_url=url_for("print_pack", cat=cat, n=n, size=size_key),
        bigger_url=url_for("pack_groter", cat=cat, n=n, size="groot"),

        # ✅ belangrijk: dropdown blijft in pack
        size_action_url=url_for("pack_groter", cat=cat, n=n),
        size_back_url=url_for("pack_view", cat=cat, n=n),

        show_more_block=False,
    )

# -----------------------------
# Routes: daily
# -----------------------------
@app.get("/")
def home():
    d = TODAY_ISO if TODAY_ISO in DAILY else LAST_VISIBLE
    return render_daily(d, size_key="normaal", mode="sudoku")

@app.get("/sudoku")
def sudoku():
    d = request.args.get("date", TODAY_ISO)
    size_key = norm_size(request.args.get("size", "normaal"), "normaal")
    return render_daily(d, size_key=size_key, mode="sudoku")

@app.get("/groter")
def groter():
    d = request.args.get("date", TODAY_ISO)
    size_key = norm_size(request.args.get("size", "groot"), "groot")
    return render_daily(d, size_key=size_key, mode="groter")

@app.get("/oplossing")
def oplossing():
    d = request.args.get("date", TODAY_ISO)
    d = clamp_to_visible(d)
    row = get_daily_or_404(d)
    diff_text = DIFF_LABEL.get(row.get("difficulty", ""), row.get("difficulty", ""))

    return render_template(
        "solution.html",
        title=f"Oplossing {format_nl_date(d)}",
        nl_date=format_nl_date(d),
        diff_text=diff_text,
        back_url=url_for("sudoku", date=d),
        archive_url=url_for("archief_jaren"),
        solution_grid=render_solution_table(row["solution"]),
    )

@app.get("/print")
def print_puzzle():
    d = request.args.get("date", TODAY_ISO)
    d = clamp_to_visible(d)
    size_key = norm_size(request.args.get("size", "groot"), "groot")
    row = get_daily_or_404(d)

    cell = SIZE_TO_CELL[size_key]
    font_px = int(cell * 0.55)

    # print as simple HTML
    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Print sudoku {format_nl_date(d)}</title>
<style>
  body {{ font-family: Arial, sans-serif; padding: 20px; text-align: center; }}
  h1 {{ margin: 0 0 10px 0; }}
  table.grid {{ border-collapse: collapse; margin: 0 auto; }}
  td.cell {{
    width:{cell}px; height:{cell}px;
    text-align:center; border:1px solid #000;
    font-size:{font_px}px;
    font-weight: 800;
  }}
  tr:nth-child(3) td, tr:nth-child(6) td {{ border-bottom:3px solid #000; }}
  td:nth-child(3), td:nth-child(6) {{ border-right:3px solid #000; }}
  .noprint {{ margin-top: 16px; }}
  @media print {{ .noprint {{ display:none; }} body {{ padding:0; }} }}
</style>
</head>
<body>
<h1>Sudoku {format_nl_date(d)}</h1>
<table class="grid">
{''.join([
    '<tr>' + ''.join([
        f"<td class='cell'>{('&nbsp;' if row['puzzle'][r*9+c]=='0' else row['puzzle'][r*9+c])}</td>"
        for c in range(9)
    ]) + '</tr>'
    for r in range(9)
])}
</table>
<div class="noprint"><p><a href="{url_for('sudoku', date=d)}">← Terug</a></p></div>
<script>window.onload=function(){{window.print();}}</script>
</body>
</html>"""

# -----------------------------
# Routes: archief
# -----------------------------
@app.get("/archief")
def archief_jaren():
    return render_template(
        "archief_years.html",
        years=YEARS,
        today_nl=format_nl_date(TODAY_ISO),
    )

@app.get("/archief/<int:year>")
def archief_maanden(year: int):
    months = ARCHIVE.get(year)
    if not months:
        abort(404, f"Geen data voor {year}")

    month_list = sorted(months.keys())
    counts = {m: len(months[m]) for m in month_list}

    return render_template(
        "archief_months.html",
        year=year,
        months=month_list,
        counts=counts,
    )

@app.get("/archief/<int:year>/<int:month>")
def archief_dagen(year: int, month: int):
    months = ARCHIVE.get(year)
    if not months or month not in months:
        abort(404, f"Geen data voor {year}-{month:02d}")

    return render_template(
        "archief_days.html",
        year=year,
        month=month,
        dates=months[month],
    )

# -----------------------------
# Routes: packs
# -----------------------------
@app.get("/pack/random/<cat>")
def pack_random(cat: str):
    cat = cat.lower()
    if cat not in PACKS or PACK_MAX_ID.get(cat, 0) == 0:
        abort(404, "Pack bestaat niet.")
    n = random.randint(1, PACK_MAX_ID[cat])
    return redirect(url_for("pack_view", cat=cat, n=n))

@app.get("/pack/<cat>/<int:n>")
def pack_view(cat: str, n: int):
    size_key = norm_size(request.args.get("size", "normaal"), "normaal")
    return render_pack(cat, n, size_key=size_key, mode="pack")

@app.get("/pack/<cat>/<int:n>/groter")
def pack_groter(cat: str, n: int):
    size_key = norm_size(request.args.get("size", "groot"), "groot")
    return render_pack(cat, n, size_key=size_key, mode="pack_groter")

@app.get("/pack/<cat>/<int:n>/oplossing")
def pack_oplossing(cat: str, n: int):
    row = get_pack_row_or_404(cat, n)
    diff_text = PACK_LABEL.get(cat, cat)
    next_url = url_for("pack_oplossing", cat=cat, n=n + 1) if n < PACK_MAX_ID[cat] else None

    return render_template(
        "solution.html",
        title=f"Oplossing {diff_text} #{n}",
        nl_date=f"{diff_text} #{n}",
        diff_text=diff_text,
        back_url=url_for("pack_view", cat=cat, n=n),
        archive_url=url_for("meer"),
        next_url=next_url,
        solution_grid=render_solution_table(row["solution"]),
    )

@app.get("/pack/<cat>/<int:n>/print")
def print_pack(cat: str, n: int):
    row = get_pack_row_or_404(cat, n)
    size_key = norm_size(request.args.get("size", "groot"), "groot")

    cell = SIZE_TO_CELL[size_key]
    font_px = int(cell * 0.55)

    title = f"Sudoku {PACK_LABEL.get(cat, cat)} #{n}"

    return f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Print {title}</title>
<style>
  body {{ font-family: Arial, sans-serif; padding: 20px; text-align: center; }}
  h1 {{ margin: 0 0 10px 0; }}
  table.grid {{ border-collapse: collapse; margin: 0 auto; }}
  td.cell {{
    width:{cell}px; height:{cell}px;
    text-align:center; border:1px solid #000;
    font-size:{font_px}px;
    font-weight: 800;
  }}
  tr:nth-child(3) td, tr:nth-child(6) td {{ border-bottom:3px solid #000; }}
  td:nth-child(3), td:nth-child(6) {{ border-right:3px solid #000; }}
  .noprint {{ margin-top: 16px; }}
  @media print {{ .noprint {{ display:none; }} body {{ padding:0; }} }}
</style>
</head>
<body>
<h1>{title}</h1>
<table class="grid">
{''.join([
    '<tr>' + ''.join([
        f"<td class='cell'>{('&nbsp;' if row['puzzle'][r*9+c]=='0' else row['puzzle'][r*9+c])}</td>"
        for c in range(9)
    ]) + '</tr>'
    for r in range(9)
])}
</table>
<div class="noprint"><p><a href="{url_for('pack_view', cat=cat, n=n)}">← Terug</a></p></div>
<script>window.onload=function(){{window.print();}}</script>
</body>
</html>"""

# -----------------------------
# Route: meer (keuze pagina)
# -----------------------------
@app.get("/meer")
def meer():
    cat = (request.args.get("cat", "makkelijk") or "makkelijk").lower()
    nr = request.args.get("nr", "1")
    size = norm_size(request.args.get("size", "normaal"), "normaal")

    try:
        nr_i = int(nr)
    except ValueError:
        nr_i = 1

    max_id = PACK_MAX_ID.get(cat, 0) or max(PACK_MAX_ID.values() or [0])

    # clamp nr
    if max_id > 0:
        nr_i = max(1, min(nr_i, max_id))
    else:
        nr_i = 1

    return render_template(
        "meer.html",
        cat=cat,
        nr=nr_i,
        size=size,
        max_id=max_id,
    )

# -----------------------------
# SEO: robots.txt + sitemap.xml
# -----------------------------
@app.get("/robots.txt")
def robots():
    base = "https://dagelijksesudoku.nl"
    lines = [
        "User-agent: *",
        "Allow: /",
        f"Sitemap: {base}/sitemap.xml",
    ]
    return Response("\n".join(lines) + "\n", mimetype="text/plain")


@app.get("/sitemap.xml")
def sitemap():
    base = "https://dagelijksesudoku.nl"
    urls = [
        f"{base}/",
        f"{base}/archief",
        f"{base}/meer",
    ]

    for d in VISIBLE_DATES:
        urls.append(f"{base}/sudoku?date={d}")

    items = []
    for u in urls:
        items.append(
            "<url>"
            f"<loc>{u}</loc>"
            "</url>"
        )

    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        + "".join(items) +
        "</urlset>"
    )
    return Response(xml, mimetype="application/xml")


if __name__ == "__main__":
    app.run(debug=True)
