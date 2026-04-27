"""Streamlit app for Masér v akcii schedule generation."""
import streamlit as st
from datetime import time
from solver import SolverConfig, SharedEvent, Activity, solve, min_to_time
from export_excel import generate_excel
import os
import base64

st.set_page_config(page_title="Masér v akcii – Harmonogram", layout="wide", page_icon="💆")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(SCRIPT_DIR, "logo.png")

BASE_CAT_COLORS = {
    "klas": {"bg": "#BDD7EE", "text": "#1a3a5c"},
    "free": {"bg": "#9BC2E6", "text": "#1a3a5c"},
    "sport": {"bg": "#C6EFCE", "text": "#1a4a2a"},
    "test": {"bg": "#FFE699", "text": "#5a4a00"},
}

DEFAULT_EVENTS = [
    {"name": "Registrácia", "start": time(8, 0), "dur": 30, "color": "#D9D9D9",
     "groups": False, "num_groups": 1, "g_starts": [], "g_sizes": []},
    {"name": "Otvorenie súťaže", "start": time(8, 30), "dur": 15, "color": "#D9D9D9",
     "groups": False, "num_groups": 1, "g_starts": [], "g_sizes": []},
    {"name": "Obed", "start": time(11, 0), "dur": 30, "color": "#F8CBAD",
     "groups": True, "num_groups": 2,
     "g_starts": [time(11, 0), time(12, 30)], "g_sizes": [6, 5]},
    {"name": "Sprievodný program", "start": time(14, 0), "dur": 45, "color": "#D9D9D9",
     "groups": False, "num_groups": 1, "g_starts": [], "g_sizes": []},
    {"name": "Vyhlásenie výsledkov", "start": time(15, 0), "dur": 30, "color": "#D9D9D9",
     "groups": False, "num_groups": 1, "g_starts": [], "g_sizes": []},
]

st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1F4E79 0%, #2874a6 100%);
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] select {
        color: #333 !important;
        background-color: #fff !important;
    }
    [data-testid="stSidebar"] .stNumberInput button {
        color: #1F4E79 !important;
    }
    [data-testid="stSidebar"] hr {
        border-color: rgba(255,255,255,0.2) !important;
    }

    .main-header {
        display: flex;
        align-items: center;
        gap: 24px;
        padding: 16px 0 8px 0;
        border-bottom: 3px solid #1F4E79;
        margin-bottom: 24px;
    }
    .main-header img { height: 60px; width: auto; }
    .main-header h1 { color: #1F4E79; font-size: 2rem; margin: 0; font-weight: 700; }
    .main-header .subtitle { color: #666; font-size: 0.95rem; margin-top: 2px; }

    .schedule-table {
        width: 100%; border-collapse: collapse; font-size: 0.9rem;
        border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .schedule-table thead th {
        background: #1F4E79; color: white; padding: 10px 14px;
        text-align: center; font-weight: 600; font-size: 0.85rem;
    }
    .schedule-table tbody td {
        padding: 8px 12px; text-align: center;
        border-bottom: 1px solid #e8e8e8; font-size: 0.85rem;
    }

    .timeline-table {
        border-collapse: collapse; font-size: 0.75rem;
        border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .timeline-table thead th {
        background: #1F4E79; color: white; padding: 6px 6px;
        text-align: center; font-weight: 600; font-size: 0.75rem;
        position: sticky; top: 0; z-index: 1;
        min-width: 70px;
    }
    .timeline-table tbody td {
        padding: 4px 4px; text-align: center; border: 1px solid #e0e0e0;
        font-size: 0.7rem; white-space: nowrap; min-width: 70px;
    }
    .timeline-table tbody td.time-col {
        font-weight: 600; background: #f0f4f8; padding: 4px 6px; color: #333;
        min-width: 50px;
    }
    .timeline-wrap {
        max-height: 600px; overflow: auto; border-radius: 8px; border: 1px solid #e0e0e0;
    }

    .team-detail-table {
        width: 100%; border-collapse: collapse; font-size: 0.9rem;
        border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .team-detail-table thead th {
        background: #1F4E79; color: white; padding: 10px 14px;
        text-align: left; font-weight: 600;
    }
    .team-detail-table tbody td { padding: 10px 14px; border-bottom: 1px solid #e8e8e8; }

    .cat-badge {
        display: inline-block; padding: 3px 10px; border-radius: 12px;
        font-weight: 500; font-size: 0.8rem;
    }
    .stat-card {
        background: white; border-radius: 12px; padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-left: 4px solid #1F4E79;
        text-align: center;
    }
    .stat-card .value { font-size: 1.8rem; font-weight: 700; color: #1F4E79; }
    .stat-card .label { font-size: 0.85rem; color: #888; margin-top: 4px; }

    .legend-item {
        display: inline-flex; align-items: center; gap: 6px;
        margin-right: 16px; font-size: 0.85rem;
    }
    .legend-dot { width: 14px; height: 14px; border-radius: 4px; display: inline-block; }

    div[data-testid="stTabs"] button[role="tab"] {
        font-size: 1rem; font-weight: 600; padding: 12px 24px;
    }
    .success-banner {
        background: linear-gradient(135deg, #d4edda, #c3e6cb);
        border: 1px solid #28a745; border-radius: 10px;
        padding: 16px 24px; color: #155724; font-weight: 500; margin-bottom: 16px;
    }
</style>
""", unsafe_allow_html=True)

header_html = '<div class="main-header">'
if os.path.exists(LOGO_PATH):
    with open(LOGO_PATH, "rb") as f:
        logo_b64 = base64.b64encode(f.read()).decode()
    header_html += f'<img src="data:image/png;base64,{logo_b64}" />'
header_html += """
    <div>
        <h1>Masér v akcii</h1>
        <div class="subtitle">Generátor harmonogramu súťaže</div>
    </div>
</div>
"""
st.markdown(header_html, unsafe_allow_html=True)


def time_to_min_ui(t):
    return t.hour * 60 + t.minute


def min_to_time_ui(m):
    return time(m // 60, m % 60)


def cat_badge(text, cat, cat_colors):
    c = cat_colors.get(cat, {"bg": "#eee", "text": "#333"})
    return f'<span class="cat-badge" style="background:{c["bg"]};color:{c["text"]}">{text}</span>'


# ── Initialize session state ──
if "shared_events" not in st.session_state:
    st.session_state["shared_events"] = [dict(e) for e in DEFAULT_EVENTS]
if "masaze_activities" not in st.session_state:
    st.session_state["masaze_activities"] = [
        {"name": "Klasická masáž (Penzión Caritas)", "duration": 20, "abbr": "Klas."},
        {"name": "Freestyle masáž (Penzión Caritas)", "duration": 20, "abbr": "Free."},
    ]
if "sport_activities" not in st.session_state:
    st.session_state["sport_activities"] = [
        {"name": "Hod medicinbalom", "duration": 5, "abbr": "Hod"},
        {"name": "Ľah-sed", "duration": 5, "abbr": "Ľah-s."},
        {"name": "Beh na 50m", "duration": 5, "abbr": "Beh"},
        {"name": "Frisbee na cieľ", "duration": 5, "abbr": "Fris."},
        {"name": "Zápis výsledkov", "duration": 5, "abbr": "Zápis"},
    ]
if "test_activity" not in st.session_state:
    st.session_state["test_activity"] = {"name": "Test", "duration": 15, "abbr": "Test"}


# ── Sidebar ──
with st.sidebar:
    st.markdown("### Nastavenia")

    num_teams = st.number_input("Počet tímov", min_value=2, max_value=20, value=11)

    st.markdown("---")
    st.markdown("**Čas súťaže**")
    col1, col2 = st.columns(2)
    with col1:
        start_t = st.time_input("Začiatok", value=time(8, 45))
    with col2:
        end_t = st.time_input("Koniec", value=time(13, 45))

    st.markdown("---")
    st.markdown("**Stanovište: Masáže**")
    for i, act in enumerate(st.session_state["masaze_activities"]):
        with st.expander(act["name"], expanded=False):
            act["name"] = st.text_input("Názov", value=act["name"], key=f"mas_name_{i}")
            act["duration"] = st.number_input(
                "Trvanie (min)", min_value=5, max_value=60,
                value=act["duration"], key=f"mas_dur_{i}")

    st.markdown("---")
    st.markdown("**Stanovište: Šport**")
    sport_to_delete = None
    for i, act in enumerate(st.session_state["sport_activities"]):
        with st.expander(act["name"], expanded=False):
            act["name"] = st.text_input("Názov", value=act["name"], key=f"sport_name_{i}")
            act["duration"] = st.number_input(
                "Trvanie (min)", min_value=1, max_value=30,
                value=act["duration"], key=f"sport_dur_{i}")
            if len(st.session_state["sport_activities"]) > 1:
                if st.button("Odstrániť", key=f"sport_del_{i}", type="secondary"):
                    sport_to_delete = i
    if sport_to_delete is not None:
        st.session_state["sport_activities"].pop(sport_to_delete)
        st.rerun()
    if st.button("+ Pridať disciplínu", key="add_sport"):
        st.session_state["sport_activities"].append(
            {"name": "Nová disciplína", "duration": 5, "abbr": ""})
        st.rerun()

    st.markdown("---")
    st.markdown("**Stanovište: Test**")
    test_act = st.session_state["test_activity"]
    test_act["name"] = st.text_input("Názov", value=test_act["name"], key="test_name")
    test_act["duration"] = st.number_input(
        "Trvanie (min)", min_value=5, max_value=60,
        value=test_act["duration"], key="test_dur")

    st.markdown("---")
    st.markdown("**Presun**")
    transfer = st.number_input("Presun medzi stanovišťami (min)", min_value=5, max_value=20, value=10)

    st.markdown("---")
    st.markdown("**Spoločné udalosti**")

    events = st.session_state["shared_events"]

    to_delete = None
    for i, ev in enumerate(events):
        with st.expander(f"{ev['name']} ({ev['start'].strftime('%H:%M')})", expanded=False):
            ev["name"] = st.text_input("Názov", value=ev["name"], key=f"ev_name_{i}")
            c1, c2 = st.columns(2)
            with c1:
                ev["start"] = st.time_input("Začiatok", value=ev["start"], key=f"ev_start_{i}")
            with c2:
                ev["dur"] = st.number_input("Trvanie (min)", min_value=5, max_value=120,
                                            value=ev["dur"], key=f"ev_dur_{i}")
            ev["color"] = st.color_picker("Farba", value=ev["color"], key=f"ev_color_{i}")
            ev["groups"] = st.checkbox("Rozdeliť do skupín", value=ev["groups"], key=f"ev_grp_{i}")

            if ev["groups"]:
                ev["num_groups"] = st.number_input(
                    "Počet skupín", min_value=2, max_value=5,
                    value=ev.get("num_groups", 2), key=f"ev_ng_{i}")
                while len(ev["g_starts"]) < ev["num_groups"]:
                    ev["g_starts"].append(ev["start"])
                while len(ev["g_sizes"]) < ev["num_groups"]:
                    ev["g_sizes"].append(0)
                ev["g_starts"] = ev["g_starts"][:ev["num_groups"]]
                ev["g_sizes"] = ev["g_sizes"][:ev["num_groups"]]

                for g in range(ev["num_groups"]):
                    gc1, gc2 = st.columns(2)
                    with gc1:
                        ev["g_starts"][g] = st.time_input(
                            f"Sk.{g+1} začiatok", value=ev["g_starts"][g], key=f"ev_gs_{i}_{g}")
                    with gc2:
                        ev["g_sizes"][g] = st.number_input(
                            f"Sk.{g+1} veľkosť (0=auto)", min_value=0, max_value=num_teams,
                            value=ev["g_sizes"][g], key=f"ev_gsz_{i}_{g}")
            else:
                ev["num_groups"] = 1
                ev["g_starts"] = []
                ev["g_sizes"] = []

            if st.button("Odstrániť", key=f"ev_del_{i}", type="secondary"):
                to_delete = i

    if to_delete is not None:
        st.session_state["shared_events"].pop(to_delete)
        st.rerun()

    if st.button("+ Pridať udalosť", use_container_width=True):
        st.session_state["shared_events"].append({
            "name": "Nová udalosť", "start": time(12, 0), "dur": 30,
            "color": "#D9D9D9", "groups": False, "num_groups": 1,
            "g_starts": [], "g_sizes": [],
        })
        st.rerun()

    st.markdown("---")
    generate = st.button("Generovať harmonogram", type="primary", use_container_width=True)


def build_shared_events():
    result = []
    for ev in st.session_state["shared_events"]:
        group_starts = [time_to_min_ui(t) for t in ev["g_starts"]] if ev["groups"] else []
        group_sizes = list(ev["g_sizes"]) if ev["groups"] else []
        result.append(SharedEvent(
            name=ev["name"],
            start_time=time_to_min_ui(ev["start"]),
            duration=ev["dur"],
            color_bg=ev["color"],
            color_text="#333333",
            num_groups=ev["num_groups"] if ev["groups"] else 1,
            group_starts=group_starts,
            group_sizes=group_sizes,
        ))
    result.sort(key=lambda e: e.start_time)
    return result


def build_cat_colors(shared_events):
    colors = dict(BASE_CAT_COLORS)
    for ev in shared_events:
        colors[ev.category] = {"bg": ev.color_bg, "text": ev.color_text}
    return colors


if generate:
    shared_events = build_shared_events()
    mas_cats = ["klas", "free"]
    config = SolverConfig(
        num_teams=num_teams,
        start_time=time_to_min_ui(start_t),
        end_time=time_to_min_ui(end_t),
        masaze_activities=[
            Activity(a["name"], a["duration"], a["abbr"], mas_cats[i])
            for i, a in enumerate(st.session_state["masaze_activities"])
        ],
        sport_activities=[
            Activity(a["name"], a["duration"], a["abbr"], "sport")
            for a in st.session_state["sport_activities"]
        ],
        test_activities=[
            Activity(st.session_state["test_activity"]["name"],
                     st.session_state["test_activity"]["duration"],
                     st.session_state["test_activity"]["abbr"], "test")
        ],
        transfer_time=transfer,
        shared_events=shared_events,
    )

    with st.spinner("Hľadám optimálny harmonogram..."):
        result = solve(config)

    if result is None:
        st.error("Nie je možné naplánovať harmonogram s danými parametrami. "
                 "Skúste zväčšiť časové okno alebo znížiť počet tímov.")
    else:
        st.session_state["schedule"] = result
        st.session_state["config"] = config


if "schedule" in st.session_state:
    result = st.session_state["schedule"]
    config = st.session_state["config"]
    num_teams = config.num_teams
    cat_colors = build_cat_colors(config.shared_events)

    st.markdown('<div class="success-banner">Harmonogram úspešne vygenerovaný!</div>',
                unsafe_allow_html=True)

    logo = LOGO_PATH if os.path.exists(LOGO_PATH) else None
    excel_bytes = generate_excel(
        result,
        logo_path=logo,
        competition_start=min_to_time(config.start_time),
        competition_end=min_to_time(config.end_time),
        shared_events=config.shared_events,
        num_teams=config.num_teams,
        config=config,
    )

    total_activities = sum(len(v) for v in result.values())
    first_start = min(
        int(s[:2]) * 60 + int(s[3:])
        for entries in result.values() for _, s, _, _ in entries
    )
    last_end = max(
        int(e[:2]) * 60 + int(e[3:])
        for entries in result.values() for _, _, e, _ in entries
    )

    cols = st.columns(4)
    stats = [
        (str(num_teams), "Tímov"),
        (str(total_activities), "Aktivít celkom"),
        (f"{min_to_time(first_start)} – {min_to_time(last_end)}", "Čas súťaže"),
        (f"{last_end - first_start} min", "Celkové trvanie"),
    ]
    for col, (val, label) in zip(cols, stats):
        col.markdown(
            f'<div class="stat-card"><div class="value">{val}</div>'
            f'<div class="label">{label}</div></div>',
            unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    dl_col, _, _ = st.columns([1, 1, 3])
    with dl_col:
        st.download_button(
            label="Stiahnuť Excel", data=excel_bytes,
            file_name="Maser_v_akcii_harmonogram.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary", use_container_width=True)

    legend_html = '<div style="margin: 8px 0 20px 0;">'
    for a in config.masaze_activities:
        c = cat_colors[a.category]
        legend_html += (f'<span class="legend-item">'
                        f'<span class="legend-dot" style="background:{c["bg"]}"></span>'
                        f'{a.name}</span>')
    c = cat_colors["sport"]
    legend_html += (f'<span class="legend-item">'
                    f'<span class="legend-dot" style="background:{c["bg"]}"></span>'
                    f'Športové disciplíny (telocvičňa ZŠ)</span>')
    for a in config.test_activities:
        c = cat_colors[a.category]
        legend_html += (f'<span class="legend-item">'
                        f'<span class="legend-dot" style="background:{c["bg"]}"></span>'
                        f'{a.name}</span>')
    for ev in config.shared_events:
        c = cat_colors.get(ev.category, {"bg": ev.color_bg})
        legend_html += (f'<span class="legend-item">'
                        f'<span class="legend-dot" style="background:{c["bg"]}"></span>'
                        f'{ev.name}</span>')
    legend_html += "</div>"
    st.markdown(legend_html, unsafe_allow_html=True)

    # Shared events during competition (for overview table columns)
    comp_start = config.start_time
    comp_end = config.end_time
    during_events = [ev for ev in config.shared_events
                     if ev.overlaps_window(comp_start, comp_end)]

    tab1, tab2, tab3 = st.tabs(["Prehľad", "Časová os", "Po tímoch"])

    with tab1:
        mas_cats = [a.category for a in config.masaze_activities]
        test_cat = config.test_activities[0].category
        mas_names = {a.name for a in config.masaze_activities}
        test_names = {a.name for a in config.test_activities}

        headers = ["Tím"] + [a.name for a in config.masaze_activities]
        headers += ["Športové disciplíny (telocvičňa ZŠ)", config.test_activities[0].name]
        for ev in during_events:
            headers.append(ev.name)

        html = '<table class="schedule-table"><thead><tr>'
        for h in headers:
            html += f"<th>{h}</th>"
        html += "</tr></thead><tbody>"

        for t_id in sorted(result.keys()):
            html += "<tr>"
            html += f'<td style="font-weight:600;background:#f0f4f8;color:#1F4E79">Team {t_id}</td>'

            sport_entries = [(s, e) for name, s, e, c in result[t_id] if c == "sport"]
            cells = {cat: "" for cat in mas_cats}
            cells["sport"] = ""
            cells[test_cat] = ""
            for ev in during_events:
                cells[ev.category] = ""

            if sport_entries:
                cells["sport"] = f"{sport_entries[0][0]} – {sport_entries[-1][1]}"

            for name, s, e, cat in result[t_id]:
                if name in mas_names:
                    cells[cat] = f"{s} – {e}"
                elif name in test_names:
                    cells[cat] = f"{s} – {e}"
                else:
                    for ev in during_events:
                        if name == ev.name:
                            cells[ev.category] = f"{s} – {e}"

            col_cats = mas_cats + ["sport", test_cat] + [ev.category for ev in during_events]
            for cat_key in col_cats:
                if cells.get(cat_key):
                    c = cat_colors.get(cat_key, {"bg": "#eee", "text": "#333"})
                    html += (f'<td style="background:{c["bg"]};color:{c["text"]};'
                             f'font-weight:500;border-radius:4px">{cells[cat_key]}</td>')
                else:
                    html += "<td>–</td>"
            html += "</tr>"

        html += "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)

    with tab2:
        all_starts = [comp_start, comp_end]
        for ev in config.shared_events:
            if ev.num_groups > 1:
                all_starts.extend(ev.group_starts)
                all_starts.extend([gs + ev.duration for gs in ev.group_starts])
            else:
                all_starts.extend([ev.start_time, ev.end_time])
        tl_start = min(all_starts)
        tl_end = max(all_starts)

        abbrevs = {a.name: a.abbreviation for a in
                   config.masaze_activities + config.sport_activities + config.test_activities}

        tl_data = {}
        tl_full = {}
        for t_id in sorted(result.keys()):
            timeline = {}
            full_names = {}
            for name, s, e, cat in result[t_id]:
                sm = int(s[:2]) * 60 + int(s[3:])
                em = int(e[:2]) * 60 + int(e[3:])
                if name in abbrevs:
                    short = abbrevs[name]
                else:
                    word = name.split()[0]
                    short = word if len(word) <= 6 else word[:5] + "."
                for m in range(sm, em):
                    timeline[m] = (short, cat)
                    full_names[m] = (name, cat)
            tl_data[t_id] = timeline
            tl_full[t_id] = full_names

        sorted_teams = sorted(result.keys())
        slots = list(range(tl_start, tl_end, 5))

        grid = []
        for slot in slots:
            row_data = []
            for t_id in sorted_teams:
                tl = tl_data[t_id]
                fl = tl_full[t_id]
                act, cat_key, full = "", None, ""
                for m in range(slot, min(slot + 5, tl_end)):
                    if m in tl:
                        act, cat_key = tl[m]
                        full, _ = fl[m]
                        break
                row_data.append((act, cat_key, full))
            grid.append(row_data)

        def is_uniform_row(row_data):
            names = {full for _, _, full in row_data}
            cats = {cat for _, cat, _ in row_data}
            return len(names) == 1 and names != {""} and len(cats) == 1

        merge_spans = {}
        r = 0
        while r < len(grid):
            if is_uniform_row(grid[r]):
                full_name = grid[r][0][2]
                cat_key = grid[r][0][1]
                span = 1
                while (r + span < len(grid)
                       and is_uniform_row(grid[r + span])
                       and grid[r + span][0][2] == full_name):
                    span += 1
                merge_spans[r] = (span, full_name, cat_key)
                r += span
            else:
                r += 1

        html = '<div class="timeline-wrap"><table class="timeline-table"><thead><tr>'
        html += '<th>Čas</th>'
        for t_id in sorted_teams:
            html += f'<th>T{t_id}</th>'
        html += '</tr></thead><tbody>'

        skip_rows = set()
        for r_idx, slot in enumerate(slots):
            html += '<tr>'
            html += f'<td class="time-col">{min_to_time(slot)}</td>'

            if r_idx in skip_rows:
                html += '</tr>'
                continue

            if r_idx in merge_spans:
                span, full_name, cat_key = merge_spans[r_idx]
                c = cat_colors.get(cat_key, {"bg": "#eee", "text": "#333"})
                html += (f'<td colspan="{len(sorted_teams)}" rowspan="{span}" '
                         f'style="background:{c["bg"]};color:{c["text"]};'
                         f'font-weight:600;font-size:0.85rem;text-align:center;'
                         f'vertical-align:middle">{full_name}</td>')
                for skip in range(r_idx + 1, r_idx + span):
                    skip_rows.add(skip)
            else:
                for col_idx, (act, cat_key, _) in enumerate(grid[r_idx]):
                    if act and cat_key:
                        c = cat_colors.get(cat_key, {"bg": "#eee", "text": "#333"})
                        html += (f'<td style="background:{c["bg"]};color:{c["text"]};'
                                 f'font-weight:500">{act}</td>')
                    else:
                        html += '<td></td>'
            html += '</tr>'

        html += '</tbody></table></div>'
        st.markdown(html, unsafe_allow_html=True)

    with tab3:
        team_cols = st.columns([1, 4])
        with team_cols[0]:
            selected = st.selectbox("Vyber tím",
                                    [f"Team {t}" for t in sorted(result.keys())],
                                    label_visibility="collapsed")
        t_id = int(selected.split(" ")[1])
        entries = result[t_id]

        html = '<table class="team-detail-table"><thead><tr>'
        for h in ["Aktivita", "Čas", "Trvanie"]:
            html += f"<th>{h}</th>"
        html += "</tr></thead><tbody>"

        for name, s, e, cat in entries:
            dur = int(e[:2]) * 60 + int(e[3:]) - int(s[:2]) * 60 - int(s[3:])
            c = cat_colors.get(cat, {"bg": "#eee", "text": "#333"})
            html += f'<tr style="background:{c["bg"]}20">'
            html += f'<td>{cat_badge(name, cat, cat_colors)}</td>'
            html += f'<td style="text-align:center;font-weight:500">{s} – {e}</td>'
            html += f'<td style="text-align:center">{dur} min</td>'
            html += "</tr>"

        html += "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)
