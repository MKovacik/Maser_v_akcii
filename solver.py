"""CP-SAT based scheduler for Masér v akcii competition."""
import re
from dataclasses import dataclass, field


@dataclass
class SharedEvent:
    name: str
    start_time: int
    duration: int
    color_bg: str = "#D9D9D9"
    color_text: str = "#333333"
    num_groups: int = 1
    group_starts: list[int] = field(default_factory=list)
    group_sizes: list[int] = field(default_factory=list)
    floating: bool = False
    min_duration: int = 0
    max_duration: int = 0

    @property
    def category(self) -> str:
        slug = re.sub(r'[^a-z0-9]', '_', self.name.lower().strip())
        return f"shared_{slug}"

    @property
    def end_time(self) -> int:
        return self.start_time + self.duration

    def effective_group_sizes(self, num_teams: int) -> list[int]:
        if self.group_sizes and sum(self.group_sizes) > 0:
            return list(self.group_sizes)
        base = num_teams // self.num_groups
        remainder = num_teams % self.num_groups
        return [base + (1 if i < remainder else 0) for i in range(self.num_groups)]

    def get_start_for_team(self, team_idx: int, num_teams: int) -> int:
        if self.num_groups <= 1:
            return self.start_time
        sizes = self.effective_group_sizes(num_teams)
        cumulative = 0
        for g, size in enumerate(sizes):
            cumulative += size
            if team_idx < cumulative:
                return self.group_starts[g]
        return self.group_starts[-1]

    def overlaps_window(self, window_start: int, window_end: int) -> bool:
        starts = self.group_starts if self.num_groups > 1 else [self.start_time]
        for s in starts:
            e = s + self.duration
            if s < window_end and e > window_start:
                return True
        return False


@dataclass
class Activity:
    name: str
    duration: int
    abbreviation: str = ""
    category: str = ""

    def __post_init__(self):
        if not self.abbreviation:
            word = self.name.split()[0]
            self.abbreviation = word if len(word) <= 6 else word[:5] + "."


@dataclass
class SolverConfig:
    num_teams: int = 11
    start_time: int = 525       # 08:45
    end_time: int = 825         # 13:45
    masaze_activities: list[Activity] = field(default_factory=lambda: [
        Activity("Klasická masáž (Penzión Caritas)", 25, "Klas.", "klas"),
        Activity("Freestyle masáž (Penzión Caritas)", 25, "Free.", "free"),
    ])
    sport_activities: list[Activity] = field(default_factory=lambda: [
        Activity("Hod medicinbalom", 5, "Hod", "sport"),
        Activity("Ľah-sed", 5, "Ľah-s.", "sport"),
        Activity("Beh na 50m", 5, "Beh", "sport"),
        Activity("Frisbee na cieľ", 5, "Fris.", "sport"),
        Activity("Zápis výsledkov", 5, "Zápis", "sport"),
    ])
    test_activities: list[Activity] = field(default_factory=lambda: [
        Activity("Test", 15, "Test", "test"),
    ])
    transfer_time: int = 10
    shared_events: list[SharedEvent] = field(default_factory=lambda: [
        SharedEvent(
            name="Registrácia", start_time=480, duration=30,
            color_bg="#D9D9D9", color_text="#333333",
        ),
        SharedEvent(
            name="Otvorenie súťaže", start_time=510, duration=15,
            color_bg="#D9D9D9", color_text="#333333",
        ),
        SharedEvent(
            name="Sprievodný program počas súťaže", start_time=525, duration=30,
            color_bg="#D9D9D9", color_text="#333333",
            num_groups=3, group_starts=[525, 615, 735],
            floating=True, min_duration=30, max_duration=90,
        ),
        SharedEvent(
            name="Obed", start_time=660, duration=30,
            color_bg="#F8CBAD", color_text="#5a2a00",
            num_groups=2, group_starts=[660, 750],
        ),
        SharedEvent(
            name="Ukončenie súťaže", start_time=825, duration=5,
            color_bg="#D9D9D9", color_text="#333333",
        ),
        SharedEvent(
            name="Sprievodný program po skončení súťaže", start_time=840, duration=45,
            color_bg="#D9D9D9", color_text="#333333",
        ),
        SharedEvent(
            name="Vyhlásenie výsledkov", start_time=900, duration=30,
            color_bg="#D9D9D9", color_text="#333333",
        ),
    ])

    @property
    def masaze_duration(self):
        return sum(a.duration for a in self.masaze_activities)

    @property
    def sport_duration(self):
        return sum(a.duration for a in self.sport_activities)

    @property
    def test_duration(self):
        return self.test_activities[0].duration

    @property
    def all_activity_names(self) -> set:
        return ({a.name for a in self.masaze_activities}
                | {a.name for a in self.sport_activities}
                | {a.name for a in self.test_activities})

    def get_station(self, name: str):
        if name in {a.name for a in self.masaze_activities}:
            return "masaze"
        if name in {a.name for a in self.sport_activities}:
            return "sport"
        if name in {a.name for a in self.test_activities}:
            return "test"
        return None

    def get_abbreviation(self, name: str) -> str:
        for a in self.masaze_activities + self.sport_activities + self.test_activities:
            if a.name == name:
                return a.abbreviation
        return name


def min_to_time(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def solve(config: SolverConfig):
    """Solve the scheduling problem. Returns teams dict (1-indexed) or None if infeasible."""
    from ortools.sat.python import cp_model

    N = config.num_teams
    H = config.start_time
    H_end = config.end_time
    D_mas = config.masaze_duration
    D_klas = config.masaze_activities[0].duration
    D_free = config.masaze_activities[1].duration
    D_sport = config.sport_duration
    D_test = config.test_duration
    TRANSFER = config.transfer_time

    model = cp_model.CpModel()

    masaze_start, sport_start, test_start = [], [], []
    masaze_end, sport_end, test_end = [], [], []
    klas_itv, free_itv, sport_itv, test_itv = [], [], [], []

    for t in range(N):
        ms = model.new_int_var(H, H_end - D_mas, f"masaze_start_{t}")
        ss = model.new_int_var(H, H_end - D_sport, f"sport_start_{t}")
        ts = model.new_int_var(H, H_end - D_test, f"test_start_{t}")

        masaze_start.append(ms)
        sport_start.append(ss)
        test_start.append(ts)

        me = model.new_int_var(H, H_end, f"masaze_end_{t}")
        model.add(me == ms + D_mas)
        masaze_end.append(me)

        se = model.new_int_var(H, H_end, f"sport_end_{t}")
        model.add(se == ss + D_sport)
        sport_end.append(se)

        te = model.new_int_var(H, H_end, f"test_end_{t}")
        model.add(te == ts + D_test)
        test_end.append(te)

        klas_itv.append(model.new_fixed_size_interval_var(ms, D_klas, f"klas_itv_{t}"))

        fs = model.new_int_var(H, H_end, f"free_start_{t}")
        model.add(fs == ms + D_klas)
        free_itv.append(model.new_fixed_size_interval_var(fs, D_free, f"free_itv_{t}"))

        sport_itv.append(model.new_fixed_size_interval_var(ss, D_sport, f"sport_itv_{t}"))
        test_itv.append(model.new_fixed_size_interval_var(ts, D_test, f"test_itv_{t}"))

    model.add_no_overlap(klas_itv)
    model.add_no_overlap(free_itv)
    model.add_no_overlap(sport_itv)
    model.add_no_overlap(test_itv)

    for t in range(N):
        b_ms = model.new_bool_var(f"mas_before_sport_{t}")
        model.add(masaze_end[t] + TRANSFER <= sport_start[t]).only_enforce_if(b_ms)
        model.add(sport_end[t] + TRANSFER <= masaze_start[t]).only_enforce_if(~b_ms)

        b_mt = model.new_bool_var(f"mas_before_test_{t}")
        model.add(masaze_end[t] + TRANSFER <= test_start[t]).only_enforce_if(b_mt)
        model.add(test_end[t] + TRANSFER <= masaze_start[t]).only_enforce_if(~b_mt)

        b_st = model.new_bool_var(f"sport_before_test_{t}")
        model.add(sport_end[t] + TRANSFER <= test_start[t]).only_enforce_if(b_st)
        model.add(test_end[t] + TRANSFER <= sport_start[t]).only_enforce_if(~b_st)

    # For multi-group events, let the solver choose which group each team attends
    ev_group_vars = {}  # (ev_idx, t) -> group var
    ev_start_vars = {}  # (ev_idx, t) -> start int var

    for ev_idx, ev in enumerate(config.shared_events):
        if not ev.overlaps_window(H, H_end):
            continue
        # Floating events are not constrained by solver — filled in post-processing
        if ev.floating:
            continue

        if ev.num_groups > 1:
            sizes = ev.effective_group_sizes(N)
            group_bools = []
            for t in range(N):
                t_bools = []
                for g in range(ev.num_groups):
                    t_bools.append(model.new_bool_var(f"ev{ev_idx}_t{t}_g{g}"))
                group_bools.append(t_bools)
                model.add_exactly_one(t_bools)

                ev_s = model.new_int_var(min(ev.group_starts), max(ev.group_starts),
                                         f"ev{ev_idx}_start_{t}")
                for g in range(ev.num_groups):
                    model.add(ev_s == ev.group_starts[g]).only_enforce_if(t_bools[g])
                ev_start_vars[(ev_idx, t)] = ev_s
                ev_group_vars[(ev_idx, t)] = t_bools

            for g in range(ev.num_groups):
                model.add(sum(group_bools[t][g] for t in range(N)) == sizes[g])
        else:
            for t in range(N):
                ev_start_vars[(ev_idx, t)] = ev.start_time

    # Shared events must not overlap with main activities
    for t in range(N):
        for ev_idx, ev in enumerate(config.shared_events):
            if not ev.overlaps_window(H, H_end):
                continue
            if (ev_idx, t) not in ev_start_vars:
                continue

            ev_s = ev_start_vars[(ev_idx, t)]
            # For floating events, only block min_duration (teams can leave early)
            ev_dur = ev.min_duration if ev.floating else ev.duration

            # Floating events have no solver constraints — they fill gaps in output
            if ev.floating:
                continue

            if isinstance(ev_s, int):
                if ev_s >= H_end:
                    continue
                for label, a_start, a_end in [
                    ("mas", masaze_start[t], masaze_end[t]),
                    ("sport", sport_start[t], sport_end[t]),
                    ("test", test_start[t], test_end[t]),
                ]:
                    b = model.new_bool_var(f"{label}_vs_ev{ev_idx}_{t}")
                    model.add(a_end <= ev_s).only_enforce_if(b)
                    model.add(a_start >= ev_s + ev_dur).only_enforce_if(~b)
            else:
                g_bools = ev_group_vars[(ev_idx, t)]
                for g in range(ev.num_groups):
                    gs = ev.group_starts[g]
                    ge = gs + ev_dur
                    if gs >= H_end:
                        continue
                    for label, a_start, a_end in [
                        ("mas", masaze_start[t], masaze_end[t]),
                        ("sport", sport_start[t], sport_end[t]),
                        ("test", test_start[t], test_end[t]),
                    ]:
                        b = model.new_bool_var(f"{label}_vs_ev{ev_idx}_g{g}_{t}")
                        model.add(a_end <= gs).only_enforce_if([g_bools[g], b])
                        model.add(a_start >= ge).only_enforce_if([g_bools[g], ~b])

        # Shared events must not overlap each other for the same team
        ev_indices = [i for i, ev in enumerate(config.shared_events)
                      if ev.overlaps_window(H, H_end) and (i, t) in ev_start_vars]
        for i_pos in range(len(ev_indices)):
            for j_pos in range(i_pos + 1, len(ev_indices)):
                ei = ev_indices[i_pos]
                ej = ev_indices[j_pos]
                ev_i = config.shared_events[ei]
                ev_j = config.shared_events[ej]
                si = ev_start_vars[(ei, t)]
                sj = ev_start_vars[(ej, t)]

                if isinstance(si, int) and isinstance(sj, int):
                    if si + ev_i.duration > sj and sj + ev_j.duration > si:
                        return None
                elif isinstance(si, int):
                    # si fixed, sj variable — for each group of ej, check feasibility
                    g_bools_j = ev_group_vars[(ej, t)]
                    for g in range(ev_j.num_groups):
                        gs_j = ev_j.group_starts[g]
                        # If overlap between fixed si and this group's time
                        if si + ev_i.duration > gs_j and gs_j + ev_j.duration > si:
                            model.add(g_bools_j[g] == 0)
                elif isinstance(sj, int):
                    g_bools_i = ev_group_vars[(ei, t)]
                    for g in range(ev_i.num_groups):
                        gs_i = ev_i.group_starts[g]
                        if gs_i + ev_i.duration > sj and sj + ev_j.duration > gs_i:
                            model.add(g_bools_i[g] == 0)
                else:
                    # Both variable — for each pair of groups, forbid overlapping ones
                    g_bools_i = ev_group_vars[(ei, t)]
                    g_bools_j = ev_group_vars[(ej, t)]
                    for gi in range(ev_i.num_groups):
                        gs_i = ev_i.group_starts[gi]
                        for gj in range(ev_j.num_groups):
                            gs_j = ev_j.group_starts[gj]
                            if (gs_i + ev_i.duration > gs_j
                                    and gs_j + ev_j.duration > gs_i):
                                # These two groups overlap — can't both be chosen
                                model.add_bool_or([~g_bools_i[gi], ~g_bools_j[gj]])

    makespan = model.new_int_var(H, H_end, "makespan")
    for t in range(N):
        model.add(makespan >= masaze_end[t])
        model.add(makespan >= sport_end[t])
        model.add(makespan >= test_end[t])
    model.minimize(makespan)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    teams = {}
    for t in range(N):
        entries = []

        ms = solver.value(masaze_start[t])
        offset = 0
        for a in config.masaze_activities:
            entries.append((a.name, min_to_time(ms + offset),
                            min_to_time(ms + offset + a.duration), a.category))
            offset += a.duration

        ss = solver.value(sport_start[t])
        offset = 0
        for a in config.sport_activities:
            entries.append((a.name, min_to_time(ss + offset),
                            min_to_time(ss + offset + a.duration), a.category))
            offset += a.duration

        ts = solver.value(test_start[t])
        for a in config.test_activities:
            entries.append((a.name, min_to_time(ts),
                            min_to_time(ts + a.duration), a.category))

        for ev_idx, ev in enumerate(config.shared_events):
            if ev.floating:
                continue

            if (ev_idx, t) in ev_start_vars:
                ev_s = ev_start_vars[(ev_idx, t)]
                if isinstance(ev_s, int):
                    es = ev_s
                else:
                    es = solver.value(ev_s)
            else:
                es = ev.get_start_for_team(t, N)
            ee = es + ev.duration
            entries.append((ev.name, min_to_time(es), min_to_time(ee), ev.category))

        entries.sort(key=lambda x: x[1])

        # Post-processing: fill largest gap with floating sprievodný program
        for ev in config.shared_events:
            if not ev.floating:
                continue
            starts = sorted(ev.group_starts) if ev.group_starts else [ev.start_time]
            # Find gaps between consecutive entries (within competition window)
            comp_entries = [(int(s[:2])*60+int(s[3:]), int(e[:2])*60+int(e[3:]))
                           for _, s, e, c in entries
                           if int(s[:2])*60+int(s[3:]) >= H]
            comp_entries.sort()
            # Also consider gap from competition start to first entry
            gaps = []
            if comp_entries:
                if comp_entries[0][0] > H:
                    gaps.append((H, comp_entries[0][0]))
                for i in range(len(comp_entries) - 1):
                    gap_start = comp_entries[i][1]
                    gap_end = comp_entries[i + 1][0]
                    if gap_end - gap_start > 0:
                        gaps.append((gap_start, gap_end))

            # Find best gap: largest one that contains a group_start
            best = None
            best_dur = 0
            for gap_s, gap_e in gaps:
                for gs in starts:
                    # group_start must fall within gap
                    if gs >= gap_s and gs < gap_e:
                        avail = min(gap_e - gs, ev.max_duration)
                        if avail >= ev.min_duration and avail > best_dur:
                            best = (gs, gs + avail)
                            best_dur = avail
            if best:
                entries.append((ev.name, min_to_time(best[0]),
                                min_to_time(best[1]), ev.category))
                entries.sort(key=lambda x: x[1])

        teams[t + 1] = entries

    return teams


if __name__ == "__main__":
    config = SolverConfig()
    result = solve(config)
    if result is None:
        print("INFEASIBLE — no valid schedule found")
    else:
        for t_id, entries in sorted(result.items()):
            print(f"\nTeam {t_id}:")
            for name, s, e, cat in entries:
                print(f"  {s} - {e}  {name}")
