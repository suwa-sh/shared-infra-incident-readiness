# 03. 共有基盤の委託契約に必要な DPA 10 条項

## TL;DR

SIIR は、共有インフラの委託契約で確認する DPA 10 条項を機械可読の定義として提供します。
`siir check-dpa` は自社契約の充足状況を採点し、必須条項の欠落を `BLOCK` として表示します。
この診断は契約レビューの出発点であり、個別案件の法的判断を代替しません。

## When to use this

- 共有 SaaS や共通基盤の委託契約を起案または更新するとき
- 契約交渉の前に、確認すべき条項の抜けを洗い出したいとき
- 委託先の変更後に、通知や監査の条件が維持されているか確認するとき

## Quick use

記入例をコピーし、各条項を `present`、`partial`、`missing` のいずれかで評価します。

```bash
bin/siir check-dpa examples/dpa/sample-dpa-answers.yaml
# DPA03 が missing のため BLOCK
```

## Concept

### DPA が固定する責任

**DPA（Data Processing Agreement）**は、個人データの取扱いを委託する側と、委託される側の契約です。
処理の目的、再委託、事故通知、監査ログ、セキュリティ対応などを定めます。

共有インフラでは、一つの基盤を複数の組織やブランドが利用します。
事故後に通知主体や調査協力を決め始めると初動が遅れるため、平時の契約で分担を合意しておきます。

### 確認する 10 条項

| ID | 条項 | 確認する内容 |
|---|---|---|
| DPA01 | 処理内容の特定 | 目的、データ種別、対象者カテゴリ、期間 |
| DPA02 | 再委託の事前承認 | 再委託の承認方法と再委託先一覧 |
| DPA03 | 委託先から委託元への漏えい通知 SLA | 第一報と確報の期限 |
| DPA04 | 本人通知の主体 | 委託元と委託先のどちらが通知するか |
| DPA05 | 規制当局通知の主体 | 個情委や総務省へ誰が通知するか |
| DPA06 | 監査ログの保持と提供 | 保持期間と提供期限 |
| DPA07 | 鍵とパスワードハッシュの管理 | 方式、責任主体、ローテーション期限 |
| DPA08 | 第三者ソフトウェアのパッチ管理 | Critical 脆弱性への暫定対応期限 |
| DPA09 | インシデント時の合同対応 | フォレンジック、広報、法務の分担 |
| DPA10 | 演習 | Tabletop または Red Team の実施頻度 |

契約上の通知期限は、DPA03 が正本です。
法令または規制上の期限は `definitions/notification-obligations.yaml` に保存します。
二つの期限を分ける理由は、[02. 初動 RACI と通知期限の管理](02_incident_raci_and_sla.md) を参照してください。

### 採点結果を読む

| 回答 | 意味 | 判定への影響 |
|---|---|---|
| `present` | 条項を満たします。 | `OK` |
| `partial` | 一部を満たしますが、追加の合意が必要です。 | `REVISE` |
| `missing` | 必須条項がありません。 | `BLOCK` |

自社固有の条項は overlay の `add` で追加できます。
DPA03 のように厳格化を許可した数値は、overlay の `strengthen` で短縮できます。
たとえば、24 時間の第一報期限を 12 時間へ短縮できますが、36 時間への緩和はできません。

```bash
bin/siir check-overlay examples/overlays/sample-company/extra-clauses.yaml
```

### 契約と監督責任を分けて考える

「DPA に責任分界を書けば、委託元の監督責任がなくなる」という意味ではありません。
DPA は初動の分担を固定する契約上の土台であり、委託先の監督、多層防御、定期演習は別に必要です。

## References

- 正本：[`definitions/dpa-clauses.yaml`](../definitions/dpa-clauses.yaml)
- 記入例：[`examples/dpa/sample-dpa-answers.yaml`](../examples/dpa/sample-dpa-answers.yaml)
- 実装：[`src/siir/check_dpa.py`](../src/siir/check_dpa.py)
