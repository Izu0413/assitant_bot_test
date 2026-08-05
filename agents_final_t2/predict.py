"""隠れ情報の決定化(determinization)。search_begin に渡す予測配列を作る。

【再構築版 2026-08-05】オリジナル消失のため書き直し。方針:
  - 自分側: 自デッキ60枚の多重集合から「見えている自分のカード」
    (手札・場・進化元・エネルギー・どうぐ・トラッシュ・スタジアム・looking)を
    引いた残りが山札+サイドのプール。rngでシャッフルしてサイド→山札に配る。
  - 相手側: 推定デッキ60枚から相手の可視カードを引いた残りを
    手札→サイド→山札に配る。プールが不足する分は水エネルギー(id 3)で
    パディングする(アーキタイプ不一致の吸収用。壊すな — CLAUDE.md 検証済み事実2)。
"""
import collections

WATER_ENERGY = 3  # 相手側パディング用


def _iter_visible(player: dict, include_hand: bool):
    """プレイヤーの可視カードid(山札・サイド以外に存在が確定しているもの)。"""
    for zone in ("active", "bench"):
        for c in (player.get(zone) or []):
            if not c:
                continue
            yield c["id"]
            for e in c.get("energyCards") or []:
                yield e["id"]
            for t in c.get("tools") or []:
                yield t["id"]
            for p in c.get("preEvolution") or []:
                yield p["id"]
    for c in player.get("discard") or []:
        yield c["id"]
    if include_hand:
        for c in player.get("hand") or []:
            yield c["id"]
    # サイドは表向きに公開された分のみ(nullは未公開)
    for c in player.get("prize") or []:
        if c:
            yield c["id"]


def _pool_after_removal(deck60: list, seen_ids) -> list:
    pool = collections.Counter(deck60)
    for cid in seen_ids:
        if pool.get(cid, 0) > 0:
            pool[cid] -= 1
    out = []
    for cid, n in pool.items():
        out.extend([cid] * n)
    return out


def _stadium_owner_ids(state: dict, player_index: int):
    for c in state.get("stadium") or []:
        if c and c.get("playerIndex") == player_index:
            yield c["id"]


def _looking_ids(state: dict, player_index: int):
    for c in state.get("looking") or []:
        if c and c.get("playerIndex") == player_index:
            yield c["id"]


def _deal(pool: list, sizes: list, rng, pad_id=None) -> list:
    """poolをシャッフルしsizes枚ずつに切り分ける。不足はpad_idで補う(相手側のみ)。"""
    pool = list(pool)
    rng.shuffle(pool)
    need = sum(sizes)
    if len(pool) < need:
        if pad_id is None:
            raise ValueError(f"pool underflow: {len(pool)} < {need}")
        pool.extend([pad_id] * (need - len(pool)))
    parts = []
    at = 0
    for n in sizes:
        parts.append(pool[at:at + n])
        at += n
    return parts


def guess_opponent_deck(obs: dict, my_deck: list) -> list:
    """相手デッキ60枚の推定。
    1. 可視ポケモンが meta_decks.ARCHETYPE_SIGNS に該当 → そのリストを使い、
       可視カードとの齟齬は水エネパディングで吸収(_dealのpad)。
    2. 該当なしで可視カードが自デッキの部分集合 → ミラーとみなす。
    3. どちらでもない → 可視カード+水エネパディングの60枚。"""
    state = obs["current"]
    opp = state["players"][1 - state["yourIndex"]]
    visible = list(_iter_visible(opp, include_hand=False))
    visible += list(_stadium_owner_ids(state, 1 - state["yourIndex"]))
    try:
        import meta_decks
        votes = collections.Counter(
            meta_decks.ARCHETYPE_SIGNS[cid] for cid in visible
            if cid in meta_decks.ARCHETYPE_SIGNS)
        if votes:
            return list(meta_decks.DECKS[votes.most_common(1)[0][0]])
    except ImportError:
        pass
    mine = collections.Counter(my_deck)
    vis = collections.Counter(visible)
    if all(mine.get(cid, 0) >= n for cid, n in vis.items()):
        return list(my_deck)
    deck = list(visible)[:60]
    deck += [WATER_ENERGY] * (60 - len(deck))
    return deck


def predict(obs: dict, deck: list, opp_deck: list, rng) -> dict:
    """search_begin(obs, **pred) に渡すキーワード引数を返す。"""
    state = obs["current"]
    you = state["yourIndex"]
    me = state["players"][you]
    opp = state["players"][1 - you]

    my_seen = list(_iter_visible(me, include_hand=True))
    my_seen += list(_stadium_owner_ids(state, you))
    my_seen += list(_looking_ids(state, you))
    my_pool = _pool_after_removal(deck, my_seen)
    n_my_prize = sum(1 for c in (me.get("prize") or []) if not c)
    my_prize, my_deck_rest = _deal(my_pool, [n_my_prize, me["deckCount"]], rng,
                                   pad_id=WATER_ENERGY)

    opp_seen = list(_iter_visible(opp, include_hand=False))
    opp_seen += list(_stadium_owner_ids(state, 1 - you))
    opp_seen += list(_looking_ids(state, 1 - you))
    opp_pool = _pool_after_removal(opp_deck, opp_seen)
    n_opp_prize = sum(1 for c in (opp.get("prize") or []) if not c)
    opp_hand, opp_prize, opp_deck_rest = _deal(
        opp_pool, [opp["handCount"], n_opp_prize, opp["deckCount"]], rng,
        pad_id=WATER_ENERGY)

    return {
        "your_deck": my_deck_rest,
        "your_prize": my_prize,
        "opponent_deck": opp_deck_rest,
        "opponent_prize": opp_prize,
        "opponent_hand": opp_hand,
        "opponent_active": [],
    }
