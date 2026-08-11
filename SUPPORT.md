# サポートポリシー

最新の公開済み minor 系列だけをサポートします。修正は原則として最新系列へ提供し、
古い系列への backport は行いません。利用者は tag または digest を固定し、更新時に
[MIGRATION.md](MIGRATION.md) と [CHANGELOG.md](CHANGELOG.md) を確認してください。

- 不具合・機能要望: [GitHub Issues](https://github.com/suwa-sh/shared-infra-incident-readiness/issues)
- 脆弱性: [SECURITY.md](SECURITY.md) の非公開窓口
- 法令・契約値: 最終判断は自組織の法務・セキュリティ責任者が行います。

定義の根拠は定期確認します。`definitions/source-registry.yaml` の `next_review_on` を過ぎると
CI が失敗します。ただし、SIIR は法的助言や事故対応サービスを提供するものではありません。
