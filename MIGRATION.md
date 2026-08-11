# 移行ガイド

## 次回リリースへ移行する

1. 現在のイメージ tag または digest と、JSON 証跡を保存します。
2. YAML／JSON 入力のトップレベルへ `schema_version: 1` を追加します。
3. JSON consumer の参照先をトップレベルから `result` 配下へ変更します。
4. `contract_version == 1` を確認してから `result` を処理します。
5. overlay に `compatible_base_version: 1` を追加します。
6. staging で `check-overlay` と全診断を再実行し、exit code と結果差分を確認します。

旧形式:

```json
{"conclusion": "BLOCK", "items": []}
```

新形式:

```json
{
  "contract_version": 1,
  "provenance": {"command": "check-responsibility"},
  "result": {"conclusion": "BLOCK", "items": []}
}
```

ロールバックでは、保存した旧 tag または digest を再指定します。新形式へ書き換えた入力は
`schema_version` を理解しない旧版で使えない場合があるため、移行前の入力も保存してください。
