# Security Policy

`r-mcp` is a local MCP server that runs R for an AI assistant. It speaks MCP over stdio
only (no network listener, no accounts, no authentication of its own) and starts one
`Rscript --vanilla` process per tool call. **Its core function is executing code chosen by a
language model**, so the security boundary is the MCP client you connect it to, not this server.

## Supported versions

| Version | Supported |
|---|---|
| 0.2.x | Current |

Single maintainer; only the latest release receives fixes.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.** Report it privately:
**[Report a vulnerability](https://github.com/sergiudanstan/r-mcp/security/advisories/new)**
(Security -> Advisories -> Report a vulnerability).

| Stage | Target |
|---|---|
| Acknowledgement | within 3 business days |
| Triage | within 10 business days |
| Fix, or a documented decision not to fix | within 90 days |

These are best-effort targets from a single unpaid maintainer, not a contractual SLA.
There is no bug bounty; credit is offered in the advisory and changelog.

## Threat model

Tool arguments are untrusted: they are chosen by an LLM that may itself be steered by
prompt injection in data it reads. Concretely, this server gives whoever controls those
arguments:

- **Arbitrary code execution as your user.** `evaluate_r_code`, `run_r_file`, `run_r_test_file`
  and `write_data` run R code supplied by the caller, and most statistics and plotting tools
  paste their string arguments (file paths, formulas, column names, R snippets) straight into
  generated R code. R can call `system()`, read and write any file you can, and open network
  connections. There is no sandbox, container or allow-list; `--vanilla` only skips profile
  and environment files, it is not a security measure.
- **File-system reach.** Input paths (`file_path`) are used as given, absolute or relative to
  the working directory, so any file readable by your user can be read. Output file names are
  confined to `~/r-mcp-workspace/` by `resolve_path` (tested), but R code you run can write
  anywhere.
- **Network and package installs.** The server itself makes no network calls.
  `install_r_package` runs `install.packages` against a CRAN mirror URL that is itself a tool
  argument, so it can install code from any repository the caller names.
- **Resource use.** Each call is limited by a timeout argument (default 60 s) and captured
  output is truncated at 50,000 characters, but the timeout is itself caller-supplied and
  there is no memory or CPU limit.

Run it only with clients and models you trust with your account, ideally as a dedicated
low-privilege user or inside a container or VM, and keep the client's per-tool approval
prompts on for the execution tools.

## Scope

In scope:

- A way to write outside `~/r-mcp-workspace/` through the tools that are meant to be confined
  to it (output file names), or any bypass of `resolve_path`.
- Code execution or file access reachable through a tool that does not advertise it (for
  example a "statistics" tool that can be made to run a shell command).
- Anything in this repository's workflows that could publish a release not built from `main`.

Out of scope:

- That `evaluate_r_code` and the other execution tools run arbitrary R. That is their
  documented purpose; see the threat model.
- Vulnerabilities in R, CRAN packages, the MCP SDK or the client application (report upstream).
- Statistical correctness of results: file a normal issue.

## Supply chain

CI runs the test suite on Python 3.10 and 3.13 against a real `Rscript`, `ruff` (syntax and
undefined-name checks only; the legacy code has style findings under the default rules),
`pip-audit` on the project's dependencies and on the hash-pinned CI toolchain, CodeQL, and
`zizmor` on the workflows. Actions are pinned to full commit SHAs and kept current by
Dependabot. Releases attach a source archive and a CycloneDX SBOM, both with Sigstore build
provenance:

```
gh attestation verify r-mcp-v0.2.0.tar.gz --repo sergiudanstan/r-mcp
```
