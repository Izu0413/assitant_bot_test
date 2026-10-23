# Mac上のClaude Codeへの引き継ぎ(ゆびなぞり)

このファイルは、クラウドのセッションで作った要件定義を、Mac上のClaude Codeで続けるためのメモです。

## ここまでに決まったこと
- 要件定義書: `01_requirements.md`(このファイルと同じフォルダ)。ユーザーの合意済みです。
- 開発は Mac 上の Claude Code で進める(ビルド、シミュレーターでの確認、iPadへのインストールまで)。

## Macで最初にやること
1. このリポジトリの `claude/yubi-nazori-requirements` ブランチから `yubi-nazori/docs/01_requirements.md` を取得し、
   `~/Desktop/claude-code/yubi-nazori/docs/01_requirements.md` に置く。
2. `technical-design` スキルで技術設計書 `02_technical_design.md` を作る。
3. `task-breakdown` スキルで実装計画 `03_implementation_plan.md` を作る。
4. ユーザーの承認を取ってから実装に入る。

## ふうせんパーン(BalloonPop)から引き継ぐ前提
- 場所: `~/Desktop/claude-code/balloon-pop/`。構成、README、署名の手順はここを参考にする。
- 環境: MacBook Air / macOS 26.2 / Xcode 26.6。シミュレーターは「iPad (A16)」(iOS 26.5)を作成済み。
- 実機: iPad Pro 11インチ(第2世代)、iPadOS 26.4.2。
- 署名: 無料のApple ID(Personal Team `JC6U88LQ3V`)。7日ごとに入れ直す。iPadで「VPNとデバイス管理」から信頼する必要がある。
- プロジェクトの作り方: ユーザーが Xcode の File → New → Project で作る(SwiftUI、Swift Testing)。その後、iPad専用、横向きのみ、iOS 17.0以上に設定する。
- 注意: `-derivedDataPath` は Desktop の外に置く(iCloud同期のせいで CodeSign エラーになるため)。
- テストは `-parallel-testing-enabled NO` を付けて実行する。テスト名は英字にし、日本語は `@Test("…")` の表示名に書く。
- 子ども向けUXのルール: 文字を出さない、失敗の表示をしない、大人は✕を2秒長押しで抜ける、ボタンは直径80pt以上。
- 素材: 1つずつユーザーの承認を取ってからダウンロードし、出典を CREDITS.md に記録する。
- 伝え方: やさしい日本語で報告する(できたこと / 確認したこと / 未確認・残っていること / 次のステップ)。
