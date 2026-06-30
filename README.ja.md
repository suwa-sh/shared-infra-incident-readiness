# shared-infra-incident-readiness

![OGP](docs/assets/ogp.png)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 🇬🇧 English version: [README.md](README.md)

**共有インフラ事故初動の最初の 30 分**を救う、診断ツール + 拡張可能フレームワークです。誰が説明責任を負うか、DPA のどの条項が欠けているか、通知タイムラインが SLA を守れているか、Tabletop 演習をどう回すか――これらを機械可読の定義として持ち、CLI で診断します。KDDI 共用メール基盤事案(6 ISP の OEM 共有基盤)の**公開分析からの抽出**であり、内部情報には依拠しません。

clone すると、次の 3 つが手に入ります。

1. **CLI 診断** — `bin/siir check-responsibility` / `check-dpa` / `validate-record` / `render-runbook` / `tabletop`。決定的で数秒、exit code でゲートできます。
2. **機械可読の正本**(`definitions/*.yaml`・`schemas/*.json`)。AI エージェントが context にロードでき、CI から直接呼べます。
3. **overlay 拡張点**。各社がロール・項目・条項・通知義務・シナリオを**フォークせず**追加できます。

> **用語について**: **DPA**(Data Processing Agreement)は、個人データの取扱いを委託元・委託先のあいだで取り決める契約です。**RACI** は責任を Responsible(実施)/ Accountable(説明責任)/ Consulted(相談)/ Informed(通知)の 4 役割で整理する手法です。**SLA**(Service Level Agreement)はここでは「いつまでに通知するか」の期限を指します。

> **言語について**: `docs/` は日本語(著者の作業言語)で書いています。英語 README が入口、本ファイル(日本語)が正本テキストです。

## Quick start(3 分)

```bash
git clone https://github.com/suwa-sh/shared-infra-incident-readiness.git
cd shared-infra-incident-readiness
pip install -r requirements.txt

# 同梱のサンプルで各コマンドの出力を確認します
bin/siir check-responsibility examples/responsibility/sample-oem-mail.yaml
bin/siir check-dpa examples/dpa/sample-dpa-answers.yaml
bin/siir validate-record examples/records/sample-incident.json --level extended
bin/siir render-runbook examples/responsibility/sample-oem-mail.yaml --scenario rce-6brand
bin/siir tabletop --scenario rce-6brand examples/responsibility/sample-oem-mail.yaml
```

各コマンドは決定的な exit code を返すので、CI のゲートに使えます。
**0** ok ・ **1** partial(黄: 警告 / 都度協議 / 未送信) ・ **2** block(欠落・条項不足・SLA 違反・overlay 却下) ・ **3** 入力エラー。

## 使い方(想定ワークフロー)

コマンドは「自分のデータを用意して実行する」ものです。同梱の `examples/` をひな型としてコピーし、自社の値に書き換えてから実行します。平時の備えから事故時の検証まで、次の順で使います。

### ステップ 0 — 準備

サンプルをコピーして、自社用の入力ファイルを作ります。

```bash
cp examples/responsibility/sample-oem-mail.yaml my-responsibility.yaml
cp examples/dpa/sample-dpa-answers.yaml         my-dpa.yaml
```

### ステップ 1 — 責任境界を点検する(平時)

`my-responsibility.yaml` の `matrix` を、自社の事故初動の割当(R/A/C/I)に書き換えます。まだ決まっていない箱は `tbd`(都度協議)と書いて構いません。

```bash
bin/siir check-responsibility my-responsibility.yaml
```

出力の `BLOCK`(未割当・説明責任の分裂)を先に潰し、`REVISE`(`tbd` のグレーゾーン)を計画的に埋めます。詳細は [docs/01](docs/01_responsibility_boundary.md) を参照してください。

### ステップ 2 — 契約(DPA)の抜けを点検する(平時)

`my-dpa.yaml` の各条項を `present` / `partial` / `missing` で記入し、委託契約に必須 10 条項が揃っているかを確認します。

```bash
bin/siir check-dpa my-dpa.yaml
```

必須条項が `missing` なら `BLOCK` になります。詳細は [docs/03](docs/03_dpa_clauses.md) を参照してください。

### ステップ 3 — 平時の演習とランブックを用意する

責任境界表とシナリオから、初動ランブック(責任境界表 → Runbook → Communication Tree)と Tabletop 演習プログラムを生成します。出力は決定的なので、レビューや差分管理ができます。

```bash
bin/siir render-runbook my-responsibility.yaml --scenario rce-6brand
bin/siir tabletop --scenario rce-6brand my-responsibility.yaml
```

利用できるシナリオ id は `bin/siir list-definitions` で確認できます。詳細は [docs/04](docs/04_tabletop_and_runbook.md) を参照してください。

### ステップ 4 — 事故が起きたら通知 SLA を検証する(事故時)

`examples/records/sample-incident.json` をひな型に、実際の事故記録(影響ブランド・共有コンポーネント・通知タイムライン)を作り、通知が SLA を守れているかを検証します。

```bash
cp examples/records/sample-incident.json my-incident.json
bin/siir validate-record my-incident.json --level extended
```

通知タイムラインの SLA 違反(`breach`)や時系列の逆転を検出します。詳細は [docs/02](docs/02_incident_raci_and_sla.md) を参照してください。

### ステップ 5 — 自社ルールで拡張する(任意)

各社固有のロール・条項・シナリオは overlay で追加し、適用前に検証します。

```bash
bin/siir check-overlay examples/overlays/sample-company/extra-clauses.yaml
bin/siir check-dpa my-dpa.yaml --overlay examples/overlays/sample-company/extra-clauses.yaml
```

## 誰のためのものか

| あなたが… | ここから |
|---|---|
| OEM / 共通基盤運用者の **PMO・セキュリティ責任者** | [`docs/01_responsibility_boundary.md`](docs/01_responsibility_boundary.md) — 自社の表を埋めて `check-responsibility` |
| 委託契約の **法務・調達** | [`docs/03_dpa_clauses.md`](docs/03_dpa_clauses.md) — 必須 10 条項を点検 |
| インシデント記録基盤を作る **エンジニア・SRE** | [`schemas/incident-record.schema.json`](schemas/incident-record.schema.json) + [`docs/02_incident_raci_and_sla.md`](docs/02_incident_raci_and_sla.md) |
| **コンサル・提案者** | 全 `docs/` + overlay モデル — clone → 顧客別に overlay → 提案 |

## overlay モデル

overlay は、フォークせずにフレームワークを拡張する仕組みです。許される操作は 2 つだけで、各定義の `extension_points` で宣言されます。

- **`add`** — 新しいロール / 項目 / 条項 / 通知義務 / シナリオを(新しい `id` で)追加します。既存の上書き・削除は却下されます。
- **`strengthen`** — 宣言された数値フィールドを厳格方向にのみ移動します(例: SLA を 24h→12h に短縮)。緩和は却下されます。

`bin/siir check-overlay <path>` で、適用前に検証します。

## 開発

```bash
pip install -r requirements.txt pytest
pytest tests/                  # 境界条件・exit code
bin/siir --help                # CLI smoke
npx md-mermaid-lint docs/*.md  # 図の構文
```

## ライセンス

MIT です。[LICENSE](LICENSE) を参照してください。
