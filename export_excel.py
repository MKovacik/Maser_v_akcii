"""Generate Excel workbook from a solved schedule."""
import io
import os
import openpyxl
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image as XlImage
from openpyxl.utils.units import cm_to_EMU, pixels_to_EMU
from openpyxl.drawing.spreadsheet_drawing import OneCellAnchor, AnchorMarker
from openpyxl.drawing.xdr import XDRPositiveSize2D
from math import ceil

FILL_HEADER = PatternFill("solid", fgColor="1F4E79")
FILL_KLASICKA = PatternFill("solid", fgColor="BDD7EE")
FILL_FREESTYLE = PatternFill("solid", fgColor="9BC2E6")
FILL_SPORT = PatternFill("solid", fgColor="C6EFCE")
FILL_TEST = PatternFill("solid", fgColor="FFE699")
FILL_OBED = PatternFill("solid", fgColor="F8CBAD")
FILL_REG = PatternFill("solid", fgColor="D9D9D9")
FILL_CEREMONY = PatternFill("solid", fgColor="D9D9D9")
FILL_PRESUN = PatternFill("solid", fgColor="E2EFDA")

FONT_HEADER = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
FONT_NORMAL = Font(name="Calibri", size=11)
FONT_BOLD = Font(name="Calibri", size=11, bold=True)

ALIGN_CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)
ALIGN_LEFT = Alignment(horizontal="left", vertical="center", wrap_text=True)

THIN_BORDER = Border(
    left=Side(style="thin"), right=Side(style="thin"),
    top=Side(style="thin"), bottom=Side(style="thin"),
)

CATEGORY_FILL = {
    "klas": FILL_KLASICKA, "free": FILL_FREESTYLE,
    "sport": FILL_SPORT, "test": FILL_TEST,
    "obed": FILL_OBED, "presun": FILL_PRESUN,
}

ROW_HEIGHT_ACTIVITY = 30
ROW_HEIGHT_HEADER = 20


def time_to_min(s):
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def min_to_time(m):
    return f"{m // 60:02d}:{m % 60:02d}"


def get_station(act_name):
    if act_name in ("Klasická masáž", "Freestyle masáž"):
        return "masaze"
    if act_name in ("Hod medicinbalom", "Ľah-sed", "Beh na 50m", "Frisbee na cieľ"):
        return "sport"
    if act_name == "Test":
        return "test"
    if act_name == "Obed":
        return "obed"
    return None


def add_transfers(schedule):
    result = []
    for i, (act, start, end, cat) in enumerate(schedule):
        result.append((act, start, end, cat))
        if i < len(schedule) - 1:
            next_act, next_start, _, _ = schedule[i + 1]
            curr_st = get_station(act)
            next_st = get_station(next_act)
            if (curr_st and next_st and curr_st != next_st
                    and curr_st != "obed" and next_st != "obed"):
                gap = time_to_min(next_start) - time_to_min(end)
                if gap >= 10:
                    result.append(("Presun", end, min_to_time(time_to_min(end) + 10), "presun"))
    return result


def generate_excel(teams, logo_path=None, competition_start="08:45",
                   competition_end="13:45", lunch_group1_size=0):
    """Generate Excel bytes from teams dict. Returns bytes."""
    num_teams = len(teams)
    if lunch_group1_size <= 0:
        lunch_group1_size = ceil(num_teams / 2)

    teams_with_transfers = {t: add_transfers(teams[t]) for t in teams}

    wb = openpyxl.Workbook()

    # ═══ OVERVIEW SHEET ═══
    ws = wb.active
    ws.title = "Prehľad"

    ws.merge_cells("A1:M1")
    c = ws["A1"]
    c.value = "MASÉR V AKCII – Časový harmonogram"
    c.font = Font(name="Calibri", size=18, bold=True, color="1F4E79")
    c.alignment = ALIGN_CENTER

    ws.merge_cells("A3:M3")
    ws["A3"].value = "Celkový program dňa"
    ws["A3"].font = Font(name="Calibri", size=13, bold=True)
    ws["A3"].alignment = ALIGN_LEFT

    general_events = [
        ("08:00 – 08:30", "Registrácia účastníkov, losovanie poradia"),
        ("08:30", "Otvorenie súťaže"),
        (competition_start, "Začiatok súťaže"),
        ("11:00 – 11:30", f"Obed – skupiny 1 až {lunch_group1_size}"),
        ("12:30 – 13:00", f"Obed – skupiny {lunch_group1_size + 1} až {num_teams}"),
        (competition_end, "Ukončenie súťaže"),
        ("13:45 – 14:00", "Presun"),
        ("14:00 – 14:45", "Sprievodný program"),
        ("14:45 – 15:00", "Presun"),
        ("15:00 – 15:30", "Vyhlásenie výsledkov"),
    ]

    row = 4
    for time_str, desc in general_events:
        ws.cell(row=row, column=1, value=time_str).font = FONT_BOLD
        ws.cell(row=row, column=1).alignment = ALIGN_LEFT
        ws.cell(row=row, column=1).border = THIN_BORDER
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=13)
        ws.cell(row=row, column=2, value=desc).font = FONT_NORMAL
        ws.cell(row=row, column=2).alignment = ALIGN_LEFT
        ws.cell(row=row, column=2).border = THIN_BORDER
        for col in range(3, 14):
            ws.cell(row=row, column=col).border = THIN_BORDER
        row += 1

    row += 1

    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=13)
    ws.cell(row=row, column=1, value="Legenda farieb:").font = FONT_BOLD
    row += 1
    for fill, label in [
        (FILL_KLASICKA, "Klasická masáž"), (FILL_FREESTYLE, "Freestyle masáž"),
        (FILL_SPORT, "Športové disciplíny (telocvičňa)"), (FILL_TEST, "Test"),
        (FILL_OBED, "Obed"), (FILL_PRESUN, "Presun medzi stanovišťami (~10 min)"),
    ]:
        ws.cell(row=row, column=1).fill = fill
        ws.cell(row=row, column=1).border = THIN_BORDER
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=5)
        ws.cell(row=row, column=2, value=label).font = FONT_NORMAL
        ws.cell(row=row, column=2).border = THIN_BORDER
        for c2 in range(3, 6):
            ws.cell(row=row, column=c2).border = THIN_BORDER
        row += 1

    row += 1

    # Summary table
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=13)
    ws.cell(row=row, column=1, value="Prehľad stanovíšť podľa tímov").font = Font(name="Calibri", size=13, bold=True)
    row += 1

    for ci, h in enumerate(["Tím", "Klasická masáž", "Freestyle masáž",
                             "Športové (telocvičňa)", "Test", "Obed"], 1):
        cell = ws.cell(row=row, column=ci, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER
    row += 1

    for t_id in sorted(teams.keys()):
        cell = ws.cell(row=row, column=1, value=f"Team {t_id}")
        cell.font = FONT_BOLD
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER

        sport_entries = [(s, e) for name, s, e, c in teams[t_id] if c == "sport"]
        if sport_entries:
            c2 = ws.cell(row=row, column=4, value=f"{sport_entries[0][0]} – {sport_entries[-1][1]}")
            c2.font = FONT_NORMAL
            c2.alignment = ALIGN_CENTER
            c2.border = THIN_BORDER
            c2.fill = FILL_SPORT

        col_map = {"Klasická masáž": (2, FILL_KLASICKA), "Freestyle masáž": (3, FILL_FREESTYLE),
                   "Test": (5, FILL_TEST), "Obed": (6, FILL_OBED)}
        for act_name, start, end, cat in teams[t_id]:
            if act_name in col_map:
                col, fill = col_map[act_name]
                c2 = ws.cell(row=row, column=col, value=f"{start} – {end}")
                c2.font = FONT_NORMAL
                c2.alignment = ALIGN_CENTER
                c2.border = THIN_BORDER
                c2.fill = fill

        for ci in range(1, 7):
            ws.cell(row=row, column=ci).border = THIN_BORDER
        row += 1

    for label, fill in [
        (f"Ukončenie súťaže – {competition_end}", FILL_CEREMONY),
        ("Presun – 13:45 – 14:00", FILL_REG),
        ("Sprievodný program – 14:00 – 14:45", FILL_REG),
        ("Presun – 14:45 – 15:00", FILL_REG),
        ("Vyhlásenie výsledkov – 15:00 – 15:30", FILL_CEREMONY),
    ]:
        ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=6)
        cell = ws.cell(row=row, column=1, value=label)
        cell.font = FONT_BOLD
        cell.alignment = ALIGN_CENTER
        cell.fill = fill
        for ci in range(1, 7):
            ws.cell(row=row, column=ci).border = THIN_BORDER
        row += 1

    row += 1

    # Timeline grid
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=num_teams + 1)
    ws.cell(row=row, column=1, value="Časová os (5-minútové intervaly)").font = Font(name="Calibri", size=13, bold=True)
    row += 1

    cell = ws.cell(row=row, column=1, value="Čas")
    cell.font = FONT_HEADER
    cell.fill = FILL_HEADER
    cell.alignment = ALIGN_CENTER
    cell.border = THIN_BORDER
    for i, t_id in enumerate(sorted(teams.keys()), 1):
        cell = ws.cell(row=row, column=i + 1, value=f"Team {t_id}")
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER
    row += 1

    team_timeline = {}
    for t_id in teams:
        timeline = {}
        for act_name, start, end, cat in teams_with_transfers[t_id]:
            s, e = time_to_min(start), time_to_min(end)
            short = {"Klasická masáž": "Klas. masáž", "Freestyle masáž": "Free. masáž",
                     "Hod medicinbalom": "Hod med.", "Frisbee na cieľ": "Frisbee",
                     "Beh na 50m": "Beh 50m"}.get(act_name, act_name)
            for m in range(s, e):
                timeline[m] = (short, cat)
        team_timeline[t_id] = timeline

    start_min = time_to_min(competition_start)
    end_min = time_to_min(competition_end)

    for slot in range(start_min, end_min, 5):
        cell = ws.cell(row=row, column=1, value=min_to_time(slot))
        cell.font = FONT_NORMAL
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER
        for i, t_id in enumerate(sorted(teams.keys()), 1):
            tl = team_timeline[t_id]
            act, cat = None, None
            for m in range(slot, min(slot + 5, end_min)):
                if m in tl:
                    act, cat = tl[m]
                    break
            cell = ws.cell(row=row, column=i + 1)
            cell.border = THIN_BORDER
            cell.alignment = ALIGN_CENTER
            cell.font = Font(name="Calibri", size=9)
            if act:
                cell.value = act
                cell.fill = CATEGORY_FILL.get(cat, PatternFill())
        row += 1

    for time_str, label, fill in [
        (competition_end, "Ukončenie súťaže", FILL_CEREMONY),
        ("13:45 – 14:00", "Presun", FILL_REG),
        ("14:00 – 14:45", "Sprievodný program", FILL_REG),
        ("14:45 – 15:00", "Presun", FILL_REG),
        ("15:00 – 15:30", "Vyhlásenie výsledkov", FILL_CEREMONY),
    ]:
        cell = ws.cell(row=row, column=1, value=time_str)
        cell.font = FONT_NORMAL
        cell.alignment = ALIGN_CENTER
        cell.border = THIN_BORDER
        ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=num_teams + 1)
        c2 = ws.cell(row=row, column=2, value=label)
        c2.font = FONT_BOLD
        c2.alignment = ALIGN_CENTER
        c2.fill = fill
        for ci in range(2, num_teams + 2):
            ws.cell(row=row, column=ci).border = THIN_BORDER
        row += 1

    ws.column_dimensions["A"].width = 16
    for ci in range(2, num_teams + 2):
        ws.column_dimensions[get_column_letter(ci)].width = 14

    # ═══ PER-TEAM SHEETS ═══
    has_logo = logo_path and os.path.exists(logo_path)

    for t_id in sorted(teams.keys()):
        ws_t = wb.create_sheet(title=f"Team {t_id}")

        # Logo
        if has_logo:
            ws_t.row_dimensions[1].height = 60
            ws_t.row_dimensions[2].height = 6
            img = XlImage(logo_path)
            marker = AnchorMarker(col=0, row=0, colOff=cm_to_EMU(0.3), rowOff=cm_to_EMU(0.1))
            size = XDRPositiveSize2D(pixels_to_EMU(280), pixels_to_EMU(75))
            img.anchor = OneCellAnchor(_from=marker, ext=size)
            ws_t.add_image(img)
            title_row = 4
        else:
            title_row = 1

        # Title
        ws_t.merge_cells(f"A{title_row}:D{title_row}")
        c = ws_t.cell(row=title_row, column=1)
        c.value = "MASÉR V AKCII"
        c.font = Font(name="Calibri", size=18, bold=True, color="1F4E79")
        c.alignment = ALIGN_CENTER
        ws_t.row_dimensions[title_row].height = 30

        # Spacer
        info_row = title_row + 2
        ws_t.row_dimensions[title_row + 1].height = 6

        # Team info
        ws_t.merge_cells(f"A{info_row}:B{info_row}")
        ws_t.cell(row=info_row, column=1, value=f"Družstvo č. {t_id}").font = Font(name="Calibri", size=14, bold=True)
        ws_t.cell(row=info_row, column=1).alignment = ALIGN_LEFT
        ws_t.cell(row=info_row, column=1).border = THIN_BORDER
        ws_t.cell(row=info_row, column=2).border = THIN_BORDER

        ws_t.merge_cells(f"C{info_row}:D{info_row}")
        ws_t.cell(row=info_row, column=3, value="Škola:").font = Font(name="Calibri", size=14, bold=True)
        ws_t.cell(row=info_row, column=3).alignment = ALIGN_LEFT
        ws_t.cell(row=info_row, column=3).border = THIN_BORDER
        ws_t.cell(row=info_row, column=4).border = THIN_BORDER
        ws_t.row_dimensions[info_row].height = 25

        # Table headers
        hdr_row = info_row + 2
        for ci, hdr in enumerate(["Aktivita", "Čas", "Poznámka", "Body"], 1):
            cell = ws_t.cell(row=hdr_row, column=ci, value=hdr)
            cell.font = FONT_HEADER
            cell.fill = FILL_HEADER
            cell.alignment = ALIGN_CENTER
            cell.border = THIN_BORDER
        ws_t.row_dimensions[hdr_row].height = ROW_HEIGHT_HEADER
        r = hdr_row + 1

        lunch_group = (f"1. skupina (tímy 1–{lunch_group1_size})"
                       if t_id <= lunch_group1_size
                       else f"2. skupina (tímy {lunch_group1_size + 1}–{num_teams})")

        for act_name, start, end, cat in teams_with_transfers[t_id]:
            fill = CATEGORY_FILL.get(cat, PatternFill())
            ws_t.cell(row=r, column=1, value=act_name).font = FONT_NORMAL
            ws_t.cell(row=r, column=1).alignment = ALIGN_LEFT
            ws_t.cell(row=r, column=1).border = THIN_BORDER
            ws_t.cell(row=r, column=1).fill = fill

            ws_t.cell(row=r, column=2, value=f"{start} – {end}").font = FONT_NORMAL
            ws_t.cell(row=r, column=2).alignment = ALIGN_CENTER
            ws_t.cell(row=r, column=2).border = THIN_BORDER
            ws_t.cell(row=r, column=2).fill = fill

            note = lunch_group if act_name == "Obed" else ""
            ws_t.cell(row=r, column=3, value=note).font = FONT_NORMAL
            ws_t.cell(row=r, column=3).alignment = ALIGN_LEFT
            ws_t.cell(row=r, column=3).border = THIN_BORDER

            ws_t.cell(row=r, column=4).border = THIN_BORDER
            ws_t.cell(row=r, column=4).alignment = ALIGN_CENTER

            ws_t.row_dimensions[r].height = ROW_HEIGHT_ACTIVITY
            r += 1

        for label, time_val, fill in [
            ("Ukončenie súťaže", competition_end, FILL_CEREMONY),
            ("Presun", "13:45 – 14:00", FILL_REG),
            ("Sprievodný program", "14:00 – 14:45", FILL_REG),
            ("Presun", "14:45 – 15:00", FILL_REG),
            ("Vyhlásenie výsledkov", "15:00 – 15:30", FILL_CEREMONY),
        ]:
            for ci in range(1, 5):
                ws_t.cell(row=r, column=ci).border = THIN_BORDER
                ws_t.cell(row=r, column=ci).fill = fill
            ws_t.cell(row=r, column=1, value=label).font = FONT_NORMAL
            ws_t.cell(row=r, column=1).alignment = ALIGN_LEFT
            ws_t.cell(row=r, column=2, value=time_val).font = FONT_NORMAL
            ws_t.cell(row=r, column=2).alignment = ALIGN_CENTER
            ws_t.row_dimensions[r].height = ROW_HEIGHT_ACTIVITY
            r += 1

        ws_t.column_dimensions["A"].width = 28
        ws_t.column_dimensions["B"].width = 18
        ws_t.column_dimensions["C"].width = 24
        ws_t.column_dimensions["D"].width = 12

        ws_t.sheet_properties.pageSetUpPr = openpyxl.worksheet.properties.PageSetupProperties(fitToPage=True)
        ws_t.page_setup.fitToWidth = 1
        ws_t.page_setup.fitToHeight = 1
        ws_t.page_setup.orientation = "portrait"
        ws_t.page_setup.paperSize = ws_t.PAPERSIZE_A4
        ws_t.page_margins.left = 0.5
        ws_t.page_margins.right = 0.5
        ws_t.page_margins.top = 0.4
        ws_t.page_margins.bottom = 0.4

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
