# R MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that lets AI assistants execute R code, create visualizations, analyze data, and manage packages — all through a local Rscript CLI.

## Features

### Execution (3 tools)

| Tool | Description |
|------|-------------|
| `evaluate_r_code` | Execute inline R code and return console output |
| `run_r_file` | Run an `.R` script file |
| `run_r_test_file` | Run testthat tests and report pass/fail |

### Visualization (5 tools)

| Tool | Description |
|------|-------------|
| `create_r_plot` | Execute base R plotting code and save as PNG |
| `create_ggplot` | Create ggplot2 plots with auto-theme and save as PNG |
| `create_correlation_heatmap` | Generate a correlation heatmap from a data file |
| `create_multi_plot` | Arrange multiple ggplots into a multi-panel figure |
| `render_rmarkdown` | Render `.Rmd` files to HTML or PDF |

### Statistical Analysis (5 tools)

| Tool | Description |
|------|-------------|
| `fit_linear_model` | Fit lm/glm and return coefficients, R-squared, p-values |
| `correlation_matrix` | Compute correlation matrix with p-values |
| `hypothesis_test` | Run t-test, Wilcoxon, chi-squared, Shapiro-Wilk, etc. |
| `descriptive_stats` | Per-column mean, sd, quartiles, skewness, kurtosis |
| `pca_analysis` | Principal Component Analysis with loadings and variance |

### Data Wrangling (5 tools)

| Tool | Description |
|------|-------------|
| `read_data` | Read CSV, TSV, Excel, JSON, Parquet, or RDS files |
| `write_data` | Execute R code and save results to CSV/TSV/RDS/JSON |
| `reshape_data` | Pivot data between wide and long formats (tidyr) |
| `merge_datasets` | Join two data files (inner, left, right, full) |
| `generate_sample_data` | Load built-in R datasets (mtcars, iris, etc.) as CSV |

### Analysis & Utilities (4 tools)

| Tool | Description |
|------|-------------|
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
