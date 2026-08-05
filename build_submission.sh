#!/usr/bin/env bash
# Kaggle提出用 tar.gz をビルドする(CLAUDE.mdチェックリスト準拠)。
# 使い方: ./build_submission.sh [エージェントdir=agents_final] [出力=submission.tar.gz]
set -euo pipefail

AGENT_DIR="${1:-agents_final}"
OUT="${2:-submission.tar.gz}"

KENV=$(python3 -c "import kaggle_environments as k,os;print(os.path.dirname(k.__file__))")
LIBCG="$KENV/envs/cabt/cg/libcg.so"
if [ ! -f "$LIBCG" ]; then
    echo "ERROR: libcg.so (Linux x86-64) が見つからない: $LIBCG" >&2
    exit 1
fi

STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

# 必須ファイル
for f in main.py deck.csv engine_search.py predict.py; do
    cp "$AGENT_DIR/$f" "$STAGE/"
done
# あれば同梱
for f in meta_decks.py lessons.py lessons.json; do
    [ -f "$AGENT_DIR/$f" ] && cp "$AGENT_DIR/$f" "$STAGE/"
done
# Linux x86-64 の libcg.so(dylibは本番では読まれない)
cp "$LIBCG" "$STAGE/"

# main.py の最後の callable が agent であることを確認
python3 - "$STAGE/main.py" <<'PYEOF'
import ast, sys
tree = ast.parse(open(sys.argv[1]).read())
last = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))][-1]
assert last == "agent", f"main.py の最後の関数定義が agent でない: {last}"
print("main.py 最終callable: agent OK")
PYEOF

tar -czf "$OUT" -C "$STAGE" .
echo "== $OUT の内容 =="
tar -tzf "$OUT" | sort
echo "== サイズ =="
ls -lh "$OUT"
