# CLAUDE.md

## このリポジトリの正体

**shared-infra-incident-readiness** — 共有インフラ事故初動(最初の 30 分)を救う**診断ツール + 拡張可能フレームワーク**。責任境界表・初動 RACI・DPA 条項・通知 SLA・Tabletop 演習を機械可読定義として持ち、CLI で診断・生成する。MIT の OSS。

出典は共用メール基盤事案(6 ISP の OEM 共有基盤)の**公開報道からの抽出**であり、事案当事者の内部情報には依拠しない。

- **機械可読の正本**(`definitions/` の YAML / `schemas/` の JSON Schema)
- **診断ツール**(`bin/siir` + `src/siir/`)
- **AI エージェント連携サンプル**(`examples/skills/`)

の 3 点セットとして提供する。各社は **オーバーレイ**(`examples/overlays/<company>/`)で自社固有のロール・項目・条項・通知義務・シナリオをフォークせず追加できる。

## 正本の所在(二重保持しない)

| 種類 | 正本パス | 役割 |
|---|---|---|
| 責任境界表 / RACI / シナリオ | `definitions/*.yaml` | 構造的正本 |
| 契約 SLA(24h/72h) | `definitions/dpa-clauses.yaml` | 契約上の通知 SLA の正本 |
| 法令・規制の通知期限 | `definitions/notification-obligations.yaml` | 法令クロックの正本 |
| インシデント記録契約 | `schemas/incident-record.schema.json` | JSON Schema 契約正本 |
| 説明書 | `docs/*.md` | 上記の解説。**定義の値は二重保持しない**(リンク参照) |
| 動く入口 | `bin/siir` / `src/siir/` / `examples/` | 上記を消費する CLI と入力サンプル |

**SLA を二重に書かない**: 通知 SLA の値は契約系=`dpa-clauses.yaml`、法令系=`notification-obligations.yaml` のどちらか一方だけに置く。`incident-raci.yaml` は `obligation_ref` / `clause_ref` で **ID 参照するだけ**で値を持たない。

## オーバーレイのマージ規則(一貫性の保護)

各社のオーバーレイで可能なのは以下の 2 操作のみ:

- **`add`**: 配列要素(roles / items / clauses / obligations / scenarios / activities)の追加。**既存要素の上書き・削除・RACI セルの書換えは不可**
- **`strengthen`**: 数値フィールドの **強化方向のみ**。方向は各定義の `extension_points` に `direction`(SLA は `lower`=短縮)で宣言。緩和は不可

違反は `bin/siir check-overlay <path>` で即検出(exit 2)。**変更を加えるときは必ず `check-overlay` を回す**。

複数 overlay は `--overlay` の指定順に逐次適用し、**各 overlay は適用時点の結果より厳格でなければならない**(strictest-wins ではなく順序依存)。例: 24→12→18 は最後で却下される。最も厳しい値を最後に積むのではなく、単調に厳しくする順で並べる。

### `extension_points` 宣言と実装の同期義務

`definitions/*.yaml` の `extension_points` ブロックは読み手と AI エージェント向けの self-documenting 宣言であり、overlay エンジン(`src/siir/overlay.py`)のマージロジックは**この宣言を実行時に読んで** add 可能パス / strengthen 可能フィールド + 方向を導出する。

**これがあるため**: `extension_points` を追加・変更したら、`overlay.py` がそのパス種別(top-level array の add / `array[].field` の strengthen)を解釈できることを確認し、回帰テスト(`tests/test_overlay.py`)で add/collision/strengthen/weaken-reject を検証する。

## doc の段階的開示テンプレ

すべての doc は以下の順で構成する: 1. TL;DR / 2. When to use this / 3. Quick use / 4. Concept(表 + mermaid)/ 5. References。書き方は能動・短文・逆ピラミッド、観測事実と設計提案をラベル分けする。

## 編集規約

- **本文は日本語**。多言語 README は `README.md`=英語(入口)/ `README.ja.md`=日本語(正本)でバッジ直下に相互リンク
- 図は **mermaid** で書き、追加・変更したら `npx md-mermaid-lint docs/*.md` で検証
- 文体は全 doc で統一(である調)
- コメントは日本語可。テストは AAA、命名は `test_<対象>_<条件>_<期待>`

## 更新運用

- 機械可読定義(`definitions/*.yaml` / `schemas/*.json`)が**正本**。spec が変わったら正本から直し、doc は説明としてリンクし直す
- 出典(分析記事)に続報・訂正が出たら、該当する義務/条項の値と `legal_basis` を更新する
- `examples/skills/<name>/SKILL.md` は **`bin/siir ... --format json` を呼ぶ薄ラッパー**として実装(定義のロード・採点ロジックは CLI 側に集約)

## 検証コマンド

```bash
pip install -r requirements.txt pytest
pytest tests/                              # overlay / scoring / SLA / runbook の境界条件
bin/siir --help                            # CLI smoke
bin/siir check-responsibility examples/responsibility/sample-oem-mail.yaml
npx md-mermaid-lint docs/*.md              # mermaid 構文
```

## 横断的な注意点

- **exit code 規約**: 0 ok / 1 partial(yellow)/ 2 block(red, SLA 違反・必須欠落・overlay 却下)/ 3 入力エラー。`tests/` で固定する
- **依存パッケージの extras**: `jsonschema[format-nongpl]` で `"format": "date-time"` 検証を有効化(素の `jsonschema` だと通知時刻の検証が no-op になる)
- **GitHub Actions** は SHA ピン + workflow トップ `permissions: {}` + `persist-credentials: false`
- **コマンド名は既知略語との衝突を pre-check 済み**(本リポは `siir` ← `shared-infra-incident-readiness` 由来)
- **このフレームワークは銀の弾丸ではない**: 責任境界表は「初動 30 分の最小装備」。多層防御・監督責任・演習とセットで運用する(docs の反証節を必ず残す)
