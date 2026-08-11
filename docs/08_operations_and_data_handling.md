# 08. 安全に運用し、証跡を保管する

## TL;DR

SIIR は入力を外部送信しませんが、事故記録や責任表には機密情報が含まれます。入力を最小化し、
ローカルの読み取り専用環境で実行し、JSON 出力と `provenance` を組織の証跡管理規則に従って
暗号化・アクセス制御・期限付き保管してください。更新時は tag または digest を固定し、同じ入力で
差分を確認してから切り替えます。

## When to use this

- 実事故の記録を `validate-record` へ渡すとき
- 責任表や DPA の診断結果を監査証跡として保管するとき
- SIIR の版、定義、overlay を更新またはロールバックするとき
- AI エージェントや CI から SIIR を呼び出すとき

## Quick use

入力専用ディレクトリだけを読み取り専用で mount し、コンテナ自体も読み取り専用にします。

```bash
docker run --rm --read-only \
  --mount type=bind,src="$PWD/input",dst=/data,readonly \
  ghcr.io/suwa-sh/shared-infra-incident-readiness:v1.0.0 \
  validate-record /data/incident.json --level extended --format json \
  > result.json
```

`result.json` では、処理前に `contract_version` を検査します。判定は `result`、再現情報は
`provenance` にあります。ファイル名、定義版、SHA-256 digest は含まれますが、入力本文は
出力しません。

## Concept

### データ境界を決める

```mermaid
flowchart LR
  source["組織内の事故・契約データ"] --> minimize["必要項目だけ抽出・秘匿化"]
  minimize --> siir["SIIR<br/>ローカル・read-only"]
  siir --> evidence["JSON 結果 + provenance"]
  evidence --> store["暗号化・アクセス制御・保管期限"]
  store --> dispose["承認済み手順で削除"]
```

氏名、メールアドレス、認証情報、完全なログ、未公開の攻撃手順は、診断に必要でなければ入力しません。
サンプルを実データへ置き換えるときも、識別子は組織内の仮名へ変換します。AI エージェントへ渡す場合は、
利用するモデル、保持方針、学習利用、越境移転を組織が承認したときだけ実行します。

SIIR はローカルファイルを読み、標準出力へ結果を返します。CLI 自体はネットワーク送信しません。
ただし、コンテナ取得、CI、呼び出し元エージェント、ログ収集基盤は別のデータ境界です。
それぞれの権限と保持を別途確認してください。

### 証跡の責任を割り当てる

| 項目 | 最低限決めること |
|---|---|
| 所有者 | 結果を承認し、再診断を指示する責任者 |
| アクセス | incident team、法務、監査など必要最小限の閲覧者 |
| 保管 | 暗号化方式、保管場所、保持期限、legal hold の扱い |
| 再現 | SIIR tag/digest、入力 digest、overlay の順序、実行時刻 |
| 廃棄 | 期限到来時の削除方法と削除記録 |

`provenance` は再現に必要な技術情報を補助しますが、実行者、承認者、時刻、保管先は組織側で
記録します。出力 digest だけで入力の真正性や法的な証拠能力を保証するものではありません。

### 更新とロールバックを試す

新しい tag を staging で固定し、現在版と同じ入力を実行します。`contract_version`、exit code、
`result` の差分をレビューします。問題があれば、保存済みの旧 tag または immutable digest へ戻します。
`latest` は更新の起点にもロールバック先にも使いません。

定義の法令・事案根拠は [`source-registry.yaml`](../definitions/source-registry.yaml) で確認します。
`next_review_on` を過ぎた資料は CI が検出します。自組織の overlay と判断根拠にも、同じ粒度の
所有者、確認日、再確認日を持たせてください。

## References

- 入出力の互換性：[`COMPATIBILITY.md`](../COMPATIBILITY.md)
- バージョン移行：[`MIGRATION.md`](../MIGRATION.md)
- サポート範囲：[`SUPPORT.md`](../SUPPORT.md)
- 脆弱性報告：[`SECURITY.md`](../SECURITY.md)
- 出典レジストリ：[`definitions/source-registry.yaml`](../definitions/source-registry.yaml)
