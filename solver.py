"""CP-SAT based scheduler for Masér v akcii competition."""
import re
from dataclasses import dataclass, field
from math import ceil
from ortools.sat.python import cp_model


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
class SolverConfig:
    num_teams: int = 11
    start_time: int = 525       # 08:45
    end_time: int = 825         # 13:45
    klasicka_duration: int = 20
    freestyle_duration: int = 20
    sport_disciplines: list[tuple[str, int]] = field(default_factory=lambda: [
        ("Hod medicinbalom", 5),
        ("Ľah-sed", 5),
        ("Beh na 50m", 5),
        ("Frisbee na cieľ", 5),
    ])
    test_duration: int = 15
    transfer_time: int = 10
    shared_events: list[SharedEvent] = field(default_factory=lambda: [
        SharedEvent(
            name="Obed", start_time=660, duration=30,
            color_bg="#F8CBAD", color_text="#5a2a00",
            num_groups=2, group_starts=[660, 750],
        ),
    ])

    @property
    def masaze_duration(self):
        return self.klasicka_duration + self.freestyle_duration

    @property
    def sport_duration(self):
        return sum(d for _, d in self.sport_disciplines)


def min_to_time(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def solve(config: SolverConfig):
    """Solve the scheduling problem. Returns teams dict (1-indexed) or None if infeasible."""
    N = config.num_teams
    H = config.start_time
    H_end = config.end_time
    D_mas = config.masaze_duration
    D_klas = config.klasicka_duration
    D_free = config.freestyle_duration
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

        for ev_idx, ev in enumerate(config.shared_events):
            if not ev.overlaps_window(H, H_end):
                continue
            ev_start = ev.get_start_for_team(t, N)
            ev_end = ev_start + ev.duration

            for label, a_start, a_end in [
                ("mas", masaze_start[t], masaze_end[t]),
                ("sport", sport_start[t], sport_end[t]),
                ("test", test_start[t], test_end[t]),
            ]:
                b = model.new_bool_var(f"{label}_vs_ev{ev_idx}_{t}")
                model.add(a_end <= ev_start).only_enforce_if(b)
                model.add(a_start >= ev_end).only_enforce_if(~b)

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
        entries.append(("Klasická masáž", min_to_time(ms), min_to_time(ms + D_klas), "klas"))
        entries.append(("Freestyle masáž", min_to_time(ms + D_klas), min_to_time(ms + D_mas), "free"))

        ss = solver.value(sport_start[t])
        offset = 0
        for name, dur in config.sport_disciplines:
            entries.append((name, min_to_time(ss + offset), min_to_time(ss + offset + dur), "sport"))
            offset += dur

        ts = solver.value(test_start[t])
        entries.append(("Test", min_to_time(ts), min_to_time(ts + D_test), "test"))

        for ev in config.shared_events:
            ev_start = ev.get_start_for_team(t, N)
            entries.append((ev.name, min_to_time(ev_start),
                            min_to_time(ev_start + ev.duration), ev.category))

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
