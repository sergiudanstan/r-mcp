# Contributing

Contributions are welcome. This is a single-maintainer project, so please open an issue
before starting anything substantial.

**Security problems do not belong in issues.** Follow [SECURITY.md](SECURITY.md).

## Branches, pull requests and releases

- `main` is the only long-lived branch and is protected: changes land through a pull
  request with the required checks green, commits on `main` are signed, and force-pushes
  are refused. Pull requests are squash-merged; GitHub deletes the branch on merge.
- Branch names: `<type>/<topic>` (`feat/`, `fix/`, `docs/`, `chore/`, `release/`);
  agents use `agent/<name>/<topic>`.
- A release is a pull request that bumps `version` in `pyproject.toml` and moves
  `[Unreleased]` in [CHANGELOG.md](CHANGELOG.md) to a dated version. After it merges, a
  signed `vX.Y.Z` tag on that commit triggers `release.yml`, which refuses to run if the
  tag, the declared version and the changelog disagree. Tags are never moved or deleted.

## Running it locally

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q tests       # needs R (Rscript) on PATH; set REQUIRE_R=1 to fail instead of skip
python -m r_mcp                 # run the server over stdio
```

The real-R tests are skipped when `Rscript` is not installed; CI always installs it and sets `REQUIRE_R=1`.
