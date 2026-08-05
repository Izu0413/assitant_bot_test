"""提出tar.gzのスモークテスト(タスク0の完了条件)。

1. tarを一時ディレクトリへ展開
2. 展開先mainを直接ロードし _SEARCH_READY=True とデッキ60枚を確認
3. kaggle_environments.make("cabt").run([展開先main.py, "random"]) を実行し、
   INVALID/ERROR なく完走することを確認
使い方: python smoke_submission.py [submission.tar.gz]
"""
import importlib.util
import subprocess
import sys
import tempfile
import os

tarball = sys.argv[1] if len(sys.argv) > 1 else "submission.tar.gz"
tmp = tempfile.mkdtemp(prefix="subm_smoke_")
subprocess.run(["tar", "-xzf", tarball, "-C", tmp], check=True)
main_path = os.path.join(tmp, "main.py")
assert os.path.exists(main_path), "main.py がtarに無い"
assert os.path.exists(os.path.join(tmp, "libcg.so")), "libcg.so がtarに無い"

# --- 2. 直接ロード検証 ---
sys.path.insert(0, tmp)
spec = importlib.util.spec_from_file_location("subm_main", main_path)
m = importlib.util.module_from_spec(spec)
sys.modules["subm_main"] = m
spec.loader.exec_module(m)
assert m._SEARCH_READY is True, "_SEARCH_READY=False: libcg.so が読めていない"
deck = m.agent({"select": None})
assert len(deck) == 60, f"デッキが60枚でない: {len(deck)}"
print("直接ロード: _SEARCH_READY=True / デッキ60枚 OK")

# --- 3. cabt環境でrandom相手に1試合 ---
from kaggle_environments import make
env = make("cabt", debug=True)
steps = env.run([main_path, "random"])
s0, s1 = steps[-1]
print(f"最終status: agent={s0.status} random={s1.status} / "
      f"reward: agent={s0.reward} random={s1.reward}")
assert s0.status == "DONE", f"エージェントが異常終了: {s0.status}"
print("スモークOK: INVALID/ERRORなしで完走")
