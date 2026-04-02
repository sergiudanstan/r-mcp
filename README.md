# R MCP Server

An [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that lets AI assistants execute R code, create visualizations, analyze data, and manage packages — all through a local Rscript CLI.

## Features — 62 Tools

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

### Time Series (4 tools)

| Tool | Description |
|------|-------------|
| `forecast_timeseries` | Fit ARIMA/ETS/TBATS/Holt-Winters and forecast with plot |
| `decompose_timeseries` | Decompose into trend, seasonal, and remainder (STL/classical) |
| `stationarity_test` | Unit root tests — ADF, KPSS, Phillips-Perron |
| `acf_pacf_plot` | Plot ACF and PACF side by side with significance bounds |

### Clustering (2 tools)

| Tool | Description |
|------|-------------|
| `kmeans_clustering` | K-means with elbow plot, silhouette score, PCA projection |
| `hierarchical_clustering` | Hierarchical clustering with dendrogram and cophenetic correlation |

### Advanced Statistics (7 tools)

| Tool | Description |
|------|-------------|
| `anova_test` | One-way and two-way ANOVA with post-hoc tests |
| `mixed_effects_model` | Fit linear mixed-effects models (lme4) |
| `bootstrap_ci` | Bootstrap confidence intervals for any statistic |
| `normality_tests` | Shapiro-Wilk, Anderson-Darling, Kolmogorov-Smirnov, Lilliefors |
| `outlier_detection` | Grubbs, Dixon, Rosner, IQR, and Z-score methods |
| `quantile_regression` | Fit quantile regression at specified quantiles |
| `survival_analysis` | Kaplan-Meier survival curves and Cox proportional hazards |

### Interactive & Publication Plots (5 tools)

| Tool | Description |
|------|-------------|
| `create_plotly` | Create interactive plotly visualizations saved as HTML |
| `create_publication_plot` | Publication-ready plots using ggpubr |
| `create_corrplot` | Correlation matrix visualization (corrplot package) |
| `create_paired_comparison_plot` | Group comparisons with statistical significance |
| `create_diagnostic_plots` | Regression diagnostic plots (residuals, Q-Q, Cook's distance) |

### Probability Distributions (5 tools)

| Tool | Description |
|------|-------------|
| `distribution_calculator` | Compute d/p/q/r for 16 distributions (normal, binomial, t, F, chi-sq, etc.) |
| `distribution_plot` | Histogram of random samples with theoretical density overlay |
| `random_sample` | Sample from any population with/without replacement |
| `qq_plot` | Q-Q plot to assess distributional fit with Shapiro-Wilk test |
| `simulate_clt` | Central Limit Theorem simulation for any distribution |

### Proportion & Contingency Tests (5 tools)

| Tool | Description |
|------|-------------|
| `proportion_test` | One-sample and two-sample proportion tests (prop.test) |
| `binomial_test` | Exact binomial test for small samples |
| `chi_squared_test` | Chi-squared test for goodness of fit, independence, homogeneity |
| `fisher_test` | Fisher's exact test on 2x2 contingency tables |
| `contingency_table` | Create contingency table with mosaic plot and chi-squared test |

### Regression & Post-hoc (6 tools)

| Tool | Description |
|------|-------------|
| `robust_regression` | Robust regression (MASS::rlm/lqs) resistant to outliers |
| `polynomial_regression` | Fit and compare polynomial models of different degrees |
| `predict_with_ci` | Predictions with confidence and prediction intervals |
| `tukey_hsd` | Tukey's HSD post-hoc pairwise comparisons after ANOVA |
| `kruskal_wallis_test` | Kruskal-Wallis nonparametric test for group differences |
| `power_analysis` | Compute sample size or power for t-test and proportion test |

### Exploratory Data Analysis (5 tools)

| Tool | Description |
|------|-------------|
| `pairs_plot` | Scatterplot matrix with correlations and histograms |
| `density_plot` | Kernel density estimation plot with multiple kernels |
| `ecdf_plot` | Empirical CDF plot with optional normal overlay |
| `stem_and_leaf` | Text-based stem-and-leaf display with five-number summary |
| `variance_test` | F-test, Bartlett's, and Fligner-Killeen variance equality tests |

### Utilities (5 tools)

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

### Probability distributions

```r
# Via the distribution_calculator tool
# Compute P(X <= 1.96) for standard normal
pnorm(1.96, mean=0, sd=1)

# Via the distribution_plot tool
# Visualize chi-squared(5) distribution with 1000 samples
```

### Hypothesis testing

```r
# Via the proportion_test tool
# Test if 42 out of 100 differs from 50%
prop.test(42, 100, p = 0.5)

# Via the hypothesis_test tool
# Two-sample t-test
t.test(x, y, alternative = "two.sided")
```

### Analyze a CSV

Use `get_data_summary` with a file path to get dimensions, column types, summary statistics, and a preview.

## License

MIT
