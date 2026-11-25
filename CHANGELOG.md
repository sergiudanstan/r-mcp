# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Migrated to the MCP Python SDK 2.x: `FastMCP` is now `MCPServer`
  (`mcp.server.mcpserver`). The dependency is `mcp>=2,<3`; SDK 1.x is no longer supported.

## [0.2.0] - 2026-11-25

`r-mcp` is an MCP server that lets an AI assistant run R through the local `Rscript` CLI:
62 tools for code execution, plotting, statistics, data wrangling, time series, clustering,
distributions and exploratory analysis. It speaks MCP over stdio.

### Added
- Test suite (`tests/`) covering workspace path confinement, output truncation, the tool
  registry (62 tools) and real `Rscript` runs (output, R errors, timeout, script files).
- CI (tests on Python 3.10 and 3.13 with R installed, ruff, `pip-audit`, `zizmor`), CodeQL,
  OpenSSF Scorecard and a tag-triggered release workflow with CycloneDX SBOM and build
  provenance; Dependabot for actions and pip.
- `SECURITY.md` (threat model for a code-executing server), `CONTRIBUTING.md` and this changelog.

### Fixed
- `predict_with_ci` always failed with `name 'pred' is not defined`: a leftover, unused
  first draft of the generated R code was evaluated before the working one.
- `RClient.resolve_path` accepted a sibling directory sharing the workspace's name prefix
  (`~/r-mcp-workspace-evil`); it now uses a real path-containment check.
- Dependency: `pyproject.toml` declared `fastmcp>=2.0` but the code imports
  `mcp.server.fastmcp`, which is gone in `mcp` 2.x (pulled in by current `fastmcp`), so a fresh
  install failed to import. It now declares `mcp>=1.28,<2`, as `openscad-mcp` does.

[Unreleased]: https://github.com/sergiudanstan/r-mcp/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/sergiudanstan/r-mcp/releases/tag/v0.2.0
