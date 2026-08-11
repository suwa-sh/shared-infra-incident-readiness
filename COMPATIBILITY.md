# 互換性ポリシー

SIIR は Semantic Versioning に従います。CLI の引数、exit code、入力 schema、JSON 出力契約、
定義 schema、overlay 互換性を公開インターフェースとして扱います。

| 変更 | バージョン方針 |
|---|---|
| 誤判定を直す検証強化、文言修正 | patch。ただし新たに拒否される入力は changelog に記載します。 |
| 後方互換なコマンド・定義項目の追加 | minor |
| 必須入力、JSON の場所、exit code、定義 schema の非互換変更 | major |

入力はトップレベルの `schema_version`、JSON 出力は `contract_version` を検査してください。
未対応の値を受け取った consumer は処理を止め、対応版へ更新します。overlay は
`compatible_base_version` を宣言し、基本定義の `version` と一致しなければ適用できません。

サポート対象は [SUPPORT.md](SUPPORT.md)、変更手順は [MIGRATION.md](MIGRATION.md) を参照してください。
