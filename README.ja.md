# shared-infra-incident-readiness

![OGP](docs/assets/ogp.png)

[![CI](https://github.com/suwa-sh/shared-infra-incident-readiness/actions/workflows/ci.yml/badge.svg)](https://github.com/suwa-sh/shared-infra-incident-readiness/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> 🇬🇧 English version: [README.md](README.md)

**shared-infra-incident-readiness（SIIR）** は、共有インフラ事故の最初の 30 分に必要な責任、契約、通知期限を診断する CLI です。
責任境界表、初動 RACI、DPA 条項、通知義務、Tabletop シナリオを機械可読の定義として提供します。

SIIR は、共用メール基盤事案の公開情報を基に作成しました。
各組織は基本定義をフォークせず、overlay で固有のロール、責任項目、契約条項、通知義務、シナリオを追加できます。

## SIIR で確認できること

| 確認する対象 | コマンド | 主な結果 |
|---|---|---|
| 事故初動の責任境界 | `check-responsibility` | 責任者の未割当、説明責任の分裂、都度協議 |
| DPA 条項の充足状況 | `check-dpa` | 必須条項の欠落と部分充足 |
| インシデント記録 | `validate-record` | スキーマ違反、通知期限の超過、未送信通知 |
| 初動ランブック | `render-runbook` | 責任境界、初動順序、連絡経路 |
| Tabletop 演習 | `tabletop` | 注入イベント、設問、重点項目の責任者 |
| overlay | `check-overlay` | `add` と `strengthen` の規則違反 |
| 有効な定義 | `list-definitions` | 基本定義と overlay を統合した項目一覧 |

**DPA（Data Processing Agreement）** は、個人データの取扱いを委託元と委託先の間で定める契約です。
**RACI** は、実施責任、説明責任、相談先、通知先を整理する方法です。
**SLA（Service Level Agreement）** は、このリポジトリでは主に通知や対応の期限を指します。
**Tabletop 演習** は、シナリオに沿って判断と連絡を確認する机上演習です。
**Communication Tree** は、誰が、いつ、誰へ、何を伝えるかを表す連絡経路です。

`docs/` は日本語で記述しています。
このファイルを日本語版の正本とし、[README.md](README.md) を英語の入口として提供します。

## 3 分で試す

公開済みの Docker イメージ `v0.3.0` を使います。
セットアップは不要です。

```bash
docker run --rm \
  ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.3.0 \
  --version

docker run --rm \
  ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.3.0 \
  check-responsibility \
  examples/responsibility/sample-oem-mail.yaml
```

二つ目のコマンドは、責任項目ごとの `OK`、`REVISE`、`BLOCK` と、全体の結論を表示します。
同梱例では RB12 が未割当のため、結論は `BLOCK` です。

各コマンドは、次の exit code を返します。

| exit code | 意味 | 例 |
|---|---|---|
| 0 | `OK` | 診断項目を満たします。 |
| 1 | `REVISE` | 都度協議、部分充足、未送信通知があります。 |
| 2 | `BLOCK` | 必須項目の欠落、期限超過、overlay 違反があります。 |
| 3 | 入力エラー | ファイル、構文、参照、引数に誤りがあります。 |

CI では、exit code 2 と 3 を失敗条件として扱えます。
exit code 1 を失敗にするかは、組織の運用方針に合わせて決めます。

## 自社データで診断する

Docker で自社ファイルを読むため、現在のディレクトリを `/data` にマウントします。
次のシェル関数を定義すると、以降のコマンドを短く書けます。

```bash
siir() {
  docker run --rm \
    -v "$PWD:/data" \
    -w /data \
    ghcr.io/suwa-sh/shared-infra-incident-readiness:v0.3.0 \
    "$@"
}
```

### 1. 責任境界を記入する

[`examples/responsibility/sample-oem-mail.yaml`](examples/responsibility/sample-oem-mail.yaml) を `my-responsibility.yaml` としてコピーします。
`matrix` の RACI セルを自社の割当に書き換えます。
まだ決めていないセルには `tbd` を記入します。

```bash
siir check-responsibility my-responsibility.yaml
```

`BLOCK` を先に解消し、`REVISE` には決定者と解決期限を設定します。
採点方法は [責任境界の解説](docs/01_responsibility_boundary.md) を参照してください。

### 2. DPA の条項を確認する

[`examples/dpa/sample-dpa-answers.yaml`](examples/dpa/sample-dpa-answers.yaml) を `my-dpa.yaml` としてコピーします。
各条項を `present`、`partial`、`missing` のいずれかで記入します。

```bash
siir check-dpa my-dpa.yaml
```

必須条項が `missing` なら `BLOCK`、`partial` なら `REVISE` です。
条項の意味は [DPA の解説](docs/03_dpa_clauses.md) を参照してください。

### 3. ランブックと演習進行表を生成する

責任境界表とシナリオから、初動ランブックと Tabletop 演習の進行表を生成します。

```bash
siir render-runbook \
  my-responsibility.yaml \
  --scenario rce-6brand

siir tabletop \
  --scenario rce-6brand \
  my-responsibility.yaml
```

`render-runbook` は、責任境界、初動活動、Communication Tree の 3 段を出力します。
`tabletop` は、時系列の注入イベント、ファシリテーション設問、重点項目の責任者を出力します。
詳しい読み方は [Tabletop 演習と初動ランブック](docs/04_tabletop_and_runbook.md) を参照してください。

### 4. 事故記録と通知期限を検証する

[`examples/records/sample-incident.json`](examples/records/sample-incident.json) を `my-incident.json` としてコピーします。
影響範囲、共有コンポーネント、通知時刻を実際の事故に合わせて記入します。

```bash
siir validate-record my-incident.json --level extended
```

CLI はスキーマを先に検証し、その後で数値化できる通知期限を照合します。
「遅滞なく」のように数値化していない期限は、自動で合否を決めず、手動確認へ回します。
期限の管理方法は [初動 RACI と通知期限](docs/02_incident_raci_and_sla.md) を参照してください。

### 5. 有効な定義を確認する

基本定義と指定した overlay を統合した結果は、`list-definitions` で確認できます。

```bash
siir list-definitions

siir list-definitions \
  --format json \
  --detail \
  --overlay /app/overlays/agentic-attacker/responsibility.yaml
```

`--detail` は JSON 出力専用です。
項目本文、注記、推奨セル、ロール名を AI エージェントや連携処理から読む場合に使います。

## 公式 overlay を使う

公式 overlay は [`overlays/`](overlays/) にあります。
それぞれ独立しており、必要に応じて併用できます。

### agentic-attacker

`agentic-attacker` は、自律 AI エージェントが駆動する侵入事案への初動責任を追加します。
責任項目 5 件、初動活動 3 件、Tabletop シナリオ 1 本で構成します。

```bash
siir check-responsibility \
  my-responsibility.yaml \
  --overlay /app/overlays/agentic-attacker/responsibility.yaml
```

この overlay は Docker イメージ `v0.3.0` に含まれます。
詳細は [agentic-attacker overlay](docs/06_agentic_attacker_overlay.md) を参照してください。

### evaluation-containment

`evaluation-containment` は、安全制御を弱めた能力評価を実施する組織の責任を追加します。
責任項目 7 件、順序付き初動活動 7 件、評価専用ロール 4 件、Tabletop シナリオ、第三者連絡の分岐で構成します。

この overlay は `v0.3.0` のリリース後に追加されています。
次のタグを公開するまでは、現在の source checkout で `bin/siir` を実行してください。

```bash
python3 -m venv .venv
.venv/bin/pip install -e .

bin/siir render-runbook \
  examples/responsibility/sample-evaluation-containment.yaml \
  --scenario evaluation-containment \
  --overlay overlays/evaluation-containment/scenarios.yaml \
  --overlay overlays/evaluation-containment/responsibility.yaml \
  --overlay overlays/evaluation-containment/incident-raci.yaml
```

詳細は [evaluation-containment overlay](docs/07_evaluation_containment_overlay.md) を参照してください。

## overlay で自社ルールを追加する

**overlay** は、基本定義をフォークせずに項目や数値を拡張する仕組みです。
各定義の `extension_points` が、許可する操作を宣言します。

- **`add`**：新しい ID でロール、項目、条項、通知義務、シナリオを追加します。
  既存項目の上書きと削除はできません。
- **`strengthen`**：許可された数値を厳格な方向へ変更します。
  たとえば、24 時間の SLA を 12 時間へ短縮できますが、36 時間へ緩和できません。

同梱例を基に自社 overlay を作り、適用前に検証します。

```bash
siir check-overlay examples/overlays/sample-company/extra-clauses.yaml
siir check-dpa \
  my-dpa.yaml \
  --overlay examples/overlays/sample-company/extra-clauses.yaml
```

複数の overlay は、`--overlay` の指定順に適用します。
各 overlay は、その時点の定義より厳格でなければなりません。

## 読者別の入口

| 読者 | 最初に読む文書 |
|---|---|
| PMO、セキュリティ責任者 | [責任境界](docs/01_responsibility_boundary.md) |
| 法務、調達担当 | [DPA 10 条項](docs/03_dpa_clauses.md) |
| エンジニア、SRE | [初動 RACI と通知期限](docs/02_incident_raci_and_sla.md) |
| 演習の設計者 | [Tabletop 演習と初動ランブック](docs/04_tabletop_and_runbook.md) |
| SaaS の委託運用者 | [SaaS 委託先の記入例](docs/05_worked_example.md) |
| AI セキュリティ担当 | [agentic-attacker](docs/06_agentic_attacker_overlay.md) と [evaluation-containment](docs/07_evaluation_containment_overlay.md) |

## リポジトリの構成

```text
shared-infra-incident-readiness/
├── definitions/     # 機械可読の基本定義
├── schemas/         # インシデント記録の JSON Schema
├── overlays/        # 公式 overlay
├── bin/ と src/     # CLI
├── examples/        # 入力例、自社 overlay 例、AI エージェント用 skill
├── docs/            # 日本語の解説
└── tests/           # 採点、期限、overlay、出力の境界条件
```

## 開発

```bash
pytest tests/
bin/siir --help
npx md-mermaid-lint docs/*.md
python scripts/check_docs.py --cli
python scripts/check_docs.py --container
```

## ライセンス

MIT License です。
[LICENSE](LICENSE) を参照してください。
