"""評価関数v2 + ワザ選択修正パッチ(agents_final/main.py 組み込み用)。

修正対象の2つの盲点:
  A. 評価が「王手」を見ない — 次ターン確定KOの盤面が蓄積ダメージ×3点でしか
     評価されず、サイドレート(非ex=1/ex=2/Mega=3)も無視されている。
  B. ロールアウト内の相手が最弱手を打つ — OPT_ATTACKが全ワザ同点30のため
     max()が先頭ワザを選び、シミュレーション内の相手が本気を出さない。

組み込み手順:
  1. このファイルの <BLOCK1> を main.py の PRIZE_VALUE 構築の直後に貼る
  2. `_evaluate = evaluate_v2` の1行を追加(旧_evaluateは残してよい)
  3. _main_option_score の OPT_ATTACK 分岐を
       return _attack_score_v2(opt.get("attackId"), state)
     に、rules_decide の SELECT_ATTACK のソートキーを
       key=lambda i: -_attack_score_v2(options[i].get("attackId"), state)
     に置き換える(旧_attack_bonusは削除可)

近似の限界(ドキュメント化): コイン・追加効果・Spiky Energyの反撃・弱点以外の
補正は打点計算に含めていない。基礎ダメージ+弱点×2+壁無効化のみ。
"""

import json as _json

# ================= <BLOCK1> ここから main.py へ =================

_WALL_ID = 345        # Crustle: 特性で相手のポケモンexからのダメージを0にする
_KANGASKHAN_ID = 756

CARD_DB = {}    # cardId -> カード情報(hp, weakness, pokemonType, attacks, ex, megaEx)
ATTACK_DB = {}  # attackId -> {"damage": 基礎打点, "cost": 必要エネ数}


def _load_battle_dbs():
    """カード/ワザDBをロードする。engine_search → エンジン直読み → 空、の順で退避。"""
    cards = attacks = None
    try:
        import engine_search as _es
        cards = _es.all_cards()
        if hasattr(_es, "all_attacks"):
            attacks = _es.all_attacks()
    except Exception:
        pass
    if cards is None or attacks is None:
        try:
            import ctypes as _ct
            from kaggle_environments.envs.cabt.cg.sim import lib as _lib
            _lib.AllCard.restype = _ct.c_char_p
            _lib.AllAttack.restype = _ct.c_char_p
            cards = cards or _json.loads(_lib.AllCard().decode())
            attacks = attacks or _json.loads(_lib.AllAttack().decode())
        except Exception:
            cards, attacks = cards or [], attacks or []
    for c in cards:
        CARD_DB[c["cardId"]] = c
    for a in attacks:
        ATTACK_DB[a["attackId"]] = {"damage": a.get("damage") or 0,
                                    "cost": len(a.get("energies") or [])}


_load_battle_dbs()


def _prize_yield(card_id) -> int:
    """このポケモンが倒されたとき相手が取るサイド枚数。"""
    c = CARD_DB.get(card_id) or {}
    return 3 if c.get("megaEx") else (2 if c.get("ex") else 1)


def _is_ex_family(card_id) -> bool:
    c = CARD_DB.get(card_id) or {}
    return bool(c.get("ex") or c.get("megaEx"))


def _best_attack_damage(attacker: dict, defender: dict) -> int:
    """attackerが今のエネ数で出せる最大打点の概算(基礎値+弱点×2、壁は0)。"""
    if not attacker:
        return 0
    if defender and defender.get("id") == _WALL_ID and _is_ex_family(attacker["id"]):
        return 0  # Mysterious Rock Inn: ex/Megaからのダメージを受けない
    card = CARD_DB.get(attacker["id"]) or {}
    energy = len(attacker.get("energies") or [])
    best = 0
    for aid in card.get("attacks") or []:
        atk = ATTACK_DB.get(aid)
        if atk and energy >= atk["cost"]:
            best = max(best, atk["damage"])
    if best and defender:
        dcard = CARD_DB.get(defender["id"]) or {}
        if dcard.get("weakness") is not None and dcard["weakness"] == card.get("pokemonType"):
            best *= 2
    return best


# 重みの単位は従来どおり「サイド1枚 = 10000」
_W_PRIZE = 10000.0
_W_THREAT_ME = 0.7    # 自分→相手の王手。評価地点は自ターン開始なので1手先の確定圧
_W_THREAT_OPP = 0.45  # 相手→自分の王手は2手先(自分の手番を挟む)ため軽く見る
_W_PROGRESS = 0.30  # 蓄積ダメージのKO進捗価値(進捗率×サイド枚数に比例)


def evaluate_v2(state: dict, me: int) -> float:
    """探索末端の盤面評価v2(自分視点で大きいほど良い)。

    v1からの変更: 蓄積ダメージの固定レート(+3/-2)を廃し、
    「KO進捗率×そのポケモンのサイド価値」+「王手ボーナス」に置き換え。
    王手は非対称(自分の王手は1手先、相手の王手は2手先で、しかもこちらが
    先に相手アタッカーを除去できるなら半減する)。
    既存のデッキ固有タイブレーク項は維持。
    """
    if state["result"] == me:
        return 1e9
    if state["result"] == 1 - me:
        return -1e9
    mep, opp = state["players"][me], state["players"][1 - me]
    my_taken = 6 - len(mep["prize"] or [])
    opp_taken = 6 - len(opp["prize"] or [])
    score = (my_taken - opp_taken) * _W_PRIZE

    def _active_of(p):
        act = p.get("active") or []
        return act[0] if act and act[0] else None

    my_act, opp_act = _active_of(mep), _active_of(opp)

    def _pressure(attacker, defender, sign, threat_weight):
        """defenderに掛かっている圧力(進捗+王手)をsign方向で加点する。"""
        if not defender:
            return 0.0
        value = _W_PRIZE * _prize_yield(defender["id"])
        damage = defender["maxHp"] - defender["hp"]
        s = sign * value * _W_PROGRESS * min(1.0, damage / max(defender["maxHp"], 1))
        if _best_attack_damage(attacker, defender) >= defender["hp"]:
            s += sign * value * threat_weight
        return s

    my_lethal = bool(opp_act and _best_attack_damage(my_act, opp_act) >= opp_act["hp"])
    opp_threat_weight = _W_THREAT_OPP * (0.5 if my_lethal else 1.0)
    score += _pressure(my_act, opp_act, +1, _W_THREAT_ME)
    score += _pressure(opp_act, my_act, -1, opp_threat_weight)

    # ベンチ0で被王手 = 次ターンほぼ敗北
    if my_act and not mep["bench"] and _best_attack_damage(opp_act, my_act) >= my_act["hp"]:
        score -= _W_PRIZE * 3

    # ---- 以下は旧v1のタイブレーク項(据え置き) ----
    opp_is_ex = bool(opp_act and _prize_yield(opp_act["id"]) >= 2)
    if my_act:
        if my_act["id"] == _KANGASKHAN_ID:
            score += 350
            if opp_act and opp_act["id"] == _WALL_ID:
                score -= 500
        elif my_act["id"] == _WALL_ID:
            score += 400 if opp_is_ex else 150
        score += 60 * min(len(my_act["energies"]), 3)
    score += 200 * min(len(mep["bench"]), 2) - 150 * min(len(opp["bench"]), 2)
    score += 15 * mep["handCount"]
    if mep["deckCount"] <= 3:
        score -= 400
    return score


def _attack_score_v2(attack_id, state: dict) -> float:
    """ワザ選択の採点。打点ベース+リーサルボーナス。

    上限70に抑えてある: ワザ選択=ターン終了なので、セットアップ行動
    (特性85/進化90/エネ装着80等)より常に下でなければならない。
    """
    me = state["yourIndex"]
    mep, opp = state["players"][me], state["players"][1 - me]
    my_act = (mep.get("active") or [None])[0]
    opp_act = (opp.get("active") or [None])[0]

    # 壁の前でex/Megaが空振りする状況は攻撃自体をやめる(END=0より下げる)
    if my_act and opp_act and opp_act.get("id") == _WALL_ID and _is_ex_family(my_act["id"]):
        return -5.0

    atk = ATTACK_DB.get(attack_id)
    damage = (atk["damage"] if atk else 0)
    if damage and opp_act:
        dcard = CARD_DB.get(opp_act["id"]) or {}
        acard = CARD_DB.get(my_act["id"]) or {} if my_act else {}
        if dcard.get("weakness") is not None and dcard["weakness"] == acard.get("pokemonType"):
            damage *= 2
    lethal = bool(opp_act and damage >= opp_act["hp"])
    # 非リーサル帯 31〜34: v1の帯(31〜33)と同じ高さに揃える。v2.0では45〜60に
    # なっており、Boss(44)やポケギア(50)等のカードプレイを追い越して
    # ターンを早終了させていた(182戦A/Bで44.5%と負け越した主因)。
    # リーサル時のみ 71〜74 に跳ねる(それでもエネ装着80/特性85より下 =
    # Run Errandのドローとエネ装着を済ませてから確殺する)
    if lethal:
        return 71.0 + min(damage, 300) / 100.0
    return 31.0 + min(damage, 300) / 100.0

# ================= </BLOCK1> ここまで =================
