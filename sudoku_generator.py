#!/usr/bin/env python3
import random
import argparse
import json
import time
from datetime import date, timedelta
from typing import List, Optional, Tuple

Grid = List[List[int]]

# -----------------------------
# Sudoku basics
# -----------------------------
def is_valid(grid: Grid, r: int, c: int, v: int) -> bool:
    if v in grid[r]:
        return False
    for i in range(9):
        if grid[i][c] == v:
            return False
    br, bc = (r // 3) * 3, (c // 3) * 3
    for rr in range(br, br + 3):
        for cc in range(bc, bc + 3):
            if grid[rr][cc] == v:
                return False
    return True

def find_empty(grid: Grid) -> Optional[Tuple[int, int]]:
    for r in range(9):
        for c in range(9):
            if grid[r][c] == 0:
                return r, c
    return None

def copy_grid(grid: Grid) -> Grid:
    return [row[:] for row in grid]

def solve(grid: Grid) -> bool:
    pos = find_empty(grid)
    if not pos:
        return True
    r, c = pos
    nums = list(range(1, 10))
    random.shuffle(nums)
    for v in nums:
        if is_valid(grid, r, c, v):
            grid[r][c] = v
            if solve(grid):
                return True
            grid[r][c] = 0
    return False

# -----------------------------
# Uniqueness check
# -----------------------------
def count_solutions(grid: Grid, limit: int = 2) -> int:
    pos = find_empty(grid)
    if not pos:
        return 1
    r, c = pos
    total = 0
    for v in range(1, 10):
        if is_valid(grid, r, c, v):
            grid[r][c] = v
            total += count_solutions(grid, limit)
            grid[r][c] = 0
            if total >= limit:
                return limit
    return total

def generate_solution(seed: int) -> Grid:
    random.seed(seed)
    grid = [[0] * 9 for _ in range(9)]
    solve(grid)
    return grid

# -----------------------------
# Difficulty settings (clues visible)
# -----------------------------
DIFFICULTY_CLUES = {
    "makkelijk": (36, 45),
    "gemiddeld": (30, 35),
    "moeilijk": (24, 29),
    "extreem": (18, 23),  # nog steeds extreem, maar haalbaar
}

def grid_to_str(grid: Grid) -> str:
    return "".join(str(grid[r][c]) for r in range(9) for c in range(9))

def make_puzzle_unique(solution: Grid, difficulty: str, time_limit_sec: float = 1.25) -> Tuple[Grid, int]:
    """
    Maak een puzzel met unieke oplossing.
    time_limit_sec voorkomt dat één puzzel eindeloos blijft hangen.
    """
    start_t = time.time()

    grid = copy_grid(solution)
    lo, hi = DIFFICULTY_CLUES[difficulty]
    target = random.randint(lo, hi)

    cells = [(r, c) for r in range(9) for c in range(9)]
    random.shuffle(cells)

    clues = 81
    for r, c in cells:
        if time.time() - start_t > time_limit_sec:
            raise TimeoutError("Puzzle generation took too long (time limit reached).")

        if clues <= target:
            break

        backup = grid[r][c]
        grid[r][c] = 0

        test = copy_grid(grid)
        if count_solutions(test, limit=2) != 1:
            grid[r][c] = backup
        else:
            clues -= 1

    return grid, clues

# -----------------------------
# Daily generation
# -----------------------------
WEEKDAY_TO_DIFF = {
    0: "makkelijk",
    1: "gemiddeld",
    2: "moeilijk",
    3: "gemiddeld",
    4: "makkelijk",
    5: "moeilijk",
    6: "gemiddeld",
}

def generate_daily(start_date: str, days: int) -> List[dict]:
    start = date.fromisoformat(start_date)
    results = []

    for i in range(days):
        d = start + timedelta(days=i)
        diff = WEEKDAY_TO_DIFF[d.weekday()]
        seed = int(d.strftime("%Y%m%d"))

        # probeer een paar keer als hij te langzaam is
        for attempt in range(1, 50):
            try:
                sol = generate_solution(seed + attempt)
                puzzle, clues = make_puzzle_unique(sol, diff, time_limit_sec=1.25)
                break
            except TimeoutError:
                continue
        else:
            raise RuntimeError(f"Kon geen daily puzzel maken voor {d.isoformat()} ({diff}).")

        results.append({
            "date": d.isoformat(),
            "difficulty": diff,
            "clues": clues,
            "puzzle": grid_to_str(puzzle),
            "solution": grid_to_str(sol)
        })

        if i % 100 == 0:
            print(f"Generated daily {i}/{days} ({d.isoformat()}, diff={diff})")

    return results

# -----------------------------
# Pack generation
# -----------------------------
def generate_pack(category: str, count: int, seed_base: int = 123456) -> List[dict]:
    if category not in DIFFICULTY_CLUES:
        raise ValueError(f"Onbekende categorie: {category}")

    results = []
    made = 0
    i = 1

    while made < count:
        seed = seed_base + i + (hash(category) % 100000)
        i += 1

        # meerdere pogingen per id totdat we een goede puzzel hebben
        ok = False
        for attempt in range(1, 80):
            try:
                sol = generate_solution(seed + attempt)
                puzzle, clues = make_puzzle_unique(sol, category, time_limit_sec=1.25)
                ok = True
                break
            except TimeoutError:
                continue

        if not ok:
            # skip deze seed, probeer volgende
            continue

        made += 1
        results.append({
            "id": made,
            "difficulty": category,
            "clues": clues,
            "puzzle": grid_to_str(puzzle),
            "solution": grid_to_str(sol)
        })

        if made % 100 == 0:
            print(f"Generated pack {category} {made}/{count}")

    return results

def main():
    p = argparse.ArgumentParser(description="Sudoku generator: daily or packs.")
    sub = p.add_subparsers(dest="mode", required=True)

    p_daily = sub.add_parser("daily", help="Generate date-based daily puzzles")
    p_daily.add_argument("--start-date", required=True, help="YYYY-MM-DD")
    p_daily.add_argument("--days", type=int, required=True)
    p_daily.add_argument("--out", default="daily.json")

    p_pack = sub.add_parser("pack", help="Generate puzzles for 1 category")
    p_pack.add_argument("--category", required=True, choices=list(DIFFICULTY_CLUES.keys()))
    p_pack.add_argument("--count", type=int, required=True)
    p_pack.add_argument("--out", required=True)
    p_pack.add_argument("--seed-base", type=int, default=123456)

    args = p.parse_args()

    if args.mode == "daily":
        data = generate_daily(args.start_date, args.days)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Klaar! {args.out} is aangemaakt met {len(data)} puzzels.")

    elif args.mode == "pack":
        data = generate_pack(args.category, args.count, seed_base=args.seed_base)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Klaar! {args.out} is aangemaakt met {len(data)} puzzels.")

if __name__ == "__main__":
    main()
