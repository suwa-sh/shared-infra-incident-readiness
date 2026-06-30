# 03. DPA 必須 10 条項 — 共有基盤の委託契約に最低限書く

## TL;DR

共有インフラの委託契約に最低限盛り込む **DPA 10 条項**(GDPR Art.28(3) と個情委ガイドラインの合成)です。`siir check-dpa` が契約のカバレッジを採点し、必須条項の欠落を `BLOCK` で表面化します。

## DPA とは

**DPA**(Data Processing Agreement、データ処理契約)は、個人データの取扱いを**委託する側(委託元 / controller)と委託される側(委託先 / processor)のあいだで取り決める契約**です。「何を・何のために処理するか」「事故が起きたとき誰がいつ通知するか」「監査ログをどう残すか」などを定めます。

共有インフラでは、1 つの基盤を複数のブランドが利用するため、事故時の責任分界が曖昧になりがちです。DPA は、その分界を**平時に契約で固定しておく**ための土台になります。本リポは、その DPA に最低限必要な 10 条項を機械可読の正本(`definitions/dpa-clauses.yaml`)として持ち、自社契約に揃っているかを採点します。

## When to use this

- 共有 SaaS / 基盤の委託契約をレビュー・起案している
- 契約交渉の出発点として「何が抜けているか」を機械的に出したい

## Quick use

```bash
bin/siir check-dpa examples/dpa/sample-dpa-answers.yaml
# => DPA03 (通知SLA) が missing => BLOCK
```

`examples/dpa/sample-dpa-answers.yaml` をコピーし、各条項を `present`(ある)/ `partial`(部分的)/ `missing`(ない)で記入してから実行します。

## Concept

### 10 条項

| ID | 条項 | 要点 |
|---|---|---|
| DPA01 | 処理内容の特定 | 目的・種別・カテゴリ・期間 |
| DPA02 | 再委託の事前承認 | 再委託先一覧の維持 |
| DPA03 | 委託先→委託元 漏えい通知SLA | 24h第一報 / 72h確報(実務推奨)。**契約 SLA の正本はここ** |
| DPA04 | 本人通知の主体明示 | 委託元 / 委託先のどちらか |
| DPA05 | 規制当局通知の主体明示 | 個情委・総務省への通知主体 |
| DPA06 | 監査ログの保持期間と提供義務 | 要請時に N営業日以内提供 |
| DPA07 | アクセス鍵・パスワードハッシュ管理責任 | ハッシュ指定、鍵ローテーションSLA |
| DPA08 | 第三者ソフトウェアのパッチ管理 | Critical公表後72h以内に暫定対応着手 |
| DPA09 | インシデント時の合同対応条項 | フォレンジック・広報・法務の役割 |
| DPA10 | 演習義務 | 年1回以上の Tabletop / Red Team を明記 |

> **SLA の正本の置き場**: 契約上の通知期限(24h / 72h)は DPA03 に置きます。一方、法令・規制の期限(個情委への速報・確報、総務省への報告)は `notification-obligations.yaml` に分けて持ちます。同じ値を 2 か所に書かないための分担です(→ [02](02_incident_raci_and_sla.md))。

### 反証 — 条項を書いても監督責任は消えません

ベネッセ判決は「契約に責任分界が書かれていても、委託元の監督責任は免除されない」と判断しました。本リポの DPA 条項は**初動の責任分界を明文化する出発点**であり、監督義務・多層防御・演習とセットで運用します(→ [04](04_tabletop_and_runbook.md))。

### 採点と overlay

`check-dpa` の answers は、各条項を `present` / `partial` / `missing` で記入します。必須条項が `missing` なら `BLOCK`、`partial` があれば `REVISE` です。自社固有の条項は overlay の `add` で増やせます。`DPA03` の SLA は `strengthen`(24h→12h など短縮方向のみ)で厳格化できます。

```bash
bin/siir check-overlay examples/overlays/sample-company/extra-clauses.yaml   # add DPA11 + strengthen DPA03
```

## References

- 正本: [`definitions/dpa-clauses.yaml`](../definitions/dpa-clauses.yaml)
- 実装: [`src/siir/check_dpa.py`](../src/siir/check_dpa.py)
