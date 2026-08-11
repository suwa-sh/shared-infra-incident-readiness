# Changelog

このファイルは、利用者に影響する変更を記録します。形式は Keep a Changelog、
バージョンは Semantic Versioning に従います。

## Unreleased

## 1.0.0 - 2026-08-12

### Added

- 回答ファイルと事故記録に、明示的な `schema_version: 1` 契約を追加しました。
- JSON 出力に `contract_version`、入力・定義・overlay の digest を含む `provenance`、
  従来の結果を含む `result` の envelope を追加しました。
- 定義間参照、role、item、overlay の基本定義バージョンを検証します。
- 根拠資料の確認日と次回確認日を `definitions/source-registry.yaml` で管理します。
- Python 3.10 から 3.14 の CI、依存 lock、SBOM、build provenance を追加しました。

### Changed

- `validate-record` は通知義務と DPA の overlay を `extends` に従って振り分けます。
- JSON 出力の従来フィールドはトップレベルから `result` 配下へ移動しました。
- コンテナは digest 固定のベースイメージと hash 固定の依存を使い、非 root で動作します。

### Fixed

- 未知の role・item・条項参照、空の通知一覧、壊れた入力構造を見逃す問題を修正しました。
- `pending` 通知に `sent_at` を要求していたスキーマ条件を修正しました。
- リリースの再実行で既存の immutable tag とリリースノートを破壊しないようにしました。

## 0.3.0 - 2026-08-07

- `agentic-attacker` overlay、複数 overlay、定義一覧、CLI／コンテナの公開フローを追加しました。

[Unreleased]: https://github.com/suwa-sh/shared-infra-incident-readiness/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/suwa-sh/shared-infra-incident-readiness/compare/v0.3.0...v1.0.0
[0.3.0]: https://github.com/suwa-sh/shared-infra-incident-readiness/releases/tag/v0.3.0
