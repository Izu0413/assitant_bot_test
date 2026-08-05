"""PTCG AI Battle Challenge エージェント(Crustle軸)。

デッキ: Mega Kangaskhan ex + Crustle壁(NAIC 2026 5位 Rahul Reddy 型の移植)。
戦略: Kangaskhanをバトル場に立てて Run Errand(毎ターン2ドロー)を回しつつ
Rapid-Fire Combo(無色3エネ200+)で殴る。相手がex主体ならCrustle壁で受ける。

構造は旧Abomasnow版(agent_abomasnow/main.py)と同一。カード知識テーブルと
評価関数のみこのデッキ用に置き換えている。
"""
import os

# ---- SDK enum定数(cg/api.py より) ----
SELECT_MAIN, SELECT_CARD, SELECT_ATTACHED_CARD, SELECT_CARD_OR_ATTACHED, SELECT_ENERGY = 0, 1, 2, 3, 4
SELECT_SKILL, SELECT_ATTACK, SELECT_EVOLVE, SELECT_COUNT, SELECT_YES_NO, SELECT_SPECIAL = 5, 6, 7, 8, 9, 10

OPT_NUMBER, OPT_YES, OPT_NO, OPT_CARD, OPT_TOOL_CARD, OPT_ENERGY_CARD, OPT_ENERGY = 0, 1, 2, 3, 4, 5, 6
OPT_PLAY, OPT_ATTACH, OPT_EVOLVE, OPT_ABILITY, OPT_DISCARD, OPT_RETREAT, OPT_ATTACK, OPT_END = 7, 8, 9, 10, 11, 12, 13, 14

AREA_DECK, AREA_HAND, AREA_DISCARD, AREA_ACTIVE, AREA_BENCH = 1, 2, 3, 4, 5

CTX_SETUP_ACTIVE, CTX_SETUP_BENCH, CTX_SWITCH = 1, 2, 3
CTX_TO_ACTIVE, CTX_TO_BENCH, CTX_TO_FIELD, CTX_TO_HAND, CTX_DISCARD = 4, 5, 6, 7, 8
CTX_ATTACH_TO = 22
CTX_ATTACK = 35
CTX_DRAW_COUNT = 38
CTX_IS_FIRST, CTX_MULLIGAN, CTX_ACTIVATE, CTX_FIRST_EFFECT, CTX_MORE_DEVOLVE, CTX_COIN_HEAD = 41, 42, 43, 44, 45, 46

# ---- カードID(このデッキで使用) ----
ENERGY_GRASS = 1
ENERGY_MIST = 11
ENERGY_SPIKY = 14
ENERGY_IDS = (ENERGY_GRASS, ENERGY_MIST, ENERGY_SPIKY)
KANGASKHAN = 756       # Mega Kangaskhan ex: HP300基本, Run Errand=毎ターン2ドロー
DWEBBLE = 344          # Ascensionで山札から即進化
CRUSTLE = 345          # 特性: 相手exから被ダメ0の壁
POFFIN = 1086          # HP70以下の基本を2体ベンチへ
HAND_TRIMMER = 1087
ULTRA_BALL = 1121
POKEGEAR = 1122
SWITCH = 1123
ICE_CREAM = 1147       # エネ3個以上のアクティブを80回復
HEROS_CAPE = 1159      # HP+100 どうぐ
HANDHELD_FAN = 1161
BOSS_ORDERS = 1182
ERI = 1186
BIANCA = 1190
XEROSIC = 1197
LISIA = 1204
PETREL = 1219
HILDA = 1225
LILLIE = 1227
COMMUNITY_CENTER = 1242
FESTIVAL_GROUNDS = 1245
ROCKET_FACTORY = 1257

# 攻撃ID(エンジンの AllAttack() から転記)
ATK_RAPID_FIRE = 1092   # Kangaskhan ●●●→200+コイン
ATK_SCISSORS = 479      # Crustle {G}●●→120(効果無視)
ATK_ASCENSION = 478     # Dwebble 山札から進化
ATTACK_PREFERENCE = [ATK_RAPID_FIRE, ATK_SCISSORS, ATK_ASCENSION]

# 山札から手札に加える際の優先度(先頭ほど優先)
FETCH_RANK = [KANGASKHAN, CRUSTLE, DWEBBLE, ICE_CREAM, BOSS_ORDERS, LILLIE,
              ENERGY_GRASS, ENERGY_MIST, ENERGY_SPIKY, HEROS_CAPE, POFFIN, HILDA, PETREL]
# 捨てる際の優先度(先頭ほど惜しくない)
DISCARD_RANK = [SWITCH, HANDHELD_FAN, HAND_TRIMMER, POKEGEAR, ERI, XEROSIC, LISIA, BIANCA,
                FESTIVAL_GROUNDS, COMMUNITY_CENTER, ROCKET_FACTORY, HILDA, PETREL,
                ENERGY_GRASS, ENERGY_MIST, ENERGY_SPIKY, POFFIN, ULTRA_BALL, BOSS_ORDERS,
                LILLIE, ICE_CREAM, DWEBBLE, HEROS_CAPE, CRUSTLE, KANGASKHAN]

_DECK_CACHE = None


def _agent_dir() -> str:
    """このエージェントのディレクトリ。Kaggleはmain.pyをexec()で読み込むため
    __file__ が存在しない — その場合は既定の配置場所を返す。"""
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:
        return "/kaggle_simulations/agent"


def _read_deck() -> list:
    global _DECK_CACHE
    if _DECK_CACHE is None:
        candidates = [
            os.path.join(_agent_dir(), "deck.csv"),
            "/kaggle_simulations/agent/deck.csv",
            "deck.csv",
        ]
        for path in candidates:
            if os.path.exists(path):
                with open(path) as f:
                    _DECK_CACHE = [int(x) for x in f.read().split()[:60]]
                return _DECK_CACHE
        # どの場所にも無い場合は埋め込みデッキで続行(公式ローカルランナー等、
        # __file__もcwdも当てにならない環境への最終フォールバック)
        _DECK_CACHE = list(_EMBEDDED_DECK)
    return _DECK_CACHE


_EMBEDDED_DECK = [756, 756, 756, 756, 344, 344, 344, 345, 345, 345, 1227, 1227, 1227, 1227, 1182, 1182, 1182, 1182, 1219, 1219, 1219, 1219, 1225, 1225, 1186, 1186, 1197, 1, 1190, 1204, 1147, 1147, 1147, 1147, 1122, 1122, 1122, 1086, 1086, 1121, 1123, 1087, 1159, 1161, 1257, 1242, 1245, 14, 14, 14, 14, 1, 1, 1, 1, 11, 11, 11, 11, 1]


def _clamp_count(indices: list, select: dict) -> list:
    """選択数を [minCount, maxCount] に収め、重複を除いて返す。"""
    seen, unique = set(), []
    for i in indices:
        if i not in seen:
            seen.add(i)
            unique.append(i)
    lo, hi = select["minCount"], select["maxCount"]
    unique = unique[:hi]
    n_options = len(select["option"])
    pad = 0
    while len(unique) < lo and pad < n_options:
        if pad not in seen:
            unique.append(pad)
            seen.add(pad)
        pad += 1
    return unique


def _hand(state: dict) -> list:
    me = state["players"][state["yourIndex"]]
    return me["hand"] or []


def _hand_ids(state: dict) -> list:
    return [c["id"] for c in _hand(state)]


def _card_id_of_option(opt: dict, state: dict, select: dict):
    """CARD/PLAY系オプションが指すカードIDを解決する(分かる範囲で)。"""
    area, idx = opt.get("area"), opt.get("index")
    me = state["players"][state["yourIndex"]] if state else None
    if area == AREA_DECK and select.get("deck") is not None and idx is not None:
        if 0 <= idx < len(select["deck"]):
            return select["deck"][idx]["id"]
    if area == AREA_HAND and me and me["hand"] and idx is not None:
        if 0 <= idx < len(me["hand"]):
            return me["hand"][idx]["id"]
    if area == AREA_BENCH and me and idx is not None and 0 <= idx < len(me["bench"]):
        return me["bench"][idx]["id"]
    if area == AREA_ACTIVE and me and me["active"] and me["active"][0]:
        return me["active"][0]["id"]
    return opt.get("cardId")


def _rank_index(card_id, rank: list) -> int:
    try:
        return rank.index(card_id)
    except ValueError:
        return len(rank)


def _select_cards_by_rank(select: dict, state: dict, rank: list, take_max: bool) -> list:
    """CARD選択をランキング順に選ぶ。take_max=Trueなら取れるだけ、Falseなら最小限。"""
    scored = []
    for i, opt in enumerate(select["option"]):
        cid = _card_id_of_option(opt, state, select)
        scored.append((_rank_index(cid, rank), i))
    scored.sort()
    count = select["maxCount"] if take_max else max(select["minCount"], 0)
    return _clamp_count([i for _, i in scored[:count]], select)


def _opp_active(state: dict):
    opp = state["players"][1 - state["yourIndex"]]
    act = opp.get("active") or []
    return act[0] if act and act[0] else None


def _opp_wall_active(state: dict) -> bool:
    """相手のアクティブがCrustle壁(=こちらのMega exの攻撃が0になる)か。"""
    act = _opp_active(state)
    return bool(act and act["id"] == CRUSTLE)


def _my_active_is(state: dict, card_id: int) -> bool:
    me = state["players"][state["yourIndex"]]
    act = me.get("active") or []
    return bool(act and act[0] and act[0]["id"] == card_id)


def _bench_crustle_ready(state: dict, min_energy: int) -> bool:
    """ベンチにエネルギーの乗ったCrustle(壁割りアタッカー)がいるか。"""
    me = state["players"][state["yourIndex"]]
    return any(p["id"] == CRUSTLE and len(p["energies"]) >= min_energy
               for p in me["bench"])


def _attack_bonus(attack_id, state: dict) -> float:
    # 壁モード: 相手アクティブがCrustleの間、Kangaskhanの攻撃は0ダメージ。
    # END(0点)より下げて無意味な攻撃をやめる(相手にSpiky Energyが付いていると
    # 攻撃側が20ダメージ受けるため実害もある)
    if _opp_wall_active(state) and _my_active_is(state, KANGASKHAN):
        return -35
    if attack_id in ATTACK_PREFERENCE:
        return len(ATTACK_PREFERENCE) - ATTACK_PREFERENCE.index(attack_id)
    return 0


def _main_option_score(opt: dict, state: dict) -> float:
    """メインフェイズの行動候補を採点する。大きいほど優先。"""
    t = opt["type"]
    me = state["players"][state["yourIndex"]]
    active = me["active"][0] if me["active"] else None
    active_energy = len(active["energies"]) if active else 0
    active_damage = (active["maxHp"] - active["hp"]) if active else 0
    hand_ids = _hand_ids(state)

    if t == OPT_ABILITY:
        return 85  # Run Errand(毎ターン2ドロー)は常に使う

    if t == OPT_EVOLVE:
        return 90  # Dwebble→Crustle

    if t == OPT_ATTACH:
        cid = None
        if opt.get("area") == AREA_HAND and opt.get("index") is not None:
            hand = _hand(state)
            if 0 <= opt["index"] < len(hand):
                cid = hand[opt["index"]]["id"]
        to_active = opt.get("inPlayArea") == AREA_ACTIVE
        if cid == HEROS_CAPE:
            return 76 if to_active else 56
        if cid == HANDHELD_FAN:
            return 40
        # 壁モード: 相手がCrustle壁ならエネルギーは自陣のCrustle/Dwebbleへ
        # (壁を割れるのは非exのCrustleのSuperb Scissorsだけ)
        if _opp_wall_active(state) and opt.get("inPlayArea") == AREA_BENCH:
            idx = opt.get("inPlayIndex")
            bench = me["bench"]
            if idx is not None and 0 <= idx < len(bench) and bench[idx]["id"] in (CRUSTLE, DWEBBLE):
                return 85
        # エネルギー: Rapid-Fireの3個をバトル場優先、その後ベンチの後続を育てる
        if to_active:
            return 80 if active_energy < 3 else 40
        # ベンチ装着は付け先の個体で差を付ける(実戦敗着: 一律60で誤配分していた)
        if opt.get("inPlayArea") == AREA_BENCH:
            idx = opt.get("inPlayIndex")
            bench = me["bench"]
            if idx is not None and 0 <= idx < len(bench):
                p = bench[idx]
                if p["id"] == KANGASKHAN and len(p["energies"]) < 3:
                    return 62  # 次のアタッカー育成が最優先
                if p["id"] in (CRUSTLE, DWEBBLE) and len(p["energies"]) < 3:
                    return 55
                return 25  # 育成済み/非アタッカーへの装着は後回し
        return 60

    if t == OPT_PLAY:
        hand = _hand(state)
        idx = opt.get("index")
        cid = hand[idx]["id"] if (idx is not None and 0 <= idx < len(hand)) else None
        bench_count = len(me["bench"])
        if cid in (KANGASKHAN, DWEBBLE):
            return 70 if bench_count < 2 else 25
        if cid == ICE_CREAM:
            # エネ3個以上のアクティブが80点分傷ついているときだけ価値がある
            return 75 if (active_energy >= 3 and active_damage >= 80) else 0
        if cid == POFFIN:
            return 55 if bench_count < 3 else 5
        if cid == LILLIE:
            return 62 if me["handCount"] <= 3 else 8
        if cid == POKEGEAR:
            return 50
        if cid == HILDA:
            return 48 if CRUSTLE not in hand_ids else 20
        if cid == ULTRA_BALL:
            if bench_count == 0 and me["handCount"] >= 3:
                return 72
            return 50 if (KANGASKHAN not in hand_ids and me["handCount"] >= 3) else 6
        if cid == PETREL:
            return 45
        if cid == BOSS_ORDERS:
            # 壁モード: Bossで壁の裏を引きずり出すのが最重要行動になる
            return 78 if _opp_wall_active(state) else 44
        if cid == ERI:
            return 42
        if cid == XEROSIC:
            return 41
        if cid == LISIA:
            return 40
        if cid == BIANCA:
            # 残りHP30以下なら全回復 — 実戦敗着分析(episode 89851917)より、
            # 瀕死時はエネルギー装着(80)よりも優先して回復する
            return 82 if (active and active["hp"] <= 30) else 0
        if cid in (COMMUNITY_CENTER, FESTIVAL_GROUNDS, ROCKET_FACTORY):
            return 46 if not state["stadium"] else 0
        if cid == HAND_TRIMMER:
            return 35 if me["handCount"] >= 6 else 0
        if cid == SWITCH:
            # 交代ピボットは撤回: Kangaskhanを下げるとRun Errand(毎ターン2ドロー)が
            # 止まり、ミラー勝率が下がった(実測57.0%→51.2%)
            return 3
        return 10

    if t == OPT_ATTACK:
        return 30 + _attack_bonus(opt.get("attackId"), state)

    if t == OPT_RETREAT:
        # にげるはエネルギー3枚を捨てるコストが重く、壁モードでも割に合わない
        # (計測: リトリート交代ありはミラー53.7% vs なし57.0%)
        return 1
    if t == OPT_END:
        return 0
    return 2


def _choose_yes_no(select: dict, want_yes: bool) -> list:
    for i, opt in enumerate(select["option"]):
        if (opt["type"] == OPT_YES) == want_yes:
            return [i]
    return [0]


def rules_decide(obs: dict) -> list:
    """ルールベースの意思決定(探索のロールアウト内でも再利用する)。"""
    select = obs["select"]
    state = obs.get("current")
    stype = select["type"]
    ctx = select["context"]
    options = select["option"]

    if stype == SELECT_MAIN:
        best = max(range(len(options)), key=lambda i: _main_option_score(options[i], state))
        return _clamp_count([best], select)

    if stype == SELECT_YES_NO:
        # 先攻を取る。退化はしない
        want_yes = ctx != CTX_MORE_DEVOLVE
        return _choose_yes_no(select, want_yes)

    if stype == SELECT_ATTACK:
        scored = sorted(
            range(len(options)),
            key=lambda i: -_attack_bonus(options[i].get("attackId"), state),
        )
        return _clamp_count(scored[: max(select["minCount"], 1)], select)

    if stype == SELECT_COUNT:
        best = max(range(len(options)), key=lambda i: options[i].get("number") or 0)
        return _clamp_count([best], select)

    if stype == SELECT_CARD:
        if ctx == CTX_SETUP_BENCH:
            take = min(2, select["maxCount"])
            return _clamp_count(list(range(take)), select)
        if ctx == CTX_TO_ACTIVE:
            you = state["yourIndex"]
            opp_index = 1 - you
            opponent_owned = any(o.get("playerIndex") == opp_index for o in options)
            if opponent_owned:
                # Boss's Orders等: 相手ベンチから引きずり出す標的の選択。
                # 確殺できるならサイドが多い順、できなければ低HP順(欲張らない)
                RAPID_FIRE_BASE = 200

                def target_score(i):
                    opt = options[i]
                    idx = opt.get("index")
                    opp = state["players"][opp_index]
                    if opt.get("area") == AREA_BENCH and idx is not None and 0 <= idx < len(opp["bench"]):
                        p = opp["bench"][idx]
                        if p["hp"] <= RAPID_FIRE_BASE:
                            return 2000 * PRIZE_VALUE.get(p["id"], 1) - p["hp"] * 0.1
                        return -p["hp"] * 0.1
                    return 0
                best = max(range(len(options)), key=target_score)
                return _clamp_count([best], select)

            # 自分の昇格: 通常はエネルギーが乗ったKangaskhan優先。
            # 相手のアクティブがex(=我々のCrustleが被ダメ0で受けられる)なら壁を前に出す
            opp_act = _opp_active(state)
            opp_is_ex = bool(opp_act and PRIZE_VALUE.get(opp_act["id"], 1) >= 2)

            def promote_score(i):
                opt = options[i]
                me2 = state["players"][you]
                if opt.get("area") == AREA_BENCH and opt.get("index") is not None:
                    if 0 <= opt["index"] < len(me2["bench"]):
                        p = me2["bench"][opt["index"]]
                        if p["id"] == KANGASKHAN:
                            base = 100
                        elif p["id"] == CRUSTLE:
                            base = 135 if opp_is_ex else 80
                        else:
                            base = 0
                        return base + len(p["energies"]) * 10 + p["hp"] / 100
                return 0
            best = max(range(len(options)), key=promote_score)
            return _clamp_count([best], select)
        if ctx in (CTX_TO_HAND, CTX_TO_FIELD, CTX_TO_BENCH, CTX_ATTACH_TO):
            rank = FETCH_RANK
            me = state["players"][state["yourIndex"]]
            if not me["bench"]:
                rank = [DWEBBLE, KANGASKHAN] + [c for c in FETCH_RANK if c not in (DWEBBLE, KANGASKHAN)]
            elif _opp_wall_active(state):
                # 壁モード: 壁を割れるCrustle陣とBossを最優先で確保
                priority = [CRUSTLE, DWEBBLE, BOSS_ORDERS, ENERGY_GRASS]
                rank = priority + [c for c in FETCH_RANK if c not in priority]
            return _select_cards_by_rank(select, state, rank, take_max=True)
        if ctx == CTX_DISCARD:
            return _select_cards_by_rank(select, state, DISCARD_RANK, take_max=False)
        return _clamp_count(list(range(max(select["minCount"], 1))), select)

    # エネルギー支払い・その他: 先頭から必要数(全エネ無色相当なのでどれでも近い)
    need = select["minCount"] if select["minCount"] > 0 else min(1, select["maxCount"])
    return _clamp_count(list(range(need)), select)


# ---- 探索(2プライ先読み) ----

SEARCH_SAMPLES = 3
SEARCH_HORIZON = 1   # 対戦中は浅く確実に(h3×3サンプルは分散過多で悪化を実測)
SEARCH_MAX_DEPTH = 80
MIN_OVERAGE_FOR_SEARCH = 60

try:
    import engine_search
    import predict as _predict_mod
    _SEARCH_READY = engine_search.available()
except Exception:
    _SEARCH_READY = False

# カードID → 倒されたとき相手が取るサイド枚数(Mega ex=3, ex=2, 通常=1)。
# エンジンから取得できない環境(Kaggleでlib無し等)では空のまま=全て1扱い。
PRIZE_VALUE = {}
if _SEARCH_READY:
    try:
        for _c in engine_search.all_cards():
            PRIZE_VALUE[_c["cardId"]] = 3 if _c.get("megaEx") else (2 if _c.get("ex") else 1)
    except Exception:
        PRIZE_VALUE = {}

import random as _random

_search_rng = _random.Random(20260804)


def _evaluate(state: dict, me: int) -> float:
    """探索末端の盤面評価(自分視点で大きいほど良い)。"""
    if state["result"] == me:
        return 1e9
    if state["result"] == 1 - me:
        return -1e9
    mep, opp = state["players"][me], state["players"][1 - me]
    my_taken = 6 - len(mep["prize"] or [])
    opp_taken = 6 - len(opp["prize"] or [])
    score = (my_taken - opp_taken) * 10000.0

    def active_of(p):
        act = p.get("active") or []
        return act[0] if act and act[0] else None

    my_act, opp_act = active_of(mep), active_of(opp)
    opp_is_ex = bool(opp_act and PRIZE_VALUE.get(opp_act["id"], 1) >= 2)
    if opp_act:
        score += (opp_act["maxHp"] - opp_act["hp"]) * 3
    if my_act:
        score -= (my_act["maxHp"] - my_act["hp"]) * 2
        if my_act["id"] == KANGASKHAN:
            score += 350  # Run Errandのドローエンジン込みの場の価値
            if opp_act and opp_act["id"] == CRUSTLE:
                score -= 500  # 壁の前でMega exが立ち往生している状態はマイナス
        elif my_act["id"] == CRUSTLE:
            # 相手がexなら被ダメ0の壁として機能している
            score += 400 if opp_is_ex else 150
        score += 60 * min(len(my_act["energies"]), 3)

    score += 200 * min(len(mep["bench"]), 2) - 150 * min(len(opp["bench"]), 2)
    score += 15 * mep["handCount"]
    if mep["deckCount"] <= 3:
        score -= 400  # 山札切れ圏
    return score



def _rollout(node: dict, me: int, root_turn: int, horizon: int = 1) -> float:
    """自ターンの残り+相手のターンを進め、自分の次ターン開始時点で評価する。"""
    for _ in range(SEARCH_MAX_DEPTH):
        sob = node["observation"]
        state = sob.get("current")
        if state is None:
            break
        if state["result"] >= 0 or sob.get("select") is None:
            break
        if state["turn"] > root_turn + horizon:
            break
        node = engine_search.search_step(node["searchId"], rules_decide(sob))
    final_state = node["observation"].get("current")
    return _evaluate(final_state, me) if final_state else 0.0


def search_score_matrix(obs: dict, samples: int, horizon: int = 1) -> list:
    """MAIN選択の全選択肢のサンプル×選択肢の生スコア行列を返す。"""
    select = obs["select"]
    me = obs["current"]["yourIndex"]
    root_turn = obs["current"]["turn"]
    deck = _read_deck()
    opp_deck = _predict_mod.guess_opponent_deck(obs, deck) if hasattr(_predict_mod, "guess_opponent_deck") else deck
    matrix = []
    try:
        for _ in range(samples):
            pred = _predict_mod.predict(obs, deck, opp_deck, _search_rng)
            root = engine_search.search_begin(obs, **pred)
            row = []
            for i in range(len(select["option"])):
                child = engine_search.search_step(root["searchId"], [i])
                row.append(_rollout(child, me, root_turn, horizon))
            matrix.append(row)
    finally:
        engine_search.search_end()
    return matrix


def search_scores(obs: dict, samples: int = None) -> list:
    n = samples or SEARCH_SAMPLES
    matrix = search_score_matrix(obs, n, horizon=SEARCH_HORIZON)
    return [sum(row[i] for row in matrix) / n for i in range(len(matrix[0]))]


RETREAT_OVERRIDE_MARGIN = 8000.0  # サイド0.8枚分の大差がなければ探索でもRETREATしない


def _search_decide_main(obs: dict) -> list:
    """探索で決める。ただしRETREAT(にげる)だけは大差がない限り採用しない。

    実戦敗着分析より: 探索ノイズによるRETREAT暴発(エネルギーを捨てて自滅)が
    実負けの系統パターンだった。一方、一般の正則化は逆効果と計測済みのため
    (探索の覆しは平均的には有益)、RETREATに限定してゲートを設ける。"""
    select = obs["select"]
    totals = search_scores(obs)
    order = sorted(range(len(totals)), key=lambda i: -totals[i])
    best = order[0]
    if select["option"][best]["type"] == OPT_RETREAT and len(order) > 1:
        second = order[1]
        if totals[best] - totals[second] < RETREAT_OVERRIDE_MARGIN:
            best = second
    return _clamp_count([best], select)


_search_failures = 0

try:
    import lessons as _lessons_mod
    _lessons = _lessons_mod.load(_agent_dir())
except Exception:
    _lessons_mod = None
    _lessons = []


def reload_lessons() -> int:
    global _lessons
    if _lessons_mod is not None:
        _lessons = _lessons_mod.load(_agent_dir())
    return len(_lessons)


def agent(obs: dict) -> list:
    select = obs.get("select")
    if select is None:
        return _read_deck()
    chosen = None
    if (
        _SEARCH_READY
        and select["type"] == SELECT_MAIN
        and obs.get("search_begin_input")
        and obs.get("current") is not None
        and obs.get("remainingOverageTime", 9999) > MIN_OVERAGE_FOR_SEARCH
    ):
        try:
            chosen = _search_decide_main(obs)
        except Exception as exc:
            global _search_failures
            _search_failures += 1
            if _search_failures <= 3:
                import sys
                print(f"search fallback: {type(exc).__name__}: {exc}", file=sys.stderr)
    if chosen is None:
        chosen = rules_decide(obs)
    if _lessons_mod is not None and _lessons and select["type"] == SELECT_MAIN and obs.get("current"):
        chosen = _lessons_mod.apply(obs, chosen, _lessons)
    return chosen
