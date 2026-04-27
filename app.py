"""Streamlit app for Masér v akcii schedule generation."""
import streamlit as st
from datetime import time
from solver import SolverConfig, solve, min_to_time
from export_excel import generate_excel
import os
import base64

st.set_page_config(page_title="Masér v akcii – Harmonogram", layout="wide", page_icon="💆")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOGO_PATH = os.path.join(SCRIPT_DIR, "logo.png")

CAT_COLORS = {
    "klas": {"bg": "#BDD7EE", "text": "#1a3a5c"},
    "free": {"bg": "#9BC2E6", "text": "#1a3a5c"},
    "sport": {"bg": "#C6EFCE", "text": "#1a4a2a"},
    "test": {"bg": "#FFE699", "text": "#5a4a00"},
    "obed": {"bg": "#F8CBAD", "text": "#5a2a00"},
}

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
    .main-header img {
        height: 60px;
        width: auto;
    }
    .main-header h1 {
        color: #1F4E79;
        font-size: 2rem;
        margin: 0;
        font-weight: 700;
    }
    .main-header .subtitle {
        color: #666;
        font-size: 0.95rem;
        margin-top: 2px;
    }

    .schedule-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .schedule-table thead th {
        background: #1F4E79;
        color: white;
        padding: 10px 14px;
        text-align: center;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .schedule-table tbody td {
        padding: 8px 12px;
        text-align: center;
        border-bottom: 1px solid #e8e8e8;
        font-size: 0.85rem;
    }

    .timeline-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.75rem;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .timeline-table thead th {
        background: #1F4E79;
        color: white;
        padding: 6px 4px;
        text-align: center;
        font-weight: 600;
        font-size: 0.75rem;
        position: sticky;
        top: 0;
        z-index: 1;
    }
    .timeline-table tbody td {
        padding: 4px 2px;
        text-align: center;
        border: 1px solid #e0e0e0;
        font-size: 0.7rem;
        white-space: nowrap;
    }
    .timeline-table tbody td.time-col {
        font-weight: 600;
        background: #f0f4f8;
        padding: 4px 6px;
        color: #333;
    }
    .timeline-wrap {
        max-height: 600px;
        overflow-y: auto;
        border-radius: 8px;
        border: 1px solid #e0e0e0;
    }

    .team-detail-table {
        width: 100%;
        border-collapse: collapse;
        font-size: 0.9rem;
        border-radius: 8px;
        overflow: hidden;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .team-detail-table thead th {
        background: #1F4E79;
        color: white;
        padding: 10px 14px;
        text-align: left;
        font-weight: 600;
    }
    .team-detail-table tbody td {
        padding: 10px 14px;
        border-bottom: 1px solid #e8e8e8;
    }

    .cat-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-weight: 500;
        font-size: 0.8rem;
    }

    .stat-card {
        background: white;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
        border-left: 4px solid #1F4E79;
        text-align: center;
    }
    .stat-card .value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #1F4E79;
    }
    .stat-card .label {
        font-size: 0.85rem;
        color: #888;
        margin-top: 4px;
    }

    .legend-item {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        margin-right: 16px;
        font-size: 0.85rem;
    }
    .legend-dot {
        width: 14px;
        height: 14px;
        border-radius: 4px;
        display: inline-block;
    }

    div[data-testid="stTabs"] button[role="tab"] {
        font-size: 1rem;
        font-weight: 600;
        padding: 12px 24px;
    }

    .success-banner {
        background: linear-gradient(135deg, #d4edda, #c3e6cb);
        border: 1px solid #28a745;
        border-radius: 10px;
        padding: 16px 24px;
        color: #155724;
        font-weight: 500;
        margin-bottom: 16px;
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
    st.markdown("**Obed**")
    col1, col2 = st.columns(2)
    with col1:
        lunch1_t = st.time_input("Skupina 1", value=time(11, 0))
    with col2:
        lunch2_t = st.time_input("Skupina 2", value=time(12, 30))
    lunch_dur = st.number_input("Trvanie obeda (min)", min_value=15, max_value=60, value=30)
    lunch_g1 = st.number_input("Veľkosť skupiny 1 (0 = auto)", min_value=0,
                               max_value=num_teams, value=0)

    st.markdown("---")
    st.markdown("**Trvanie aktivít (min)**")
    klasicka_dur = st.number_input("Klasická masáž", min_value=10, max_value=40, value=20)
    freestyle_dur = st.number_input("Freestyle masáž", min_value=10, max_value=40, value=20)
    sport_dur_each = st.number_input("Športová disciplína (1 z 4)", min_value=3, max_value=15, value=5)
    test_dur = st.number_input("Test", min_value=10, max_value=30, value=15)

    st.markdown("---")
    st.markdown("**Presun**")
    transfer = st.number_input("Presun medzi stanovišťami (min)", min_value=5, max_value=20, value=10)

    st.markdown("---")
    generate = st.button("Generovať harmonogram", type="primary", use_container_width=True)


def time_to_min_ui(t):
    return t.hour * 60 + t.minute


def cat_badge(text, cat):
    c = CAT_COLORS.get(cat, {"bg": "#eee", "text": "#333"})
    return f'<span class="cat-badge" style="background:{c["bg"]};color:{c["text"]}">{text}</span>'


if generate:
    config = SolverConfig(
        num_teams=num_teams,
        start_time=time_to_min_ui(start_t),
        end_time=time_to_min_ui(end_t),
        klasicka_duration=klasicka_dur,
        freestyle_duration=freestyle_dur,
        sport_disciplines=[
            ("Hod medicinbalom", sport_dur_each),
            ("Ľah-sed", sport_dur_each),
            ("Beh na 50m", sport_dur_each),
            ("Frisbee na cieľ", sport_dur_each),
        ],
        test_duration=test_dur,
        lunch_duration=lunch_dur,
        transfer_time=transfer,
        lunch_group1_start=time_to_min_ui(lunch1_t),
        lunch_group2_start=time_to_min_ui(lunch2_t),
        lunch_group1_size=lunch_g1,
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

    st.markdown('<div class="success-banner">Harmonogram úspešne vygenerovaný!</div>',
                unsafe_allow_html=True)

    logo = LOGO_PATH if os.path.exists(LOGO_PATH) else None
    excel_bytes = generate_excel(
        result,
        logo_path=logo,
        competition_start=min_to_time(config.start_time),
        competition_end=min_to_time(config.end_time),
        lunch_group1_size=config.group1_size,
    )

    # Stats row
    total_activities = sum(len(v) for v in result.values())
    first_start = min(
        int(s[:2]) * 60 + int(s[3:])
        for entries in result.values()
        for _, s, _, _ in entries
    )
    last_end = max(
        int(e[:2]) * 60 + int(e[3:])
        for entries in result.values()
        for _, _, e, _ in entries
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
            f'<div class="stat-card"><div class="value">{val}</div><div class="label">{label}</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("<br>", unsafe_allow_html=True)

    dl_col, _, _ = st.columns([1, 1, 3])
    with dl_col:
        st.download_button(
            label="Stiahnuť Excel",
            data=excel_bytes,
            file_name="Maser_v_akcii_harmonogram.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

    # Legend
    legend_html = '<div style="margin: 8px 0 20px 0;">'
    for cat, label in [("klas", "Klasická masáž"), ("free", "Freestyle masáž"),
                       ("sport", "Športové"), ("test", "Test"), ("obed", "Obed")]:
        c = CAT_COLORS[cat]
        legend_html += f'<span class="legend-item"><span class="legend-dot" style="background:{c["bg"]}"></span>{label}</span>'
    legend_html += "</div>"
    st.markdown(legend_html, unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["Prehľad", "Časová os", "Po tímoch"])

    with tab1:
        html = '<table class="schedule-table"><thead><tr>'
        for h in ["Tím", "Klasická masáž", "Freestyle masáž", "Športové", "Test", "Obed"]:
            html += f"<th>{h}</th>"
        html += "</tr></thead><tbody>"

        for t_id in sorted(result.keys()):
            html += "<tr>"
            html += f'<td style="font-weight:600;background:#f0f4f8;color:#1F4E79">Team {t_id}</td>'

            sport_entries = [(s, e) for name, s, e, c in result[t_id] if c == "sport"]
            cells = {"klas": "", "free": "", "sport": "", "test": "", "obed": ""}

            if sport_entries:
                cells["sport"] = f"{sport_entries[0][0]} – {sport_entries[-1][1]}"

            for name, s, e, cat in result[t_id]:
                if name == "Klasická masáž":
                    cells["klas"] = f"{s} – {e}"
                elif name == "Freestyle masáž":
                    cells["free"] = f"{s} – {e}"
                elif name == "Test":
                    cells["test"] = f"{s} – {e}"
                elif name == "Obed":
                    cells["obed"] = f"{s} – {e}"

            for cat in ["klas", "free", "sport", "test", "obed"]:
                if cells[cat]:
                    c = CAT_COLORS[cat]
                    html += f'<td style="background:{c["bg"]};color:{c["text"]};font-weight:500;border-radius:4px">{cells[cat]}</td>'
                else:
                    html += "<td>–</td>"

            html += "</tr>"

        html += "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)

    with tab2:
        start_min = config.start_time
        end_min = config.end_time

        tl_data = {}
        for t_id in sorted(result.keys()):
            timeline = {}
            for name, s, e, cat in result[t_id]:
                sm = int(s[:2]) * 60 + int(s[3:])
                em = int(e[:2]) * 60 + int(e[3:])
                short = {"Klasická masáž": "Klas.", "Freestyle masáž": "Free.",
                         "Hod medicinbalom": "Hod", "Frisbee na cieľ": "Fris.",
                         "Beh na 50m": "Beh", "Ľah-sed": "Ľah-s."}.get(name, name)
                for m in range(sm, em):
                    timeline[m] = (short, cat)
            tl_data[t_id] = timeline

        sorted_teams = sorted(result.keys())
        html = '<div class="timeline-wrap"><table class="timeline-table"><thead><tr>'
        html += '<th>Čas</th>'
        for t_id in sorted_teams:
            html += f'<th>T{t_id}</th>'
        html += '</tr></thead><tbody>'

        for slot in range(start_min, end_min, 5):
            html += '<tr>'
            html += f'<td class="time-col">{min_to_time(slot)}</td>'
            for t_id in sorted_teams:
                tl = tl_data[t_id]
                act, cat = "", None
                for m in range(slot, min(slot + 5, end_min)):
                    if m in tl:
                        act, cat = tl[m]
                        break
                if act and cat:
                    c = CAT_COLORS.get(cat, {"bg": "#eee", "text": "#333"})
                    html += f'<td style="background:{c["bg"]};color:{c["text"]};font-weight:500">{act}</td>'
                else:
                    html += '<td></td>'
            html += '</tr>'

        html += '</tbody></table></div>'
        st.markdown(html, unsafe_allow_html=True)

    with tab3:
        team_cols = st.columns([1, 4])
        with team_cols[0]:
            selected = st.selectbox("Vyber tím", [f"Team {t}" for t in sorted(result.keys())],
                                    label_visibility="collapsed")
        t_id = int(selected.split(" ")[1])

        entries = result[t_id]

        html = '<table class="team-detail-table"><thead><tr>'
        for h in ["Aktivita", "Čas", "Trvanie"]:
            html += f"<th>{h}</th>"
        html += "</tr></thead><tbody>"

        for name, s, e, cat in entries:
            dur = int(e[:2]) * 60 + int(e[3:]) - int(s[:2]) * 60 - int(s[3:])
            c = CAT_COLORS.get(cat, {"bg": "#eee", "text": "#333"})
            html += f'<tr style="background:{c["bg"]}20">'
            html += f'<td>{cat_badge(name, cat)}</td>'
            html += f'<td style="text-align:center;font-weight:500">{s} – {e}</td>'
            html += f'<td style="text-align:center">{dur} min</td>'
            html += "</tr>"

        html += "</tbody></table>"
        st.markdown(html, unsafe_allow_html=True)
