"""Генерирует docs/flowchart.svg — блок-схему алгоритма подбора поставщика (Задача 1)."""

W, H = 860, 1180
INK = "#1c2118"; GREEN = "#3f6b3a"; GREEN_DEEP = "#2c4d29"; AMBER = "#c47a1e"
RED = "#b23b2e"; LINE = "#9aa08c"; PAPER = "#fbfaf4"; GREEN_SOFT = "#dce8d6"
RED_SOFT = "#f6dcd7"; MUTED = "#7c7a6c"

parts = []
def add(s): parts.append(s)

CX = 300  # центр основной колонки
MX = 690  # центр колонки "ручной разбор"

def term(cx, cy, w, h, text, fill, stroke, tcol="#fff", fs=15, bold=True):
    add(f'<rect x="{cx-w/2}" y="{cy-h/2}" width="{w}" height="{h}" rx="{h/2}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>')
    _multiline(cx, cy, text, tcol, fs, bold)

def proc(cx, cy, w, h, text, fs=14):
    add(f'<rect x="{cx-w/2}" y="{cy-h/2}" width="{w}" height="{h}" rx="10" '
        f'fill="#ffffff" stroke="{LINE}" stroke-width="1.5"/>')
    _multiline(cx, cy, text, INK, fs, False)

def decision(cx, cy, w, h, text, fs=13):
    add(f'<polygon points="{cx},{cy-h/2} {cx+w/2},{cy} {cx},{cy+h/2} {cx-w/2},{cy}" '
        f'fill="{PAPER}" stroke="{AMBER}" stroke-width="2"/>')
    _multiline(cx, cy, text, INK, fs, False)

def _multiline(cx, cy, text, col, fs, bold):
    lines = text.split("\n")
    fw = "600" if bold else "500"
    start = cy - (len(lines) - 1) * (fs + 3) / 2
    for i, ln in enumerate(lines):
        add(f'<text x="{cx}" y="{start + i*(fs+3) + fs*0.35}" text-anchor="middle" '
            f'font-family="Hanken Grotesk, sans-serif" font-size="{fs}" font-weight="{fw}" '
            f'fill="{col}">{ln}</text>')

def arrow(x1, y1, x2, y2, label="", lcol=GREEN_DEEP):
    add(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{LINE}" '
        f'stroke-width="1.8" marker-end="url(#arr)"/>')
    if label:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        add(f'<rect x="{mx-13}" y="{my-10}" width="26" height="18" rx="9" fill="{PAPER}"/>')
        add(f'<text x="{mx}" y="{my+3}" text-anchor="middle" font-family="Hanken Grotesk,sans-serif" '
            f'font-size="11" font-weight="700" fill="{lcol}">{label}</text>')

def elbow(x1, y1, x2, y2, label=""):
    add(f'<polyline points="{x1},{y1} {x2},{y1} {x2},{y2}" fill="none" stroke="{LINE}" '
        f'stroke-width="1.8" marker-end="url(#arr)"/>')
    if label:
        add(f'<rect x="{(x1+x2)/2-15}" y="{y1-22}" width="30" height="18" rx="9" fill="{PAPER}"/>')
        add(f'<text x="{(x1+x2)/2}" y="{y1-9}" text-anchor="middle" font-family="Hanken Grotesk,sans-serif" '
            f'font-size="11" font-weight="700" fill="{RED}">{label}</text>')

# --- узлы основной цепочки (y-координаты центров) ---
y = {}
term(CX, 40, 320, 56, "НОВЫЙ ЗАКАЗ\n(фрукт, кол-во, дата заказа, срок клиенту)",
     GREEN_DEEP, GREEN_DEEP, fs=13)
arrow(CX, 68, CX, 100)
proc(CX, 128, 360, 50, "Доступное время = срок клиенту − дата заказа")
arrow(CX, 153, CX, 183)
proc(CX, 213, 360, 50, "Найти всех поставщиков нужного фрукта")
arrow(CX, 238, CX, 272)
decision(CX, 320, 220, 96, "Поставщики\nэтого фрукта\nесть?")
arrow(CX, 368, CX, 408, "да")
proc(CX, 440, 360, 52, "Оставить тех, у кого\nостаток на складе ≥ количество")
arrow(CX, 466, CX, 500)
decision(CX, 548, 220, 96, "Остался\nхотя бы один?")
arrow(CX, 596, CX, 636, "да")
proc(CX, 668, 360, 54, "Оставить тех, чей срок поставки\n≤ доступного времени")
arrow(CX, 695, CX, 729)
decision(CX, 777, 220, 96, "Остался\nхотя бы один?")
arrow(CX, 825, CX, 865, "да")
proc(CX, 900, 360, 52, "Выбрать поставщика\nс минимальной ценой закупки")
arrow(CX, 926, CX, 958)
proc(CX, 990, 360, 56, "Цена продажи = цена закупки × 1.25\nСумма заказа = цена продажи × количество")
arrow(CX, 1018, CX, 1050)
proc(CX, 1078, 360, 44, "Списать количество со склада поставщика", fs=13)
# терминатор "подобран" справа внизу под последним process
add(f'<line x1="{CX}" y1="1100" x2="{CX}" y2="1126" stroke="{LINE}" stroke-width="1.8"/>')
term(CX, 1150, 300, 50, "СТАТУС: «Подобран поставщик»", GREEN_SOFT, GREEN_DEEP, tcol=GREEN_DEEP, fs=13)

# --- ветви "нет" -> общий терминатор ручного разбора (справа) ---
BUS = 520
for cy in (320, 548, 777):
    elbow(CX + 110, cy, BUS, cy, "нет")
# вертикальная шина
add(f'<line x1="{BUS}" y1="320" x2="{BUS}" y2="777" stroke="{LINE}" stroke-width="1.8"/>')
# от шины к терминатору
mid_y = 548
add(f'<line x1="{BUS}" y1="{mid_y}" x2="{MX-150}" y2="{mid_y}" stroke="{LINE}" stroke-width="1.8" marker-end="url(#arr)"/>')
term(MX, mid_y, 270, 70, "СТАТУС:\n«Требует ручного разбора»", RED_SOFT, RED, tcol=RED, fs=13)

# заголовок + легенда
header = (f'<text x="40" y="40" font-family="Fraunces, serif" font-size="22" font-weight="600" '
          f'fill="{INK}">Подбор поставщика для заказа</text>'
          f'<text x="40" y="62" font-family="Hanken Grotesk,sans-serif" font-size="13" fill="{MUTED}">'
          f'Задача 1 · алгоритм выполняется для каждого заказа из Таблицы 2</text>')

legend_x = MX - 130
ly = 760
legend = (
    f'<rect x="{legend_x}" y="{ly}" width="260" height="120" rx="10" fill="#ffffff" stroke="{LINE}"/>'
    f'<text x="{legend_x+16}" y="{ly+26}" font-family="Fraunces,serif" font-size="14" font-weight="600" fill="{INK}">Обозначения</text>'
    f'<rect x="{legend_x+16}" y="{ly+40}" width="22" height="14" rx="7" fill="{GREEN_DEEP}"/>'
    f'<text x="{legend_x+46}" y="{ly+51}" font-family="Hanken Grotesk,sans-serif" font-size="12" fill="{INK}">начало / конец</text>'
    f'<rect x="{legend_x+16}" y="{ly+62}" width="22" height="14" rx="3" fill="#fff" stroke="{LINE}"/>'
    f'<text x="{legend_x+46}" y="{ly+73}" font-family="Hanken Grotesk,sans-serif" font-size="12" fill="{INK}">действие</text>'
    f'<polygon points="{legend_x+27},{ly+84} {legend_x+38},{ly+91} {legend_x+27},{ly+98} {legend_x+16},{ly+91}" fill="{PAPER}" stroke="{AMBER}" stroke-width="1.5"/>'
    f'<text x="{legend_x+46}" y="{ly+95}" font-family="Hanken Grotesk,sans-serif" font-size="12" fill="{INK}">условие (да / нет)</text>'
)

svg = (
    f'<svg viewBox="0 0 {W} {H+70}" xmlns="http://www.w3.org/2000/svg">'
    f'<defs><marker id="arr" markerWidth="9" markerHeight="9" refX="7" refY="3" orient="auto">'
    f'<path d="M0,0 L7,3 L0,6 Z" fill="{LINE}"/></marker></defs>'
    f'<rect width="{W}" height="{H+70}" fill="{PAPER}"/>'
    + header
    + f'<g transform="translate(0,80)">' + legend + "".join(parts) + "</g>"
    + "</svg>"
)

with open("docs/flowchart.svg", "w", encoding="utf-8") as f:
    f.write(svg)
print("docs/flowchart.svg сгенерирован")
