"""自己対戦評価基盤(再構築版 2026-08-05)。

使い方: python arena.py <挑戦者main.py> <現行チャンピオンmain.py> -n 400 --note "変更内容"

- 先攻後攻は自動で半々に入れ替える(偶数ゲームはA先攻、奇数はB先攻)。
- 勝率のWilson 95%CIを計算し、experiments.csv に1行追記する。
- 不正手(エンジンがIndexErrorを返す)はINVALID負け、エージェント例外はERROR負け。
- 各エージェントは自ディレクトリの deck.csv / engine_search.py / predict.py を使う。
"""
import argparse
import csv
import datetime
import importlib.util
import math
import os
import sys
import time
import traceback
from multiprocessing import Pool

STEP_LIMIT = 3000        # 無限ループ保険。超えたらdraw扱い
OVERAGE_BUDGET = 600.0   # 本番の持ち時間(秒)を模擬

_agents = None  # ワーカープロセス内の (modA, modB)


def _load_agent(path: str, name: str):
    path = os.path.abspath(path)
    d = os.path.dirname(path)
    if d not in sys.path:
        sys.path.insert(0, d)
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _init_worker(path_a: str, path_b: str):
    global _agents
    # 同名モジュール(engine_search等)は先勝ちで共有される。両ディレクトリの
    # 中身は同一なので問題ない(mainのみ別名でロード)。
    _agents = (_load_agent(path_a, "agent_a_main"), _load_agent(path_b, "agent_b_main"))


def _play_one(spec):
    """1試合実行。spec=(game_index, a_is_first). 戻り値: (aの結果, 種別, 先攻がAか)
    aの結果: 1=win 0=lose 0.5=draw / 種別: OK|INVALID|ERROR"""
    game_idx, a_first = spec
    from kaggle_environments.envs.cabt.cg.game import battle_start, battle_select, battle_finish
    mods = _agents if a_first else (_agents[1], _agents[0])
    decks = []
    for m in mods:
        decks.append(m.agent({"select": None}))
    obs, sd = battle_start(decks[0], decks[1])
    if obs is None:
        raise RuntimeError(f"battle_start failed: errorType={sd.errorType}")
    used = [0.0, 0.0]
    kind = "OK"
    loser = None
    try:
        steps = 0
        while obs["current"]["result"] < 0 and obs["select"] is not None and steps < STEP_LIMIT:
            cur = obs["current"]
            p = cur["yourIndex"]
            aobs = {
                "select": obs["select"],
                "current": cur,
                "logs": obs.get("logs", []),
                "search_begin_input": obs["search_begin_input"],
                "remainingOverageTime": max(0.0, OVERAGE_BUDGET - used[p]),
            }
            t0 = time.perf_counter()
            try:
                action = mods[p].agent(aobs)
            except Exception:
                traceback.print_exc()
                kind, loser = "ERROR", p
                break
            used[p] += time.perf_counter() - t0
            try:
                obs = battle_select(action)
            except (IndexError, ValueError):
                kind, loser = "INVALID", p
                break
            steps += 1
    finally:
        battle_finish()
    if loser is not None:
        winner = 1 - loser
    else:
        r = obs["current"]["result"]
        winner = r if r in (0, 1) else None  # None=draw
    if winner is None:
        a_res = 0.5
    else:
        a_won = (winner == 0) == a_first
        a_res = 1 if a_won else 0
    return (a_res, kind, a_first)


def wilson_ci(wins: float, n: int, z: float = 1.96):
    if n == 0:
        return (0.0, 1.0)
    p = wins / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (center - half, center + half)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("agent_a", help="挑戦者 main.py")
    ap.add_argument("agent_b", help="現行チャンピオン main.py")
    ap.add_argument("-n", type=int, default=400)
    ap.add_argument("-w", "--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--note", default="")
    ap.add_argument("--csv", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "experiments.csv"))
    args = ap.parse_args()

    specs = [(i, i % 2 == 0) for i in range(args.n)]
    t0 = time.time()
    win = lose = draw = invalid = error = 0
    first_win = first_n = second_win = second_n = 0
    results = []
    with Pool(args.workers, initializer=_init_worker,
              initargs=(args.agent_a, args.agent_b)) as pool:
        for i, (a_res, kind, a_first) in enumerate(
                pool.imap_unordered(_play_one, specs, chunksize=1), 1):
            results.append((a_res, kind, a_first))
            if a_res == 1:
                win += 1
            elif a_res == 0:
                lose += 1
            else:
                draw += 1
            if kind == "INVALID":
                invalid += 1
            elif kind == "ERROR":
                error += 1
            if a_first:
                first_n += 1
                first_win += a_res == 1
            else:
                second_n += 1
                second_win += a_res == 1
            if i % 20 == 0 or i == args.n:
                n = win + lose + draw
                wr = win / n if n else 0
                print(f"[{i}/{args.n}] A勝率 {wr:.3f} (W{win}/L{lose}/D{draw} "
                      f"inv{invalid} err{error}) {time.time()-t0:.0f}s", flush=True)

    n = win + lose + draw
    wr = win / n if n else 0.0
    lo, hi = wilson_ci(win, n)
    fwr = first_win / first_n if first_n else 0.0
    swr = second_win / second_n if second_n else 0.0
    row = [datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
           args.agent_a, args.agent_b, n, args.workers, win, lose, draw, invalid, error,
           round(wr, 4), round(lo, 4), round(hi, 4), round(fwr, 4), round(swr, 4),
           args.note]
    exists = os.path.exists(args.csv)
    with open(args.csv, "a", newline="") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow("timestamp,agent_a,agent_b,games,workers,win,lose,draw,invalid,"
                       "error,win_rate,ci_low,ci_high,first_win_rate,second_win_rate,note"
                       .split(","))
        w.writerow(row)
    print(f"\n=== {args.agent_a} vs {args.agent_b}: {n}戦 ===")
    print(f"勝率 {wr:.4f} [95%CI {lo:.4f}, {hi:.4f}]  先攻時 {fwr:.4f} / 後攻時 {swr:.4f}")
    print(f"W{win} L{lose} D{draw} INVALID{invalid} ERROR{error}  ({time.time()-t0:.0f}s)")
    print(f"→ {args.csv} に記録済み")


if __name__ == "__main__":
    main()
