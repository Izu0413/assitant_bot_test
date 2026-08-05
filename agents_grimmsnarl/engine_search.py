"""cabtエンジンの探索API(SearchBegin/SearchStep/SearchEnd)のctypesラッパー。

【再構築版 2026-08-05】オリジナルは失われたため、libcg.so のエクスポート関数を
逆アセンブル+実挙動プローブで特定して書き直したもの。確認済みの事実:
  - SearchBegin(ctx, input, len, my_deck*, my_prize*, opp_deck*, opp_prize*,
                opp_hand*, opp_active*, manual_coin) -> char* JSON
    {"state": {"observation": {...}, "searchId": N}, "error": 0}
    各配列の要素数はstate側の枚数(deckCount等)と一致している必要がある。
  - SearchStep(ctx, searchId, select*, count) -> 同形式。フォーク方式で
    呼ぶたび新しいsearchIdが返り、rootは何度でも再分岐できる。
  - SearchEnd(ctx) で全searchIdを解放。SearchRelease(ctx, id)は個別解放。
  - GameInitialize() は1インスタンスにつき1回だけ。二重呼び出しは
    C++例外(buffer full)でプロセスごと落ちる。
    → 自ディレクトリの libcg を自前ロードできた場合のみ初期化し、
      フォールバックで kaggle_environments 同梱のものを使う場合は
      cg.sim が初期化済みのlibオブジェクトを再利用する(再初期化しない)。
"""
import ctypes
import json
import os

_lib = None
_ctx = None
_IntArr = ctypes.POINTER(ctypes.c_int)


def _here() -> str:
    try:
        return os.path.dirname(os.path.abspath(__file__))
    except NameError:  # Kaggleはexec実行で__file__が無い
        return "/kaggle_simulations/agent"


def _load() -> bool:
    global _lib, _ctx
    if _lib is not None:
        return True
    lib = None
    for name in ("libcg.so", "libcg.dylib"):
        path = os.path.join(_here(), name)
        if os.path.exists(path):
            try:
                lib = ctypes.cdll.LoadLibrary(path)
                lib.GameInitialize()
                break
            except OSError:
                lib = None
    if lib is None:
        try:
            # cg.sim はimport時にGameInitialize済み。同一インスタンスを共有し
            # 再初期化はしない(二重初期化はプロセスごとabortする)。
            from kaggle_environments.envs.cabt.cg.sim import lib as _shared
            lib = _shared
        except Exception:
            return False
    lib.AgentStart.restype = ctypes.c_void_p
    lib.AllCard.restype = ctypes.c_char_p
    lib.AllAttack.restype = ctypes.c_char_p
    lib.SearchBegin.restype = ctypes.c_char_p
    lib.SearchBegin.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int,
                                _IntArr, _IntArr, _IntArr, _IntArr, _IntArr, _IntArr,
                                ctypes.c_int]
    lib.SearchStep.restype = ctypes.c_char_p
    lib.SearchStep.argtypes = [ctypes.c_void_p, ctypes.c_int, _IntArr, ctypes.c_int]
    lib.SearchEnd.argtypes = [ctypes.c_void_p]
    lib.SearchRelease.argtypes = [ctypes.c_void_p, ctypes.c_int]
    _lib = lib
    _ctx = lib.AgentStart()
    return True


def available() -> bool:
    try:
        return _load()
    except Exception:
        return False


def all_cards() -> list:
    _load()
    return json.loads(_lib.AllCard().decode())


def all_attacks() -> list:
    _load()
    return json.loads(_lib.AllAttack().decode())


def _arr(ids):
    ids = list(ids or [])
    return (ctypes.c_int * max(len(ids), 1))(*ids)


def _parse(raw: bytes) -> dict:
    res = json.loads(raw.decode())
    if res.get("error") or not res.get("state"):
        raise RuntimeError(f"search error {res.get('error')}")
    return res["state"]


def search_begin(obs: dict, your_deck, your_prize, opponent_deck, opponent_prize,
                 opponent_hand, opponent_active=None, manual_coin: int = 0) -> dict:
    """探索を開始し {"searchId": int, "observation": {...}} を返す。"""
    _load()
    inp = obs["search_begin_input"].encode("ascii")
    raw = _lib.SearchBegin(
        _ctx, inp, len(inp),
        _arr(your_deck), _arr(your_prize),
        _arr(opponent_deck), _arr(opponent_prize), _arr(opponent_hand),
        _arr(opponent_active), int(manual_coin))
    return _parse(raw)


def search_step(search_id: int, select_list: list) -> dict:
    """searchIdの状態からselect_listを選んだ次状態を返す(元の状態は保持される)。"""
    sel = [int(x) for x in select_list]
    raw = _lib.SearchStep(_ctx, int(search_id), _arr(sel), len(sel))
    return _parse(raw)


def search_end() -> None:
    """このプロセスの全探索状態を解放する。"""
    if _lib is not None and _ctx is not None:
        _lib.SearchEnd(_ctx)
