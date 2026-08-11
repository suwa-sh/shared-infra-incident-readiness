# CLAUDE.md

## このリポジトリの正体

**shared-infra-incident-readiness** — 共有インフラ事故初動(最初の 30 分)を救う**診断ツール + 拡張可能フレームワーク**。責任境界表・初動 RACI・DPA 条項・通知 SLA・Tabletop 演習を機械可読定義として持ち、CLI で診断・生成する。MIT の OSS。

出典は共用メール基盤事案(6 ISP の OEM 共有基盤)の**公開報道からの抽出**です。

- **機械可読の正本**(`definitions/` の YAML / `schemas/` の JSON Schema)
- **診断ツール**(`bin/siir` + `src/siir/`)
- **AI エージェント連携サンプル**(`examples/skills/`)

の 3 点セットとして提供する。各社は **オーバーレイ**(`examples/overlays/<company>/`)で自社固有のロール・項目・条項・通知義務・シナリオをフォークせず追加できる。

## 正本の所在(二重保持しない)

| 種類 | 正本パス | 役割 |
|---|---|---|
| 責任境界表 / RACI / シナリオ | `definitions/*.yaml` | 構造的正本 |
| 公式 overlay(脅威モデル拡張) | `overlays/<name>/*.yaml` | 公式配布の追加次元(例: `agentic-attacker`)。`examples/overlays/` は各社が真似るサンプルで別物 |
| 契約 SLA(24h/72h) | `definitions/dpa-clauses.yaml` | 契約上の通知 SLA の正本 |
| 法令・規制の通知期限 | `definitions/notification-obligations.yaml` | 法令クロックの正本 |
| 回答 / インシデント記録契約 | `schemas/*.schema.json` | JSON Schema 契約正本 |
| JSON 出力契約 | `schemas/output-envelope.schema.json` | `contract_version` / `provenance` / `result` の正本 |
| 出典と再確認日 | `definitions/source-registry.yaml` | 定義値を支える一次資料と freshness の正本 |
| 説明書 | `docs/*.md` | 上記の解説。**定義の値は二重保持しない**(リンク参照) |
| 動く入口 | `bin/siir` / `src/siir/` / `examples/` | 上記を消費する CLI と入力サンプル |

**SLA を二重に書かない**: 通知 SLA の値は契約系=`dpa-clauses.yaml`、法令系=`notification-obligations.yaml` のどちらか一方だけに置く。`incident-raci.yaml` は `obligation_ref` / `clause_ref` で **ID 参照するだけ**で値を持たない。

## 定義モデル(flat items + group selector)

`definitions/*.yaml` は単一フラット `items` リスト。id は `<group>`(group ヘッダ、ドット無し)か `<group>.<leaf>`(leaf、ドット 1 個。`separator: "."`)のどちらかで、ネストは 1 階層固定。例: `clauses` ヘッダ + `clauses.DPA01` leaf、`resp` ヘッダ + `resp.RB01` leaf。group ヘッダは group レベルの数値を、leaf は明細(宣言済み数値 + 任意の opaque payload = `cells` / `recommended` / `injects` 等)を持つ。答え(answers)・overlay・相互参照(`obligation_ref` / `clause_ref` / `focus_items`)は group prefix を持たない短い id(`RB01` / `DPA03` 等)で書く — consumer 側 (`src/siir/*.py`) が `overlay.group_items(defn)` + `definitions.local_id(id, sep)` で prefix を剥がして answers と突き合わせる。

## オーバーレイのマージ規則(一貫性の保護)

各社のオーバーレイで可能なのは以下の 2 操作のみ:

- **`add`**: `{id: "<group>.<leaf>", ...}` の形で新しい item を追加。**既存 item の上書き・削除・RACI セルの書換えは不可**
- **`strengthen`**: `{"<group>.<leaf または group>": {field: val}}` で数値フィールドを **強化方向のみ**変更。方向は各定義の `extension_points` に `direction`(SLA は `lower`=短縮)で宣言。緩和は不可

違反は `bin/siir check-overlay <path>` で即検出(exit 2)。**変更を加えるときは必ず `check-overlay` を回す**。

複数 overlay は `--overlay` の指定順に逐次適用し、**各 overlay は適用時点の結果より厳格でなければならない**(strictest-wins ではなく順序依存)。例: 24→12→18 は最後で却下される。最も厳しい値を最後に積むのではなく、単調に厳しくする順で並べる。

### overlay ルーティング(複数定義コマンド)

複数の定義を同時に読むコマンド(`tabletop` / `render-runbook` / `list-definitions` / `validate-record`)は、`definitions.route_overlays()` が各 overlay の `extends` を見て**適用先の定義へ振り分ける**。どの定義にも一致しない `extends` は入力エラー(exit 3)でありサイレントに捨てない。単一定義コマンド(`check-responsibility` / `check-dpa`)はルーティングせず、不一致 overlay を渡したら明示エラーにする。

### `extension_points` 宣言と実装の同期義務

`definitions/*.yaml` の `extension_points` は `{group: <selector>, allow: add}` または `{group: <selector>, level: leaf|group, field: <f>, allow: strengthen, direction: lower|higher}` の構造化宣言(`group` は完全一致 / 前方一致 `"L*"` / `"*"`。キー名は `level` — `on` は YAML 1.1 の boolean キーワードなので使わない)。読み手と AI エージェント向けの self-documenting 宣言であり、overlay エンジン(`src/siir/overlay.py`)のマージロジックは**この宣言を実行時に読んで** add 可能な group / strengthen 可能な group+field+方向を導出する。

**これがあるため**: `extension_points` を追加・変更したら、`overlay.py` がその宣言(`group` selector の add / `level`+`field` の strengthen)を解釈できることを確認し、回帰テスト(`tests/test_overlay.py`)で add/collision/strengthen/weaken-reject を検証する。

## doc の段階的開示テンプレ

すべての doc は以下の順で構成する: 1. TL;DR / 2. When to use this / 3. Quick use / 4. Concept(表 + mermaid)/ 5. References。書き方は能動・短文・逆ピラミッド、観測事実と設計提案をラベル分けする。

## ドキュメントとリリースの境界

- README の Docker 例は `latest` やタグ無しを使わず、実際に公開済みのバージョンタグを明記する
- main にだけ存在し、公開済みイメージに未収録の機能は source checkout 用として説明する。次のタグが公開されるまで、Docker で使えるように書かない
- `/app/...` を README に記載する場合は、そのパスが記載した公開済みイメージ内に存在することを確認する
- バージョン番号そのものを規約へ固定しない。`python scripts/check_docs.py --container` で README の記載と公開物を照合する
- README、`docs/*.md`、`examples/skills/*/SKILL.md` を変更したら、ローカルリンク、見出し anchor、記載 CLI、Mermaid、公開イメージの境界を検証する

## 編集規約

- **本文は日本語**。多言語 README は `README.md`=英語(入口)/ `README.ja.md`=日本語(正本)でバッジ直下に相互リンク
- 図は **mermaid** で書き、追加・変更したら `npm ci && npm run lint:mermaid` で検証
- 文体は全 doc で統一(**ですます調**)。テクニカルライティング(タスク指向見出し / 能動・短文 / 逆ピラミッド / 箇条書きの並列性)に従う
- 専門用語・略語(DPA / RACI / SLA 等)は初出で 1 行説明を添える。CLI は README に**想定ワークフロー(何を用意→どの順で実行→出力をどう読む)**を必ず置く
- コメントは日本語可。テストは AAA、命名は `test_<対象>_<条件>_<期待>`

## 更新運用

- 機械可読定義(`definitions/*.yaml` / `schemas/*.json`)が**正本**。spec が変わったら正本から直し、doc は説明としてリンクし直す
- 出典(分析記事)に続報・訂正が出たら、該当する義務/条項の値と `legal_basis` を更新する
- `examples/skills/<name>/SKILL.md` は **`bin/siir ... --format json` を呼ぶ薄ラッパー**として実装(定義のロード・採点ロジックは CLI 側に集約)

## 検証コマンド

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
.venv/bin/pytest                           # overlay / scoring / SLA / runbook の境界条件
python scripts/check_docs.py --cli         # link / anchor / image tag / 記載 CLI
npm ci && npm run lint:mermaid              # lock 済み mermaid 構文検査
python scripts/check_sources.py             # 出典 coverage / freshness
qlty check --all --no-fix --no-progress --no-upgrade-check
python scripts/check_docs.py --container   # 公開イメージと /app パス。Docker / network 必須
```

リポジトリに `.venv` がある場合は、その Python と pytest を優先する。システムの pyenv が正常だと仮定しない。

## 横断的な注意点

- **exit code 規約**: 0 ok / 1 partial(yellow)/ 2 block(red, SLA 違反・必須欠落・overlay 却下)/ 3 入力エラー。`tests/` で固定する
- **契約版**: 回答と事故記録は `schema_version`、JSON 出力は `contract_version` を必須とする。破壊的変更では major version と `MIGRATION.md` を更新する
- **依存パッケージの extras**: `jsonschema[format-nongpl]` で `"format": "date-time"` 検証を有効化(素の `jsonschema` だと通知時刻の検証が no-op になる)
- **GitHub Actions** は SHA ピン + workflow トップ `permissions: {}` + `persist-credentials: false`
- **コマンド名は既知略語との衝突を pre-check 済み**(本リポは `siir` ← `shared-infra-incident-readiness` 由来)
- **このフレームワークは銀の弾丸ではない**: 責任境界表は「初動 30 分の最小装備」。多層防御・監督責任・演習とセットで運用する(docs の反証節を必ず残す)
