"""Exploratory data analysis tools — pairs, density, ECDF, stem-and-leaf, variance tests."""

import json

from mcp.server.fastmcp import FastMCP, Context


def register_eda_tools(mcp: FastMCP) -> None:
    """Register exploratory data analysis tools with the MCP server."""

    @mcp.tool()
    async def pairs_plot(
        ctx: Context,
        file_path: str,
        columns: str = "",
        filename: str = "pairs_plot.png",
    ) -> str:
        """Create a scatterplot matrix (pairs plot) for multivariate EDA.

        Shows pairwise scatterplots, correlations, and distributions for
        all numeric columns. Uses base R pairs() with enhanced panels.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            columns: Comma-separated column names (empty = all numeric).
            filename: Output PNG filename.

        Returns:
            JSON with plot path, column names, and correlation matrix.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)
            import os
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".tsv":
                read_cmd = f'df <- read.delim("{file_path}")'
            elif ext == ".rds":
                read_cmd = f'df <- readRDS("{file_path}")'
            else:
                read_cmd = f'df <- read.csv("{file_path}")'

            col_filter = ""
            if columns.strip():
                cols = [c.strip() for c in columns.split(",")]
                col_r = ", ".join(f'"{c}"' for c in cols)
                col_filter = f'nums <- df[, c({col_r}), drop = FALSE]\n'
            else:
                col_filter = 'nums <- df[, sapply(df, is.numeric), drop = FALSE]\n'

            code = (
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'{col_filter}'
                'if (ncol(nums) < 2) stop("Need at least 2 numeric columns")\n'
                '# Enhanced panel functions\n'
                'panel.cor <- function(x, y, ...) {\n'
                '    usr <- par("usr"); on.exit(par(usr))\n'
                '    par(usr = c(0, 1, 0, 1))\n'
                '    r <- cor(x, y, use = "pairwise.complete.obs")\n'
                '    txt <- format(round(r, 2), nsmall = 2)\n'
                '    cex.cor <- max(0.8, min(2, 0.8/strwidth(txt)))\n'
                '    col <- if (r > 0) "#E63946" else "#457B9D"\n'
                '    text(0.5, 0.5, txt, cex = cex.cor * abs(r), col = col)\n'
                '}\n'
                'panel.hist <- function(x, ...) {\n'
                '    usr <- par("usr"); on.exit(par(usr))\n'
                '    par(usr = c(usr[1:2], 0, 1.5))\n'
                '    h <- hist(x, plot = FALSE)\n'
                '    breaks <- h$breaks; nB <- length(breaks)\n'
                '    y <- h$counts; y <- y/max(y)\n'
                '    rect(breaks[-nB], 0, breaks[-1], y, col = gray(0.85), border = "white")\n'
                '}\n'
                f'n <- ncol(nums)\n'
                f'png("{out_path}", width = max(600, 200*n), height = max(600, 200*n), res = 150)\n'
                'pairs(nums, lower.panel = panel.smooth,\n'
                '    upper.panel = panel.cor, diag.panel = panel.hist,\n'
                '    pch = 19, col = "#45789D80", cex = 0.5)\n'
                'dev.off()\n'
                'cor_mat <- cor(nums, use = "pairwise.complete.obs")\n'
                'cat(toJSON(list(\n'
                '    columns = colnames(nums),\n'
                '    n_obs = nrow(nums),\n'
                '    correlation = round(cor_mat, 4),\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Pairs plot failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def density_plot(
        ctx: Context,
        code: str,
        kernel: str = "gaussian",
        bw: str = "nrd0",
        filename: str = "density.png",
    ) -> str:
        """Create a kernel density estimation plot.

        The code must create one or more numeric vectors. If a single
        vector named `x` is created, one density curve is plotted. If
        a list named `groups` is created (e.g. list(A=x1, B=x2)),
        overlaid density curves with a legend are plotted.

        Args:
            code: R code that creates `x` (single vector) or
                  `groups` (named list of vectors).
                  Single: 'x <- mtcars$mpg'
                  Multiple: 'data(iris); groups <- split(iris$Sepal.Length, iris$Species)'
            kernel: Kernel type — "gaussian" (default), "epanechnikov",
                "rectangular", "triangular", "biweight", "cosine".
            bw: Bandwidth selector — "nrd0" (default), "nrd", "ucv",
                "bcv", "SJ", or a numeric value.
            filename: Output PNG filename.

        Returns:
            JSON with plot path, bandwidth used, and summary statistics.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)

            wrapped = (
                'library(jsonlite)\n'
                f'{code}\n'
                f'png("{out_path}", width = 900, height = 600, res = 150)\n'
                'if (exists("groups") && is.list(groups)) {\n'
                '    colors <- c("#E63946","#457B9D","#2A9D8F","#E9C46A","#264653",\n'
                '               "#F4A261","#6A4C93","#1982C4")\n'
                '    dens_list <- lapply(groups, function(g) {\n'
                f'        density(g, kernel = "{kernel}", bw = "{bw}")\n'
                '    })\n'
                '    xlim <- range(sapply(dens_list, function(d) range(d$x)))\n'
                '    ylim <- c(0, max(sapply(dens_list, function(d) max(d$y))))\n'
                '    plot(dens_list[[1]], xlim = xlim, ylim = ylim,\n'
                '        col = colors[1], lwd = 2, main = "Kernel Density",\n'
                '        xlab = "x")\n'
                '    for (i in seq_along(dens_list)[-1]) {\n'
                '        lines(dens_list[[i]], col = colors[i], lwd = 2)\n'
                '    }\n'
                '    legend("topright", names(groups),\n'
                '        col = colors[seq_along(groups)], lwd = 2)\n'
                '    stats <- lapply(groups, function(g) {\n'
                '        list(n = length(g), mean = mean(g), sd = sd(g),\n'
                '             median = median(g))\n'
                '    })\n'
                '    bw_used <- sapply(dens_list, function(d) d$bw)\n'
                '} else {\n'
                f'    d <- density(x, kernel = "{kernel}", bw = "{bw}")\n'
                '    plot(d, col = "#E63946", lwd = 2, main = "Kernel Density",\n'
                '        xlab = "x")\n'
                '    polygon(d, col = "#E6394620", border = "#E63946")\n'
                '    rug(x, col = "#45789D80")\n'
                '    stats <- list(n = length(x), mean = mean(x), sd = sd(x),\n'
                '                  median = median(x), min = min(x), max = max(x))\n'
                '    bw_used <- d$bw\n'
                '}\n'
                'dev.off()\n'
                'cat(toJSON(list(\n'
                f'    kernel = "{kernel}",\n'
                '    bandwidth = bw_used,\n'
                '    statistics = stats,\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Density plot failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def ecdf_plot(
        ctx: Context,
        code: str,
        filename: str = "ecdf.png",
    ) -> str:
        """Create an empirical cumulative distribution function (ECDF) plot.

        The code must create `x` (single vector) or `groups` (named list).
        Optionally overlays a theoretical normal CDF for comparison.

        Args:
            code: R code that creates `x` (single vector) or
                  `groups` (named list of vectors).
                  Single: 'x <- rnorm(100)'
                  Multiple: 'data(iris); groups <- split(iris$Petal.Length, iris$Species)'
            filename: Output PNG filename.

        Returns:
            JSON with plot path, Kolmogorov-Smirnov test against normality,
            and quantile summary.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)

            wrapped = (
                'library(jsonlite)\n'
                f'{code}\n'
                f'png("{out_path}", width = 900, height = 600, res = 150)\n'
                'if (exists("groups") && is.list(groups)) {\n'
                '    colors <- c("#E63946","#457B9D","#2A9D8F","#E9C46A","#264653")\n'
                '    plot(ecdf(groups[[1]]), col = colors[1], lwd = 2,\n'
                '        main = "Empirical CDF", xlab = "x", ylab = "F(x)",\n'
                '        xlim = range(unlist(groups)))\n'
                '    for (i in seq_along(groups)[-1]) {\n'
                '        lines(ecdf(groups[[i]]), col = colors[i], lwd = 2)\n'
                '    }\n'
                '    legend("bottomright", names(groups),\n'
                '        col = colors[seq_along(groups)], lwd = 2)\n'
                '    ks_results <- lapply(groups, function(g) {\n'
                '        ks <- tryCatch(ks.test(g, "pnorm", mean(g), sd(g)),\n'
                '                       error = function(e) NULL)\n'
                '        list(n = length(g), ks_p = if (!is.null(ks)) ks$p.value else NA,\n'
                '             quantiles = as.list(quantile(g)))\n'
                '    })\n'
                '} else {\n'
                '    plot(ecdf(x), col = "#E63946", lwd = 2,\n'
                '        main = "Empirical CDF", xlab = "x", ylab = "F(x)")\n'
                '    # Overlay normal CDF\n'
                '    curve(pnorm(x, mean(x), sd(x)), add = TRUE,\n'
                '        col = "#457B9D", lwd = 2, lty = 2)\n'
                '    legend("bottomright", c("ECDF", "Normal CDF"),\n'
                '        col = c("#E63946", "#457B9D"), lwd = 2, lty = c(1, 2))\n'
                '    ks <- tryCatch(ks.test(x, "pnorm", mean(x), sd(x)),\n'
                '                   error = function(e) NULL)\n'
                '    ks_results <- list(\n'
                '        n = length(x),\n'
                '        ks_statistic = if (!is.null(ks)) ks$statistic else NA,\n'
                '        ks_p = if (!is.null(ks)) ks$p.value else NA,\n'
                '        quantiles = as.list(quantile(x))\n'
                '    )\n'
                '}\n'
                'dev.off()\n'
                'cat(toJSON(list(\n'
                '    results = ks_results,\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "ECDF plot failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def stem_and_leaf(
        ctx: Context,
        code: str,
        scale: int = 1,
    ) -> str:
        """Create a stem-and-leaf display — a text-based distribution summary.

        The code must create a numeric vector named `x`.

        Args:
            code: R code that creates a numeric vector `x`.
                  Example: 'data(mtcars); x <- mtcars$mpg'
            scale: Controls stem length (default 1). Larger values
                   give more stems.

        Returns:
            JSON with the stem-and-leaf text, summary statistics, and
            five-number summary.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            wrapped = (
                'library(jsonlite)\n'
                f'{code}\n'
                f'stem_text <- capture.output(stem(x, scale = {scale}))\n'
                'fivenum <- fivenum(x)\n'
                'names(fivenum) <- c("min", "Q1", "median", "Q3", "max")\n'
                'cat(toJSON(list(\n'
                '    stem_and_leaf = stem_text,\n'
                '    n = length(x),\n'
                '    mean = mean(x),\n'
                '    sd = sd(x),\n'
                '    five_number = as.list(fivenum),\n'
                '    iqr = IQR(x),\n'
                '    mad = mad(x)\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=15)
            if rc != 0:
                return json.dumps({"error": stderr or "Stem-and-leaf failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def variance_test(
        ctx: Context,
        code: str,
        test: str = "var.test",
        alternative: str = "two.sided",
        conf_level: float = 0.95,
    ) -> str:
        """Test equality of variances between groups.

        Supports F-test (two groups), Bartlett's test (multiple groups,
        assumes normality), and Fligner-Killeen test (robust to
        non-normality).

        The code must create the data for the test:
        - For var.test: two vectors `x` and `y`.
        - For bartlett.test / fligner.test: a formula + data frame,
          or a list of vectors.

        Args:
            code: R code that creates the test data.
                  F-test: 'x <- rnorm(30, sd=2); y <- rnorm(30, sd=3)'
                  Bartlett: 'data(iris); vals <- iris$Sepal.Length; grp <- iris$Species'
                  List form: 'groups <- list(a=rnorm(20,sd=1), b=rnorm(20,sd=2), c=rnorm(20,sd=3))'
            test: "var.test" (F-test, default), "bartlett.test", or
                "fligner.test" (Fligner-Killeen, robust).
            alternative: For var.test only — "two.sided" (default),
                "less", or "greater".
            conf_level: Confidence level for var.test CI (default 0.95).

        Returns:
            JSON with test statistic, p-value, variance estimates,
            and confidence interval (for var.test).
        """
        try:
            client = ctx.request_context.lifespan_context["client"]

            if test == "var.test":
                test_cmd = (
                    f'result <- var.test(x, y, alternative = "{alternative}",\n'
                    f'    conf.level = {conf_level})\n'
                    'out <- list(\n'
                    '    method = result$method,\n'
                    '    statistic = result$statistic,\n'
                    '    df_num = result$parameter[1],\n'
                    '    df_denom = result$parameter[2],\n'
                    '    p_value = result$p.value,\n'
                    '    conf_int = as.numeric(result$conf.int),\n'
                    f'    conf_level = {conf_level},\n'
                    '    ratio_estimate = result$estimate,\n'
                    '    var_x = var(x), var_y = var(y),\n'
                    '    sd_x = sd(x), sd_y = sd(y),\n'
                    '    summary = capture.output(result)\n'
                    ')\n'
                )
            elif test == "bartlett.test":
                test_cmd = (
                    'if (exists("groups") && is.list(groups)) {\n'
                    '    result <- bartlett.test(groups)\n'
                    '    variances <- sapply(groups, var)\n'
                    '} else {\n'
                    '    result <- bartlett.test(vals ~ grp)\n'
                    '    variances <- tapply(vals, grp, var)\n'
                    '}\n'
                    'out <- list(\n'
                    '    method = result$method,\n'
                    '    statistic = result$statistic,\n'
                    '    df = result$parameter,\n'
                    '    p_value = result$p.value,\n'
                    '    group_variances = as.list(variances),\n'
                    '    summary = capture.output(result)\n'
                    ')\n'
                )
            else:  # fligner.test
                test_cmd = (
                    'if (exists("groups") && is.list(groups)) {\n'
                    '    result <- fligner.test(groups)\n'
                    '    variances <- sapply(groups, var)\n'
                    '} else {\n'
                    '    result <- fligner.test(vals ~ grp)\n'
                    '    variances <- tapply(vals, grp, var)\n'
                    '}\n'
                    'out <- list(\n'
                    '    method = result$method,\n'
                    '    statistic = result$statistic,\n'
                    '    df = result$parameter,\n'
                    '    p_value = result$p.value,\n'
                    '    group_variances = as.list(variances),\n'
                    '    summary = capture.output(result)\n'
                    ')\n'
                )

            wrapped = (
                'library(jsonlite)\n'
                f'{code}\n'
                f'{test_cmd}'
                'cat(toJSON(out, auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=15)
            if rc != 0:
                return json.dumps({"error": stderr or "Variance test failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})
