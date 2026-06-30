# 03. DPA 必須 10 条項 — 共有基盤の委託契約に最低限書く

## TL;DR

共有インフラの DPA / 委託契約に最低限盛り込む **10 条項**(GDPR Art.28(3) + 個情委ガイドライン合成)。`siir check-dpa` が契約のカバレッジを採点し、必須条項の欠落を BLOCK で表面化する。

## When to use this

- 共有 SaaS / 基盤の委託契約をレビュー・起案している
- 契約交渉の出発点として「何が抜けているか」を機械的に出したい

## Quick use

```bash
bin/siir check-dpa examples/dpa/sample-dpa-answers.yaml
# => DPA03 (通知SLA) が missing => BLOCK
```

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

### 反証 — 条項を書いても監督責任は消えない

ベネッセ判決は「契約に責任分界が書かれていても、委託元の監督責任は免除されない」と判断した。本リポの DPA 条項は**初動の責任分界を明文化する出発点**であり、監督義務・多層防御・演習とセットで運用する(→ [04](04_tabletop_and_runbook.md))。

### 採点と overlay

`check-dpa` の answers は各条項を `present` / `partial` / `missing` で記入する。必須条項が `missing` なら BLOCK、`partial` があれば REVISE。自社固有の条項は overlay の `add` で増やせ、`DPA03` の SLA は `strengthen`(24h→12h など短縮方向のみ)で厳格化できる:

```bash
bin/siir check-overlay examples/overlays/sample-company/extra-clauses.yaml   # add DPA11 + strengthen DPA03
```

## References

- 正本: [`definitions/dpa-clauses.yaml`](../definitions/dpa-clauses.yaml)
- 実装: [`src/siir/check_dpa.py`](../src/siir/check_dpa.py)
