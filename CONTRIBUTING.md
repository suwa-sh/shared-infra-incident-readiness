# Contributing

Issue または Pull Request を歓迎します。変更前に [CLAUDE.md](CLAUDE.md) の正本・overlay・
文書規約を確認してください。公開事案や法令に基づく定義変更には、一次資料と確認日を
`definitions/source-registry.yaml` へ追加します。

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[test]"
npm ci
.venv/bin/pytest
.venv/bin/python scripts/check_docs.py --cli
.venv/bin/python scripts/check_sources.py
npm run lint:mermaid
qlty check --all --no-fix --no-progress --no-upgrade-check
```

依存を変更したら Python 3.14 を対象に hash lock を再生成します。

```bash
uv pip compile pyproject.toml --output-file requirements.lock \
  --generate-hashes --python-version 3.14 \
  --no-emit-package shared-infra-incident-readiness
uv pip compile requirements-build.in --output-file requirements-build.lock \
  --generate-hashes --python-version 3.14
```

利用者に影響する変更は `CHANGELOG.md` に追記し、非互換変更は `MIGRATION.md` も更新します。
