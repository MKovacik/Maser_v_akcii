"""Generate a self-contained static HTML page from a solved schedule."""
import html
import os
import base64
from export_excel import add_transfers, time_to_min, min_to_time

BASE_CAT_COLORS = {
    "klas": {"bg": "#BDD7EE", "text": "#1a3a5c"},
    "free": {"bg": "#9BC2E6", "text": "#1a3a5c"},
    "sport": {"bg": "#C6EFCE", "text": "#1a4a2a"},
    "test": {"bg": "#FFE699", "text": "#5a4a00"},
    "presun": {"bg": "#E2EFDA", "text": "#333"},
}

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Calibri, Arial, sans-serif; background: #f5f7fa; color: #333; }
.container { max-width: 1200px; margin: 0 auto; padding: 16px; }

.header { display: flex; align-items: center; gap: 24px; padding: 16px 0 12px 0;
  border-bottom: 3px solid #1F4E79; margin-bottom: 20px; }
.header img { height: 60px; width: auto; }
.header h1 { color: #1F4E79; font-size: 2rem; font-weight: 700; }
.header .subtitle { color: #666; font-size: 0.95rem; margin-top: 2px; }

.stats { display: flex; gap: 16px; margin-bottom: 20px; flex-wrap: wrap; }
.stat-card { flex: 1; min-width: 140px; background: white; border-radius: 12px; padding: 16px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.06); border-left: 4px solid #1F4E79; text-align: center; }
.stat-card .value { font-size: 1.6rem; font-weight: 700; color: #1F4E79; }
.stat-card .label { font-size: 0.85rem; color: #888; margin-top: 4px; }

.legend { display: flex; flex-wrap: wrap; gap: 8px 16px; margin-bottom: 20px; }
.legend-item { display: inline-flex; align-items: center; gap: 6px; font-size: 0.85rem; }
.legend-dot { width: 14px; height: 14px; border-radius: 4px; display: inline-block; }

input[name="tabs"] { display: none; }
.tab-labels { display: flex; gap: 0; margin-bottom: 0; border-bottom: 2px solid #e0e0e0; }
.tab-labels label { padding: 12px 24px; font-size: 1rem; font-weight: 600; cursor: pointer;
  color: #666; border-bottom: 3px solid transparent; margin-bottom: -2px; transition: all 0.2s; }
.tab-labels label:hover { color: #1F4E79; }
#tab1:checked ~ .tab-labels label[for="tab1"],
#tab2:checked ~ .tab-labels label[for="tab2"],
#tab3:checked ~ .tab-labels label[for="tab3"] {
  color: #1F4E79; border-bottom-color: #1F4E79; }
.tab-content { display: none; padding: 20px 0; }
#tab1:checked ~ #content1,
#tab2:checked ~ #content2,
#tab3:checked ~ #content3 { display: block; }

.schedule-table { width: 100%; border-collapse: collapse; font-size: 0.9rem;
  border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.schedule-table thead th { background: #1F4E79; color: white; padding: 10px 14px;
  text-align: center; font-weight: 600; font-size: 0.85rem; }
.schedule-table tbody td { padding: 8px 12px; text-align: center;
  border-bottom: 1px solid #e8e8e8; font-size: 0.85rem; }

.timeline-wrap { max-height: 600px; overflow: auto; border-radius: 8px; border: 1px solid #e0e0e0; }
.timeline-table { border-collapse: collapse; font-size: 0.75rem; width: 100%;
  border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.timeline-table thead th { background: #1F4E79; color: white; padding: 6px 6px;
  text-align: center; font-weight: 600; font-size: 0.75rem;
  position: sticky; top: 0; z-index: 1; min-width: 70px; }
.timeline-table tbody td { padding: 4px 4px; text-align: center; border: 1px solid #e0e0e0;
  font-size: 0.7rem; white-space: nowrap; min-width: 70px; }
.timeline-table tbody td.time-col { font-weight: 600; background: #f0f4f8;
  padding: 4px 6px; color: #333; min-width: 50px; }

details { margin-bottom: 8px; }
details summary { background: #1F4E79; color: white; padding: 10px 16px; border-radius: 8px;
  cursor: pointer; font-weight: 600; font-size: 1rem; list-style: none; }
details summary::-webkit-details-marker { display: none; }
details summary::before { content: "\\25B6  "; font-size: 0.7rem; }
details[open] summary::before { content: "\\25BC  "; }
details[open] summary { border-radius: 8px 8px 0 0; }

.team-table { width: 100%; border-collapse: collapse; font-size: 0.9rem;
  box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.team-table thead th { background: #2874a6; color: white; padding: 10px 14px;
  text-align: left; font-weight: 600; }
.team-table tbody td { padding: 10px 14px; border-bottom: 1px solid #e8e8e8; }

.cat-badge { display: inline-block; padding: 3px 10px; border-radius: 12px;
  font-weight: 500; font-size: 0.8rem; }

.footer { text-align: center; padding: 24px 0; color: #999; font-size: 0.8rem;
  border-top: 1px solid #e0e0e0; margin-top: 24px; }

@media (max-width: 768px) {
  .header h1 { font-size: 1.4rem; }
  .stats { flex-direction: column; }
  .stat-card { min-width: auto; }
  .tab-labels label { padding: 10px 12px; font-size: 0.9rem; }
  .schedule-table, .timeline-table, .team-table { font-size: 0.8rem; }
  .schedule-table { display: block; overflow-x: auto; }
}
"""


def _esc(text):
    return html.escape(str(text))


def _build_cat_colors(config):
    colors = dict(BASE_CAT_COLORS)
    for ev in config.shared_events:
        colors[ev.category] = {"bg": ev.color_bg, "text": ev.color_text}
    return colors


def _cat_badge(text, cat, cat_colors):
    c = cat_colors.get(cat, {"bg": "#eee", "text": "#333"})
    return (f'<span class="cat-badge" style="background:{c["bg"]};'
            f'color:{c["text"]}">{_esc(text)}</span>')


def _build_legend(config, cat_colors):
    parts = []
    for a in config.masaze_activities:
        c = cat_colors[a.category]
        parts.append(f'<span class="legend-item">'
                     f'<span class="legend-dot" style="background:{c["bg"]}"></span>'
                     f'{_esc(a.name)}</span>')
    c = cat_colors["sport"]
    parts.append(f'<span class="legend-item">'
                 f'<span class="legend-dot" style="background:{c["bg"]}"></span>'
                 f'Športové disciplíny (telocvičňa ZŠ)</span>')
    for a in config.test_activities:
        c = cat_colors[a.category]
        parts.append(f'<span class="legend-item">'
                     f'<span class="legend-dot" style="background:{c["bg"]}"></span>'
                     f'{_esc(a.name)}</span>')
    for ev in config.shared_events:
        c = cat_colors.get(ev.category, {"bg": ev.color_bg})
        parts.append(f'<span class="legend-item">'
                     f'<span class="legend-dot" style="background:{c["bg"]}"></span>'
                     f'{_esc(ev.name)}</span>')
    return f'<div class="legend">{"".join(parts)}</div>'


def _build_overview(result, config, cat_colors):
    comp_start = config.start_time
    comp_end = config.end_time
    during_events = [ev for ev in config.shared_events
                     if ev.overlaps_window(comp_start, comp_end)]

    mas_cats = [a.category for a in config.masaze_activities]
    test_cat = config.test_activities[0].category
    mas_names = {a.name for a in config.masaze_activities}
    test_names = {a.name for a in config.test_activities}

    headers = ["Tím"] + [a.name for a in config.masaze_activities]
    headers += ["Športové disciplíny (telocvičňa ZŠ)", config.test_activities[0].name]
    for ev in during_events:
        headers.append(ev.name)

    h = '<table class="schedule-table"><thead><tr>'
    for hdr in headers:
        h += f"<th>{_esc(hdr)}</th>"
    h += "</tr></thead><tbody>"

    for t_id in sorted(result.keys()):
        h += "<tr>"
        h += f'<td style="font-weight:600;background:#f0f4f8;color:#1F4E79">Team {t_id}</td>'

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
                h += (f'<td style="background:{c["bg"]};color:{c["text"]};'
                      f'font-weight:500;border-radius:4px">{cells[cat_key]}</td>')
            else:
                h += "<td>–</td>"
        h += "</tr>"

    h += "</tbody></table>"
    return h


def _build_timeline(result, config, cat_colors):
    comp_start = config.start_time
    comp_end = config.end_time

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
            sm = time_to_min(s)
            em = time_to_min(e)
            short = abbrevs.get(name)
            if not short:
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

    def is_uniform(row_data):
        names = {full for _, _, full in row_data}
        cats = {cat for _, cat, _ in row_data}
        return len(names) == 1 and names != {""} and len(cats) == 1

    merge_spans = {}
    r = 0
    while r < len(grid):
        if is_uniform(grid[r]):
            full_name = grid[r][0][2]
            cat_key = grid[r][0][1]
            span = 1
            while (r + span < len(grid)
                   and is_uniform(grid[r + span])
                   and grid[r + span][0][2] == full_name):
                span += 1
            merge_spans[r] = (span, full_name, cat_key)
            r += span
        else:
            r += 1

    h = '<div class="timeline-wrap"><table class="timeline-table"><thead><tr>'
    h += '<th>Čas</th>'
    for t_id in sorted_teams:
        h += f'<th>T{t_id}</th>'
    h += '</tr></thead><tbody>'

    skip_rows = set()
    for r_idx, slot in enumerate(slots):
        h += '<tr>'
        h += f'<td class="time-col">{min_to_time(slot)}</td>'

        if r_idx in skip_rows:
            h += '</tr>'
            continue

        if r_idx in merge_spans:
            span, full_name, cat_key = merge_spans[r_idx]
            c = cat_colors.get(cat_key, {"bg": "#eee", "text": "#333"})
            h += (f'<td colspan="{len(sorted_teams)}" rowspan="{span}" '
                  f'style="background:{c["bg"]};color:{c["text"]};'
                  f'font-weight:600;font-size:0.85rem;text-align:center;'
                  f'vertical-align:middle">{_esc(full_name)}</td>')
            for skip in range(r_idx + 1, r_idx + span):
                skip_rows.add(skip)
        else:
            for act, cat_key, _ in grid[r_idx]:
                if act and cat_key:
                    c = cat_colors.get(cat_key, {"bg": "#eee", "text": "#333"})
                    h += (f'<td style="background:{c["bg"]};color:{c["text"]};'
                          f'font-weight:500">{_esc(act)}</td>')
                else:
                    h += '<td></td>'
        h += '</tr>'

    h += '</tbody></table></div>'
    return h


def _build_teams(result, config, cat_colors):
    shared_names = {ev.name for ev in config.shared_events}

    def station_lookup(act_name, sn):
        st = config.get_station(act_name)
        if st:
            return st
        if act_name in sn:
            return "shared"
        return None

    num_teams = config.num_teams
    during_events = [ev for ev in config.shared_events
                     if ev.overlaps_window(config.start_time, config.end_time)]

    parts = []
    for t_id in sorted(result.keys()):
        schedule = result[t_id]
        entries_with_transfers = add_transfers(schedule, shared_names, station_lookup)

        group_notes = {}
        for ev in during_events:
            if ev.num_groups > 1:
                sizes = ev.effective_group_sizes(num_teams)
                cumul = 0
                for g in range(ev.num_groups):
                    start_team = cumul + 1
                    cumul += sizes[g]
                    end_team = cumul
                    if start_team <= t_id <= end_team:
                        group_notes[ev.name] = f"{g+1}. skupina (tímy {start_team}–{end_team})"
                        break

        h = f'<details><summary>Team {t_id}</summary>'
        h += '<table class="team-table"><thead><tr>'
        for hdr in ["Aktivita", "Čas", "Trvanie", "Poznámka"]:
            h += f"<th>{_esc(hdr)}</th>"
        h += "</tr></thead><tbody>"

        for name, s, e, cat in entries_with_transfers:
            dur = time_to_min(e) - time_to_min(s)
            c = cat_colors.get(cat, {"bg": "#eee", "text": "#333"})
            note = group_notes.get(name, "")
            h += f'<tr style="background:{c["bg"]}20">'
            h += f'<td>{_cat_badge(name, cat, cat_colors)}</td>'
            h += f'<td style="text-align:center;font-weight:500">{s} – {e}</td>'
            h += f'<td style="text-align:center">{dur} min</td>'
            h += f'<td>{_esc(note)}</td>'
            h += "</tr>"

        h += "</tbody></table></details>"
        parts.append(h)

    return "\n".join(parts)


def generate_html(teams, config, logo_path=None):
    """Generate a self-contained HTML page. Returns HTML string."""
    cat_colors = _build_cat_colors(config)

    logo_tag = ""
    if logo_path and os.path.exists(logo_path):
        with open(logo_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        logo_tag = f'<img src="data:image/png;base64,{b64}" />'

    total_activities = sum(len(v) for v in teams.values())
    first_start = min(time_to_min(s) for entries in teams.values() for _, s, _, _ in entries)
    last_end = max(time_to_min(e) for entries in teams.values() for _, _, e, _ in entries)

    legend = _build_legend(config, cat_colors)
    overview = _build_overview(teams, config, cat_colors)
    timeline = _build_timeline(teams, config, cat_colors)
    team_details = _build_teams(teams, config, cat_colors)

    return f"""<!DOCTYPE html>
<html lang="sk">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Masér v akcii – Harmonogram</title>
<style>{CSS}</style>
</head>
<body>
<div class="container">

<div class="header">
  {logo_tag}
  <div>
    <h1>Masér v akcii</h1>
    <div class="subtitle">Harmonogram súťaže</div>
  </div>
</div>

<div class="stats">
  <div class="stat-card"><div class="value">{config.num_teams}</div><div class="label">Tímov</div></div>
  <div class="stat-card"><div class="value">{total_activities}</div><div class="label">Aktivít celkom</div></div>
  <div class="stat-card"><div class="value">{min_to_time(first_start)} – {min_to_time(last_end)}</div><div class="label">Čas súťaže</div></div>
  <div class="stat-card"><div class="value">{last_end - first_start} min</div><div class="label">Celkové trvanie</div></div>
</div>

{legend}

<input type="radio" name="tabs" id="tab1" checked>
<input type="radio" name="tabs" id="tab2">
<input type="radio" name="tabs" id="tab3">
<div class="tab-labels">
  <label for="tab1">Prehľad</label>
  <label for="tab2">Časová os</label>
  <label for="tab3">Po tímoch</label>
</div>

<div class="tab-content" id="content1">
{overview}
</div>

<div class="tab-content" id="content2">
{timeline}
</div>

<div class="tab-content" id="content3">
{team_details}
</div>

<div class="footer">Vygenerované aplikáciou Masér v akcii</div>

</div>
</body>
</html>"""
