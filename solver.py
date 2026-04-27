"""CP-SAT based scheduler for Masér v akcii competition."""
from dataclasses import dataclass, field
from math import ceil
from ortools.sat.python import cp_model


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
    lunch_duration: int = 30
    transfer_time: int = 10
    lunch_group1_start: int = 660   # 11:00
    lunch_group2_start: int = 750   # 12:30
    lunch_group1_size: int = 0      # 0 = auto (ceil(N/2))

    @property
    def masaze_duration(self):
        return self.klasicka_duration + self.freestyle_duration

    @property
    def sport_duration(self):
        return sum(d for _, d in self.sport_disciplines)

    @property
    def group1_size(self):
        if self.lunch_group1_size > 0:
            return self.lunch_group1_size
        return ceil(self.num_teams / 2)


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
    D_lunch = config.lunch_duration
    TRANSFER = config.transfer_time
    G1_SIZE = config.group1_size

    model = cp_model.CpModel()

    masaze_start = []
    sport_start = []
    test_start = []

    masaze_end = []
    sport_end = []
    test_end = []

    klas_itv = []
    free_itv = []
    sport_itv = []
    test_itv = []

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

        # Interval vars for NoOverlap
        ki = model.new_fixed_size_interval_var(ms, D_klas, f"klas_itv_{t}")
        klas_itv.append(ki)

        fs = model.new_int_var(H, H_end, f"free_start_{t}")
        model.add(fs == ms + D_klas)
        fi = model.new_fixed_size_interval_var(fs, D_free, f"free_itv_{t}")
        free_itv.append(fi)

        si = model.new_fixed_size_interval_var(ss, D_sport, f"sport_itv_{t}")
        sport_itv.append(si)

        ti = model.new_fixed_size_interval_var(ts, D_test, f"test_itv_{t}")
        test_itv.append(ti)

    # Resource constraints: no overlap on each station
    model.add_no_overlap(klas_itv)
    model.add_no_overlap(free_itv)
    model.add_no_overlap(sport_itv)
    model.add_no_overlap(test_itv)

    # Per-team constraints
    for t in range(N):
        # Pairwise ordering with transfer time between competition locations
        # Masáže vs Sport
        b_ms = model.new_bool_var(f"mas_before_sport_{t}")
        model.add(masaze_end[t] + TRANSFER <= sport_start[t]).only_enforce_if(b_ms)
        model.add(sport_end[t] + TRANSFER <= masaze_start[t]).only_enforce_if(~b_ms)

        # Masáže vs Test
        b_mt = model.new_bool_var(f"mas_before_test_{t}")
        model.add(masaze_end[t] + TRANSFER <= test_start[t]).only_enforce_if(b_mt)
        model.add(test_end[t] + TRANSFER <= masaze_start[t]).only_enforce_if(~b_mt)

        # Sport vs Test
        b_st = model.new_bool_var(f"sport_before_test_{t}")
        model.add(sport_end[t] + TRANSFER <= test_start[t]).only_enforce_if(b_st)
        model.add(test_end[t] + TRANSFER <= sport_start[t]).only_enforce_if(~b_st)

        # Lunch non-overlap with competition activities
        lunch_s = config.lunch_group1_start if t < G1_SIZE else config.lunch_group2_start
        lunch_e = lunch_s + D_lunch

        # Masáže must not overlap with lunch
        b_ml = model.new_bool_var(f"mas_before_lunch_{t}")
        model.add(masaze_end[t] <= lunch_s).only_enforce_if(b_ml)
        model.add(masaze_start[t] >= lunch_e).only_enforce_if(~b_ml)

        # Sport must not overlap with lunch
        b_sl = model.new_bool_var(f"sport_before_lunch_{t}")
        model.add(sport_end[t] <= lunch_s).only_enforce_if(b_sl)
        model.add(sport_start[t] >= lunch_e).only_enforce_if(~b_sl)

        # Test must not overlap with lunch
        b_tl = model.new_bool_var(f"test_before_lunch_{t}")
        model.add(test_end[t] <= lunch_s).only_enforce_if(b_tl)
        model.add(test_start[t] >= lunch_e).only_enforce_if(~b_tl)

    # Objective: minimize makespan
    makespan = model.new_int_var(H, H_end, "makespan")
    for t in range(N):
        model.add(makespan >= masaze_end[t])
        model.add(makespan >= sport_end[t])
        model.add(makespan >= test_end[t])
    model.minimize(makespan)

    # Solve
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30
    status = solver.solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    # Extract solution
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

        lunch_s = config.lunch_group1_start if t < G1_SIZE else config.lunch_group2_start
        entries.append(("Obed", min_to_time(lunch_s), min_to_time(lunch_s + D_lunch), "obed"))

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
