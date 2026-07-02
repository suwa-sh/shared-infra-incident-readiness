# shared-infra-incident-readiness

![OGP](docs/assets/ogp.png)

[![CI](https://github.com/suwa-sh/shared-infra-incident-readiness/actions/workflows/ci.yml/badge.svg)](https://github.com/suwa-sh/shared-infra-incident-readiness/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 🇬🇧 English version: [README.md](README.md)

**共有インフラ事故初動の最初の 30 分**を救う、診断ツール + 拡張可能フレームワークです。誰が説明責任を負うか、DPA のどの条項が欠けているか、通知タイムラインが SLA を守れているか、Tabletop 演習をどう回すか――これらを機械可読の定義として持ち、CLI で診断します。KDDI 共用メール基盤事案(6 ISP の OEM 共有基盤)の**公開分析からの抽出**です。

主な特徴は、次の 3 点です。

1. **事故初動の備えを診断します** — 責任境界・契約条項(DPA)・通知 SLA を機械的に点検し、結果を決定的な合否で返します。
2. **機械可読の正本を持ちます** — 責任境界表・RACI・DPA 条項・通知義務・シナリオを定義として持ち、AI エージェントや CI から直接利用できます。
3. **フォークせず拡張できます** — 各社固有のロール・項目・条項・通知義務・シナリオを、overlay で追加できます。

> **用語について**: **DPA**(Data Processing Agreement)は、個人データの取扱いを委託元・委託先のあいだで取り決める契約です。**RACI** は責任を Responsible(実施)/ Accountable(説明責任)/ Consulted(相談)/ Informed(通知)の 4 役割で整理する手法です。**SLA**(Service Level Agreement)はここでは「いつまでに通知するか」の期限を指します。

> **言語について**: `docs/` は日本語(著者の作業言語)で書いています。英語 README が入口、本ファイル(日本語)が正本テキストです。

## Quick start(3 分)

セットアップ不要です。公開済みイメージを pull して実行するだけで、同梱のサンプルがそのまま動きます。

```bash
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 --version

# 同梱のサンプルで各コマンドの出力を確認します
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 \
  check-responsibility examples/responsibility/sample-oem-mail.yaml
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 \
  check-dpa examples/dpa/sample-dpa-answers.yaml
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 \
  validate-record examples/records/sample-incident.json --level extended
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 \
  render-runbook examples/responsibility/sample-oem-mail.yaml --scenario rce-6brand
docker run --rm ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 \
  tabletop --scenario rce-6brand examples/responsibility/sample-oem-mail.yaml
```

`--version` は、アプリのバージョンと同梱の overlay エンジンのバージョンを表示します(例: `siir 0.2.0 (overlay-scoring-skeleton 0.1.0)`)。

各コマンドは決定的な exit code を返すので、CI のゲートに使えます。
**0** ok ・ **1** partial(黄: 警告 / 都度協議 / 未送信) ・ **2** block(欠落・条項不足・SLA 違反・overlay 却下) ・ **3** 入力エラー。

## 使い方(想定ワークフロー)

コマンドは「自分のデータを用意して実行する」ものです。自社のファイルが入ったディレクトリをコンテナにマウントします。以降の説明を読みやすくするため、シェル関数を定義しておきます。

```bash
siir() { docker run --rm -v "$PWD:/data" -w /data \
  ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.2.0 "$@"; }
```

同梱の [`examples/`](examples/) をひな型として、自社の値に書き換えてから実行します。平時の備えから事故時の検証まで、次の順で使います。

### ステップ 0 — 準備

[`examples/responsibility/sample-oem-mail.yaml`](examples/responsibility/sample-oem-mail.yaml) と
[`examples/dpa/sample-dpa-answers.yaml`](examples/dpa/sample-dpa-answers.yaml) をひな型に、
`my-responsibility.yaml` / `my-dpa.yaml` として自社用の入力ファイルを作ります。

### ステップ 1 — 責任境界を点検する(平時)

`my-responsibility.yaml` の `matrix` を、自社の事故初動の割当(R/A/C/I)に書き換えます。まだ決まっていない箱は `tbd`(都度協議)と書いて構いません。

```bash
siir check-responsibility my-responsibility.yaml
```

出力例(抜粋):

```text
Target: 共用メール基盤 (6 ISP OEM)
Responsibility readiness: 83%

[OK] RB01 利用者向け窓口・本人通知: OK (ok)
[..] RB04 プレスリリース (共同 / 個別の決定): REVISE (accountability_deferred)
    gray (tbd): oem_operator
[NG] RB12 平時 / 事故時の合同演習主催: BLOCK (unassigned)

Conclusion: BLOCK
```

`[OK]` ok / `[..]` revise / `[NG]` block を行ごとに示し、最後に総合判定を返します。`BLOCK`(未割当・説明責任の分裂)を先に潰し、`REVISE`(`tbd` のグレーゾーン)を計画的に埋めます。詳細は [docs/01](docs/01_responsibility_boundary.md) を参照してください。

### ステップ 2 — 契約(DPA)の抜けを点検する(平時)

`my-dpa.yaml` の各条項を `present` / `partial` / `missing` で記入し、委託契約に必須 10 条項が揃っているかを確認します。

```bash
siir check-dpa my-dpa.yaml
```

出力例(抜粋):

```text
Target: 共用メール基盤 委託契約 v1
DPA coverage: 70%

[OK] DPA01 処理内容の特定: PRESENT (required)
[NG] DPA03 委託先→委託元 漏えい通知SLA: MISSING (required)
[..] DPA05 規制当局通知の主体明示: PARTIAL (required)

Conclusion: BLOCK
```

必須条項が `missing` なら `BLOCK`、`partial` があれば `REVISE` になります。詳細は [docs/03](docs/03_dpa_clauses.md) を参照してください。

### ステップ 3 — 平時の演習とランブックを用意する

責任境界表とシナリオから、初動ランブック(責任境界表 → Runbook → Communication Tree)と Tabletop 演習プログラムを生成します。出力は決定的なので、レビューや差分管理ができます。

```bash
siir render-runbook my-responsibility.yaml --scenario rce-6brand
siir tabletop --scenario rce-6brand my-responsibility.yaml
```

`render-runbook` の出力例(Markdown、抜粋):

```text
# 初動ランブック: 共用メール基盤 (6 ISP OEM)

- シナリオ: 共有メール基盤の第三者製SW RCE → 6ブランド同時公表
- 想定影響ブランド数: 6

## Stage 1. 責任境界表 (この事故で誰が何の責任か)

| 項目 | Accountable | Responsible | 都度協議 | 出典 |
|---|---|---|---|---|
| RB02 * 個情委への速報・確報 | 委託元ISP | OEM基盤運用者 | - | org |
| RB04 * プレスリリース (共同 / 個別の決定) | - | - | OEM基盤運用者 | org |
... (Stage 2 初動ランブック / Stage 3 Communication Tree が続く)
```

`tabletop` の出力例(Markdown、抜粋):

```text
# Tabletop 演習プログラム: 共有メール基盤の第三者製SW RCE → 6ブランド同時公表

- 所要時間: 90 分

## 注入イベント (時系列)
- T+0分: 1ブランドの EDR が不審なプロセス実行を検知。共有基盤起因かは未確定
- T+30分: 報道機関から「6社共通基盤か」と問い合わせ。24h SLA の第一報期限が接近
... (ファシリ設問 / focus 項目が続く)
```

出力は Markdown なので、そのまま社内 wiki やランブックに貼れます。利用できるシナリオ id は `siir list-definitions` で確認できます。詳細は [docs/04](docs/04_tabletop_and_runbook.md) を参照してください。

### ステップ 4 — 事故が起きたら通知 SLA を検証する(事故時)

[`examples/records/sample-incident.json`](examples/records/sample-incident.json) をひな型に、実際の事故記録(影響ブランド・共有コンポーネント・通知タイムライン)を `my-incident.json` として作り、通知が SLA を守れているかを検証します。

```bash
siir validate-record my-incident.json --level extended
```

出力例:

```text
Record schema: incident_record_extended
[OK] schema: valid

Notification SLA:
  [OK] DPA03 委託先→委託元 漏えい通知SLA: sent 11.0h after awareness (<= 24h)
  [NG] DPA03 委託先→委託元 漏えい通知SLA (確報): sent 102.0h after awareness, SLA is 72h
  [i] OB03 総務省への重大事故報告: non-numeric deadline; review manually
  [..] OB04 本人への通知: not sent yet (pending)

Conclusion: BLOCK
```

まずスキーマ(影響ブランド・共有コンポーネント・通知タイムラインの形式)を検証し、続いて各通知が SLA に間に合っているかを照合します。数値締切の超過(`breach`)や時系列の逆転を検出し、「遅滞なく」などの非数値締切は手動レビュー(`[i]`)に回します。詳細は [docs/02](docs/02_incident_raci_and_sla.md) を参照してください。

### ステップ 5 — 自社ルールで拡張する(任意)

各社固有のロール・条項・シナリオは overlay で追加し、適用前に検証します。
[`examples/overlays/sample-company/extra-clauses.yaml`](examples/overlays/sample-company/extra-clauses.yaml)
をひな型に `my-overlay.yaml` を作ります。

```bash
siir check-overlay my-overlay.yaml
siir check-dpa my-dpa.yaml --overlay my-overlay.yaml
```

`check-overlay` の出力例:

```text
[OK] overlay valid (add / strengthen rules satisfied)
```

overlay が `add`(追加)/ `strengthen`(厳格化)のルールを満たせば `[OK]`、違反すれば `[NG]` と理由を返します。検証を通った overlay を `--overlay` で各コマンドに適用します。

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

[使い方(想定ワークフロー)](#使い方想定ワークフロー)の `siir` シェル関数を使い、
`siir check-overlay <path>` で適用前に検証します。

## 開発

```bash
pytest tests/                  # 境界条件・exit code
bin/siir --help                # CLI smoke
npx md-mermaid-lint docs/*.md  # 図の構文
```

## ライセンス

MIT です。[LICENSE](LICENSE) を参照してください。
