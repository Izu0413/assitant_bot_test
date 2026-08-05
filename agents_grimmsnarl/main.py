"""タスクA-2用: Marnie's Grimmsnarl ex デッキの汎用優先度ボット(探索なし)。

meta_decks.py が失われたため、カードDB(engine_search.all_cards)から
Grimmsnarlライン(646 Impidimp / 647 Morgrem / 648 Grimmsnarl ex)を再構成した
リストを使う。ロジックは汎用優先度のみ: 進化 > 特性 > エネ装着 > 展開 >
ドローサポート > リーサル攻撃 > 通常攻撃。v1/v2.1 の共通対戦相手として使い、
両者の勝率差(サイドレート評価の効果が出る非ミラー環境)を測る。
"""
import os

SELECT_MAIN, SELECT_CARD, SELECT_ATTACHED_CARD, SELECT_CARD_OR_ATTACHED, SELECT_ENERGY = 0, 1, 2, 3, 4
SELECT_SKILL, SELECT_ATTACK, SELECT_EVOLVE, SELECT_COUNT, SELECT_YES_NO, SELECT_SPECIAL = 5, 6, 7, 8, 9, 10
OPT_NUMBER, OPT_YES, OPT_NO, OPT_CARD, OPT_TOOL_CARD, OPT_ENERGY_CARD, OPT_ENERGY = 0, 1, 2, 3, 4, 5, 6
OPT_PLAY, OPT_ATTACH, OPT_EVOLVE, OPT_ABILITY, OPT_DISCARD, OPT_RETREAT, OPT_ATTACK, OPT_END = 7, 8, 9, 10, 11, 12, 13, 14
AREA_DECK, AREA_HAND, AREA_DISCARD, AREA_ACTIVE, AREA_BENCH = 1, 2, 3, 4, 5
CTX_SETUP_BENCH, CTX_TO_ACTIVE, CTX_TO_HAND, CTX_TO_FIELD, CTX_TO_BENCH = 2, 4, 7, 6, 5
CTX_DISCARD, CTX_ATTACH_TO, CTX_MORE_DEVOLVE = 8, 22, 45

IMPIDIMP, MORGREM, GRIMMSNARL = 646, 647, 648
DARK = 7
LILLIE, POFFIN, ULTRA_BALL, POKEGEAR, BOSS, SWITCH, CAPE = 1227, 1086, 1121, 1122, 1182, 1123, 1159
HILDA, ERI, XEROSIC, BIANCA, LISIA, COMMUNITY = 1225, 1186, 1197, 1190, 1204, 1242

DECK = ([IMPIDIMP] * 4 + [MORGREM] * 3 + [GRIMMSNARL] * 3 +
        [LILLIE] * 4 + [POFFIN] * 4 + [ULTRA_BALL] * 4 + [POKEGEAR] * 4 +
        [BOSS] * 3 + [SWITCH] * 2 + [CAPE] * 1 + [HILDA] * 2 +  # CapeはACE SPEC=1枚制限
        [ERI] * 2 + [XEROSIC] * 2 + [BIANCA] * 2 + [LISIA] * 2 + [COMMUNITY] * 2 +
        [DARK] * 16)
assert len(DECK) == 60, len(DECK)

FETCH_RANK = [GRIMMSNARL, MORGREM, IMPIDIMP, DARK, BOSS, LILLIE, ULTRA_BALL, POFFIN]
DISCARD_RANK = [POKEGEAR, SWITCH, LISIA, BIANCA, XEROSIC, ERI, COMMUNITY, HILDA, CAPE,
                DARK, POFFIN, ULTRA_BALL, BOSS, LILLIE, IMPIDIMP, MORGREM, GRIMMSNARL]


def _clamp(indices, select):
    seen, out = set(), []
    for i in indices:
        if i not in seen:
            seen.add(i)
            out.append(i)
    lo, hi = select["minCount"], select["maxCount"]
    out = out[:hi]
    pad = 0
    while len(out) < lo and pad < len(select["option"]):
        if pad not in seen:
            out.append(pad)
            seen.add(pad)
        pad += 1
    return out


def _me(state):
    return state["players"][state["yourIndex"]]


def _hand(state):
    return _me(state)["hand"] or []


def _card_of(opt, state, select):
    area, idx = opt.get("area"), opt.get("index")
    me = _me(state)
    if area == AREA_DECK and select.get("deck") is not None and idx is not None:
        if 0 <= idx < len(select["deck"]):
            return select["deck"][idx]["id"]
    if area == AREA_HAND and idx is not None and 0 <= idx < len(_hand(state)):
        return _hand(state)[idx]["id"]
    if area == AREA_BENCH and idx is not None and 0 <= idx < len(me["bench"]):
        return me["bench"][idx]["id"]
    if area == AREA_ACTIVE and me["active"] and me["active"][0]:
        return me["active"][0]["id"]
    return opt.get("cardId")


def _rank(cid, rank):
    try:
        return rank.index(cid)
    except ValueError:
        return len(rank)


def _score_main(opt, state):
    t = opt["type"]
    me = _me(state)
    active = me["active"][0] if me["active"] else None
    a_energy = len(active["energies"]) if active else 0
    if t == OPT_EVOLVE:
        return 90  # Grimmsnarl進化はPunk Upで5エネ加速
    if t == OPT_ABILITY:
        return 85
    if t == OPT_ATTACH:
        to_active = opt.get("inPlayArea") == AREA_ACTIVE
        if to_active:
            return 80 if a_energy < 2 else 45
        return 60
    if t == OPT_PLAY:
        hand = _hand(state)
        idx = opt.get("index")
        cid = hand[idx]["id"] if (idx is not None and 0 <= idx < len(hand)) else None
        bench = len(me["bench"])
        if cid == IMPIDIMP:
            return 70 if bench < 3 else 20
        if cid == POFFIN:
            return 55 if bench < 3 else 5
        if cid == LILLIE:
            return 62 if me["handCount"] <= 4 else 15
        if cid == ULTRA_BALL:
            return 50 if me["handCount"] >= 3 else 5
        if cid == POKEGEAR:
            return 48
        if cid == BOSS:
            return 42
        if cid == CAPE:
            return 40
        if cid in (HILDA, ERI, XEROSIC, BIANCA, LISIA):
            return 35
        if cid == COMMUNITY:
            return 38 if not state["stadium"] else 0
        if cid == SWITCH:
            return 3
        return 10
    if t == OPT_ATTACK:
        return 30 + _atk_bonus(opt.get("attackId"), state)
    if t == OPT_RETREAT:
        return 1
    if t == OPT_END:
        return 0
    return 2


ATTACK_DB = {}
CARD_DB = {}
try:
    import engine_search as _es
    for _c in _es.all_cards():
        CARD_DB[_c["cardId"]] = _c
    for _a in _es.all_attacks():
        ATTACK_DB[_a["attackId"]] = _a
except Exception:
    pass


def _atk_bonus(attack_id, state):
    a = ATTACK_DB.get(attack_id)
    if not a:
        return 1
    dmg = a.get("damage") or 0
    opp = state["players"][1 - state["yourIndex"]]
    opp_act = (opp.get("active") or [None])[0]
    if opp_act and dmg >= opp_act["hp"]:
        return 41 + dmg / 100.0  # リーサル(71相当)
    return 1 + min(dmg, 300) / 100.0


def agent(obs):
    select = obs.get("select")
    if select is None:
        return list(DECK)
    state = obs.get("current")
    stype = select["type"]
    ctx = select["context"]
    options = select["option"]

    if stype == SELECT_MAIN:
        best = max(range(len(options)), key=lambda i: _score_main(options[i], state))
        return _clamp([best], select)
    if stype == SELECT_YES_NO:
        want_yes = ctx != CTX_MORE_DEVOLVE
        for i, o in enumerate(options):
            if (o["type"] == OPT_YES) == want_yes:
                return [i]
        return [0]
    if stype == SELECT_ATTACK:
        order = sorted(range(len(options)),
                       key=lambda i: -_atk_bonus(options[i].get("attackId"), state))
        return _clamp(order[:max(select["minCount"], 1)], select)
    if stype == SELECT_COUNT:
        best = max(range(len(options)), key=lambda i: options[i].get("number") or 0)
        return _clamp([best], select)
    if stype == SELECT_CARD:
        if ctx == CTX_SETUP_BENCH:
            return _clamp(list(range(min(2, select["maxCount"]))), select)
        if ctx == CTX_TO_ACTIVE:
            def promote(i):
                opt = options[i]
                me = _me(state)
                if opt.get("area") == AREA_BENCH and opt.get("index") is not None \
                        and 0 <= opt["index"] < len(me["bench"]):
                    p = me["bench"][opt["index"]]
                    return len(p["energies"]) * 10 + p["hp"] / 100
                return 0
            return _clamp([max(range(len(options)), key=promote)], select)
        if ctx in (CTX_TO_HAND, CTX_TO_FIELD, CTX_TO_BENCH, CTX_ATTACH_TO):
            scored = sorted(range(len(options)),
                            key=lambda i: _rank(_card_of(options[i], state, select), FETCH_RANK))
            return _clamp(scored[:select["maxCount"]], select)
        if ctx == CTX_DISCARD:
            scored = sorted(range(len(options)),
                            key=lambda i: _rank(_card_of(options[i], state, select), DISCARD_RANK))
            return _clamp(scored[:max(select["minCount"], 0)], select)
        return _clamp(list(range(max(select["minCount"], 1))), select)
    need = select["minCount"] if select["minCount"] > 0 else min(1, select["maxCount"])
    return _clamp(list(range(need)), select)
