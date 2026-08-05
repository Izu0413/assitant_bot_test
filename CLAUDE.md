# CLAUDE.md — ポケカABC エージェント開発

## プロジェクト概要

Kaggle「The Pokémon Company - PTCG AI Battle Challenge」への参加。
- シミュレーション部門: エージェント提出締切 **2026-08-17 08:59 JST**
- ストラテジー部門: レポート提出締切 **2026-09-14 08:59 JST**(賞金対象、上位8チーム)
- 戦略方針: エージェントは堅実に強く、**勝負はレポートの質**(仮説→実装→計測→反証の記録)。
  experiments.csv がそのままレポートの根拠になるため、実験記録は絶対に欠かさない。

## リポジトリ構成

- `agents_final/` — 現行チャンピオン(v1)。main.py + engine_search.py + predict.py +
  lessons.py + meta_decks.py + deck.csv + libcg.dylib(macOS用)
- `agents_final_v2/main.py` — 挑戦者(評価v2.1統合済み)。**採用判定待ち**(下記タスクA)
- `arena.py` — 自己対戦評価基盤(Wilson CI、先攻後攻入替、experiments.csvへ自動記録)
- `kaggle_scrape.py` / `meta_analyze.py` — LB上位チームのリプレイ収集と
  デッキ完全復元(リプレイにはデッキ提出が行動として記録されている)
- `eval_v2_patch.py` — 評価v2.1のパッチ原本(BLOCK1をmain.pyに注入する方式)
- `experiments.csv` — 全実験の記録。**1行=1実験、note列に「何を変えたか」必須**

## 環境

- `pip install kaggle-environments pandas` のみ。**Docker不要**。
  対戦エンジン(cabt)は kaggle_environments に同梱
  (`kaggle_environments/envs/cabt/cg/libcg.{so,dylib}`)。
- engine_search.py は**自分と同じディレクトリ**の libcg.dylib(mac)/libcg.so(Linux)を読む。
- ローカル実行時は sys.path にエージェントディレクトリを入れること
  (kaggle-environmentsのファイルエージェントは exec 実行で __file__ が無い)。

## 検証済みの事実(再検証不要。これに反する「修正」をしないこと)

1. **search_step はフォーク方式**。呼ぶたびに新しい searchId が返り、rootは
   何度でも再分岐できる。search_score_matrix の候補ループは正しい。
2. **predict の自分側会計は完全一致**(40局面で不一致0)。水エネパディングは
   相手側のアーキタイプ不一致吸収のためだけに存在する。壊すな。
3. **探索コストは1判断 9〜41ms**(サンプル3×h1)。1試合の探索合計≈1秒。
   持ち時間は600秒/試合 → **量を10〜30倍にする余地がある**(タスク1)。
4. **先攻後攻の選択(context 41)は YES=先攻**(実測14/14, 6/6)。先攻有利は
   優先度ボット同士で約17pt。常にYESを維持。
5. **不正手=即敗北**。optionの範囲外インデックス1つでその試合はINVALID負け。
   デッキは必ず60枚。_clamp_count がこの保証を担う。触るときは慎重に。
6. **ワザ選択=ターン終了**。行動採点の帯域設計が生命線:
   非リーサル攻撃 31〜34 < カードプレイ帯 40〜78 < エネ装着 80 < 特性 85 < 進化 90、
   リーサル攻撃のみ 71〜74。v2.0はこの帯域を壊して(非リーサル45〜60)
   **182戦44.5%[37.5,51.8]で負け越した**。帯域を跨ぐ変更は必ずA/Bで検証。
7. **評価v2.1の現状**: ミラー175戦で53.1%[45.8,60.4]。回帰は解消したが
   v1超えは未証明。かつ**ミラーはv2の強み(サイドレート重み)が対称で
   打ち消される最悪の測定環境**。非ミラーでの検証が必要(タスクA)。
8. Kaggleのレートは600付近スタートのElo風・同レート帯マッチング。
   **LBを実験装置に使わない**(1日5提出、最終順位は直近2提出のみ、収束に半日以上)。
9. カード/ワザの静的データはエンジンから直接取れる:
   `engine_search.all_cards()` / `all_attacks()`(attackId→damage/energies)。
   CSVとの突き合わせは不要。

## 実験プロトコル(必須)

- 変更1つにつき: `python arena.py <挑戦者> <現行チャンピオン> -n 400 --note "変更内容"`
- 判定: 勝率の95%CIが50%から離れたら昇格。CIが跨ぐなら「差なし」と記録して次へ。
- 先攻後攻は arena.py が自動で半々にする。手動で対戦を組むときも必ず入れ替える。
- 400戦未満の数字で意思決定しない(175戦でCI幅±7ptある)。
- 結果は必ず experiments.csv に残す(negative resultも。レポートの材料)。

## Kaggle提出(tar.gz)チェックリスト

- [ ] main.py(**ファイル内で最後に定義されたcallableがエージェントになる**。
      agent() を最後に置く)
- [ ] deck.csv / engine_search.py / predict.py / lessons.py / meta_decks.py
      (+ lessons.json があれば)
- [ ] **libcg.so(Linux x86-64版)** — kaggle_environments 同梱のものを同梱する。
      dylibはmac用なので本番では読まれない。これが無いと _SEARCH_READY=False で
      **探索なしのまま静かに対戦する**(過去のLB成績がこれだった疑いは未回収)
- [ ] 提出後、エピソード画面のstderrに `search fallback` が出ていないか確認

## 開発の進め方

- スキルパック(dev-core-principles / implementation-rules / task-breakdown /
  testing-and-review)に従う。タスク宣言→実装→動作確認→エラーケース→報告。
- バックログと受け入れ条件は TASKS.md を参照。着手順もそこに明記。
- Kaggle画面での操作(提出アップロード、エピソードstderr確認、エントリー)は
  人間にしかできない。必要になったらタスクを止めて依頼すること。
