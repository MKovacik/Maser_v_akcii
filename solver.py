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
            name="Sprievodný program – Vojaci a Samaritáni", start_time=525, duration=30,
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
            name="Sprievodný program – NU det. TBC", start_time=840, duration=45,
            color_bg="#B4C7E7", color_text="#333333",
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


def _build_model(config, cp_model_module, team_group_starts=None):
    """Build the CP-SAT model. Returns (model, variables dict)."""
    N = config.num_teams
    H = config.start_time
    H_end = config.end_time
    D_mas = config.masaze_duration
    D_klas = config.masaze_activities[0].duration
    D_free = config.masaze_activities[1].duration
    D_sport = config.sport_duration
    D_test = config.test_duration
    TRANSFER = config.transfer_time

    model = cp_model_module.CpModel()

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

    # Non-floating shared events (e.g. obed)
    ev_group_vars = {}
    ev_start_vars = {}

    for ev_idx, ev in enumerate(config.shared_events):
        if not ev.overlaps_window(H, H_end):
            continue
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
            if ev.floating:
                continue
            if (ev_idx, t) not in ev_start_vars:
                continue

            ev_s = ev_start_vars[(ev_idx, t)]
            ev_dur = ev.duration

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
                        return None, None
                elif isinstance(si, int):
                    g_bools_j = ev_group_vars[(ej, t)]
                    for g in range(ev_j.num_groups):
                        gs_j = ev_j.group_starts[g]
                        if si + ev_i.duration > gs_j and gs_j + ev_j.duration > si:
                            model.add(g_bools_j[g] == 0)
                elif isinstance(sj, int):
                    g_bools_i = ev_group_vars[(ei, t)]
                    for g in range(ev_i.num_groups):
                        gs_i = ev_i.group_starts[g]
                        if gs_i + ev_i.duration > sj and sj + ev_j.duration > gs_i:
                            model.add(g_bools_i[g] == 0)
                else:
                    g_bools_i = ev_group_vars[(ei, t)]
                    g_bools_j = ev_group_vars[(ej, t)]
                    for gi in range(ev_i.num_groups):
                        gs_i = ev_i.group_starts[gi]
                        for gj in range(ev_j.num_groups):
                            gs_j = ev_j.group_starts[gj]
                            if (gs_i + ev_i.duration > gs_j
                                    and gs_j + ev_j.duration > gs_i):
                                model.add_bool_or([~g_bools_i[gi], ~g_bools_j[gj]])

    variables = {
        "masaze_start": masaze_start, "sport_start": sport_start, "test_start": test_start,
        "masaze_end": masaze_end, "sport_end": sport_end, "test_end": test_end,
        "ev_start_vars": ev_start_vars, "ev_group_vars": ev_group_vars,
    }
    return model, variables


def solve(config: SolverConfig):
    """Solve the scheduling problem. Returns teams dict (1-indexed) or None if infeasible."""
    from ortools.sat.python import cp_model

    N = config.num_teams
    H = config.start_time
    H_end = config.end_time

    # Identify floating events and their feasible group_starts
    floating_events = [ev for ev in config.shared_events if ev.floating]

    # Pass 1: minimize makespan
    model, variables = _build_model(config, cp_model)
    if model is None:
        return None

    masaze_start = variables["masaze_start"]
    sport_start = variables["sport_start"]
    test_start = variables["test_start"]
    masaze_end = variables["masaze_end"]
    sport_end = variables["sport_end"]
    test_end = variables["test_end"]
    ev_start_vars = variables["ev_start_vars"]
    ev_group_vars = variables["ev_group_vars"]

    makespan = model.new_int_var(H, H_end, "makespan")
    for t in range(N):
        model.add(makespan >= masaze_end[t])
        model.add(makespan >= sport_end[t])
        model.add(makespan >= test_end[t])
    model.minimize(makespan)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 10
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    optimal_makespan = solver.value(makespan)

    # Pass 2: fix makespan, maximize sprievodný program time
    # Sprievodný is a full activity with no-overlap constraints — solver can
    # rearrange activities to create space for it anywhere in the schedule.
    model2, variables2 = _build_model(config, cp_model)
    if model2 is None:
        return None

    masaze_start = variables2["masaze_start"]
    sport_start = variables2["sport_start"]
    test_start = variables2["test_start"]
    masaze_end = variables2["masaze_end"]
    sport_end = variables2["sport_end"]
    test_end = variables2["test_end"]
    ev_start_vars = variables2["ev_start_vars"]
    ev_group_vars = variables2["ev_group_vars"]

    # Fix makespan
    for t in range(N):
        model2.add(masaze_end[t] <= optimal_makespan)
        model2.add(sport_end[t] <= optimal_makespan)
        model2.add(test_end[t] <= optimal_makespan)

    float_group_bools = {}
    float_group_start_vars = {}
    float_dur_vars = {}

    total_spriev = 0
    for ev in floating_events:
        starts = sorted(ev.group_starts) if ev.group_starts else [ev.start_time]
        num_g = len(starts)
        sizes = ev.effective_group_sizes(N)

        all_g_bools = []
        for t in range(N):
            g_bools = [model2.new_bool_var(f"float_{ev.name}_{t}_g{g}") for g in range(num_g)]
            model2.add_exactly_one(g_bools)
            float_group_bools[(id(ev), t)] = g_bools
            all_g_bools.append(g_bools)

            # Group start variable
            gs_var = model2.new_int_var(min(starts), max(starts), f"float_gs_{ev.name}_{t}")
            for g in range(num_g):
                model2.add(gs_var == starts[g]).only_enforce_if(g_bools[g])
            float_group_start_vars[(id(ev), t)] = gs_var

            # Sprievodný as a real interval: start at group_start, variable duration
            spriev_dur = model2.new_int_var(ev.min_duration, ev.max_duration, f"spriev_dur_{t}")
            float_dur_vars[(id(ev), t)] = spriev_dur

            spriev_end = model2.new_int_var(H, H_end, f"spriev_end_{t}")
            model2.add(spriev_end == gs_var + spriev_dur)

            # No overlap: sprievodný must not collide with masáže/šport/test
            for label, a_start, a_end in [
                ("mas", masaze_start[t], masaze_end[t]),
                ("sport", sport_start[t], sport_end[t]),
                ("test", test_start[t], test_end[t]),
            ]:
                b = model2.new_bool_var(f"spriev_vs_{label}_{t}")
                model2.add(spriev_end <= a_start).only_enforce_if(b)
                model2.add(a_end <= gs_var).only_enforce_if(~b)

            # No overlap with non-floating shared events (e.g. obed)
            for ev_idx2, ev2 in enumerate(config.shared_events):
                if ev2.floating or not ev2.overlaps_window(H, H_end):
                    continue
                if (ev_idx2, t) not in ev_start_vars:
                    continue
                ev2_s = ev_start_vars[(ev_idx2, t)]
                ev2_dur = ev2.duration
                if isinstance(ev2_s, int):
                    b = model2.new_bool_var(f"spriev_vs_ev{ev_idx2}_{t}")
                    model2.add(spriev_end <= ev2_s).only_enforce_if(b)
                    model2.add(ev2_s + ev2_dur <= gs_var).only_enforce_if(~b)
                else:
                    ev2_g_bools = ev_group_vars[(ev_idx2, t)]
                    for g2 in range(ev2.num_groups):
                        gs2 = ev2.group_starts[g2]
                        ge2 = gs2 + ev2_dur
                        b = model2.new_bool_var(f"spriev_vs_ev{ev_idx2}_g{g2}_{t}")
                        model2.add(spriev_end <= gs2).only_enforce_if([ev2_g_bools[g2], b])
                        model2.add(ge2 <= gs_var).only_enforce_if([ev2_g_bools[g2], ~b])

            total_spriev += spriev_dur

        # Enforce group sizes
        for g in range(num_g):
            model2.add(sum(all_g_bools[t][g] for t in range(N)) <= sizes[g])

    model2.maximize(total_spriev)

    solver2 = cp_model.CpSolver()
    solver2.parameters.max_time_in_seconds = 10
    status2 = solver2.solve(model2)

    if status2 not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        solver2 = solver
        masaze_start = variables["masaze_start"]
        sport_start = variables["sport_start"]
        test_start = variables["test_start"]
        masaze_end = variables["masaze_end"]
        sport_end = variables["sport_end"]
        test_end = variables["test_end"]
        ev_start_vars = variables["ev_start_vars"]
        ev_group_vars = variables["ev_group_vars"]
        float_group_start_vars = {}
        float_dur_vars = {}

    # Build result
    teams = {}
    for t in range(N):
        entries = []

        ms = solver2.value(masaze_start[t])
        offset = 0
        for a in config.masaze_activities:
            entries.append((a.name, min_to_time(ms + offset),
                            min_to_time(ms + offset + a.duration), a.category))
            offset += a.duration

        ss = solver2.value(sport_start[t])
        offset = 0
        for a in config.sport_activities:
            entries.append((a.name, min_to_time(ss + offset),
                            min_to_time(ss + offset + a.duration), a.category))
            offset += a.duration

        ts = solver2.value(test_start[t])
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
                    es = solver2.value(ev_s)
            else:
                es = ev.get_start_for_team(t, N)
            ee = es + ev.duration
            entries.append((ev.name, min_to_time(es), min_to_time(ee), ev.category))

        # Add floating sprievodný program from solver result
        for ev in floating_events:
            if (id(ev), t) in float_group_start_vars and (id(ev), t) in float_dur_vars:
                gs = solver2.value(float_group_start_vars[(id(ev), t)])
                dur = solver2.value(float_dur_vars[(id(ev), t)])
                entries.append((ev.name, min_to_time(gs), min_to_time(gs + dur), ev.category))
            else:
                gs = ev.start_time
                entries.append((ev.name, min_to_time(gs),
                                min_to_time(gs + ev.min_duration), ev.category))

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
