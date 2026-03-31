# R MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that lets AI assistants execute R code, create visualizations, analyze data, and manage packages — all through a local Rscript CLI.

## Features

| Tool | Description |
|------|-------------|
| `evaluate_r_code` | Execute inline R code and return console output |
| `run_r_file` | Run an `.R` script file |
| `run_r_test_file` | Run testthat tests and report pass/fail |
| `create_r_plot` | Execute plotting code and save as PNG |
| `render_rmarkdown` | Render `.Rmd` files to HTML or PDF |
| `check_r_code` | Static analysis via lintr |
| `get_data_summary` | Load CSV/TSV/RDS and return summary stats |
| `detect_r_packages` | List all installed R packages |
| `get_r_version` | Return R version and session info |
| `install_r_package` | Install a CRAN package |

## Prerequisites

- **R** (>= 4.0) with `Rscript` on your PATH
- **Python** (>= 3.10)

Install R from [CRAN](https://cran.r-project.org/) or via Homebrew:

```bash
brew install r
```

## Installation

```bash
git clone https://github.com/sergiudanstan/r-mcp.git
cd r-mcp
pip install -e .
```

## Usage

### With Claude Code

Add to your Claude Code MCP settings (`~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "r": {
      "command": "python",
      "args": ["-m", "r_mcp"],
      "cwd": "/path/to/r-mcp"
    }
  }
}
```

### Standalone

```bash
python -m r_mcp
```

The server communicates over stdio using the MCP protocol.

## How It Works

The server wraps the `Rscript --vanilla` CLI. Each tool call spawns a fresh R session, executes the code, and returns structured JSON results. Code is wrapped in `tryCatch` for clean error reporting.

- **Workspace**: Output files (plots, rendered docs) are saved to `~/r-mcp-workspace/`
- **Timeout**: Default 60s per execution (configurable per call)
- **Safety**: Path traversal prevention on file outputs; output truncation at 50K chars

## Examples

### Run R code

```r
# Via the evaluate_r_code tool
x <- rnorm(100)
cat("Mean:", mean(x), "\nSD:", sd(x), "\n")
```

### Create a plot

```r
# Via the create_r_plot tool
library(ggplot2)
df <- data.frame(x = rnorm(200), y = rnorm(200))
ggplot(df, aes(x, y)) + geom_point(alpha = 0.5) + theme_minimal()
```

### Analyze a CSV

Use `get_data_summary` with a file path to get dimensions, column types, summary statistics, and a preview.

## License

MIT
