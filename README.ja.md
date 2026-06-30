# shared-infra-incident-readiness

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 🇬🇧 English version: [README.md](README.md)

**共有インフラ事故初動の最初の 30 分**を救う診断ツール + 拡張可能フレームワーク。誰が説明責任を負うか、DPA のどの条項が欠けているか、通知タイムラインが SLA を守れているか、Tabletop 演習をどう回すか。共用メール基盤事案(6 ISP の OEM 共有基盤)の**公開分析からの抽出**であり、内部情報には依拠しない。

clone すると 3 つが手に入る:

1. **CLI 診断** — `bin/siir check-responsibility` / `check-dpa` / `validate-record` / `render-runbook` / `tabletop`。決定的で数秒、exit code でゲートできる。
2. **機械可読の正本**(`definitions/*.yaml`・`schemas/*.json`)。AI エージェントが context にロードでき、CI から直接呼べる。
3. **overlay 拡張点**。各社がロール・項目・条項・通知義務・シナリオを**フォークせず**追加できる。

> **言語について**: `docs/` は日本語(著者の作業言語)。英語 README が入口、本ファイル(日本語)が正本テキスト。

## Quick start (3 分)

```bash
git clone https://github.com/suwa-sh/shared-infra-incident-readiness.git
cd shared-infra-incident-readiness
pip install -r requirements.txt

# 1. 記入済みの責任境界表を採点
bin/siir check-responsibility examples/responsibility/sample-oem-mail.yaml

# 2. DPA 条項のカバレッジを点検
bin/siir check-dpa examples/dpa/sample-dpa-answers.yaml

# 3. インシデント記録 + 通知 SLA タイムラインを検証
bin/siir validate-record examples/records/sample-incident.json --level extended

# 4. 三段ランブック (責任境界表 → 初動ランブック → Communication Tree) を生成
bin/siir render-runbook examples/responsibility/sample-oem-mail.yaml --scenario rce-6brand

# 5. Tabletop 演習プログラムを生成
bin/siir tabletop --scenario rce-6brand examples/responsibility/sample-oem-mail.yaml

# 6. overlay を検証 (add / strengthen のみ) + 定義を確認
bin/siir check-overlay examples/overlays/sample-company/extra-clauses.yaml
bin/siir list-definitions
```

各コマンドは決定的な exit code を返すので CI ゲートに使える:
**0** ok ・ **1** partial(黄: 警告 / 都度協議 / 未送信) ・ **2** block(欠落・条項不足・SLA 違反・overlay 却下) ・ **3** 入力エラー。

## 誰のためのものか

| あなたが… | ここから |
|---|---|
| OEM / 共通基盤運用者の **PMO・セキュリティ責任者** | [`docs/01_responsibility_boundary.md`](docs/01_responsibility_boundary.md) — 自社の表を埋めて `check-responsibility` |
| 委託契約の **法務・調達** | [`docs/03_dpa_clauses.md`](docs/03_dpa_clauses.md) — 必須 10 条項を点検 |
| インシデント記録基盤を作る **エンジニア・SRE** | [`schemas/incident-record.schema.json`](schemas/incident-record.schema.json) + [`docs/02_incident_raci_and_sla.md`](docs/02_incident_raci_and_sla.md) |
| **コンサル・提案者** | 全 `docs/` + overlay モデル — clone → 顧客別に overlay → 提案 |

## overlay モデル

overlay はフォークせずにフレームワークを拡張する仕組み。許される操作は 2 つだけで、各定義の `extension_points` で宣言される:

- **`add`** — 新しいロール / 項目 / 条項 / 通知義務 / シナリオを(新しい `id` で)追加。既存の上書き・削除は却下。
- **`strengthen`** — 宣言された数値フィールドを厳格方向にのみ移動(例: SLA を 24h→12h に短縮)。緩和は却下。

`bin/siir check-overlay <path>` で適用前に検証する。

## 開発

```bash
pip install -r requirements.txt pytest
pytest tests/                  # 境界条件・exit code
bin/siir --help                # CLI smoke
npx md-mermaid-lint docs/*.md  # 図の構文
```

## ライセンス

MIT — [LICENSE](LICENSE) 参照。
