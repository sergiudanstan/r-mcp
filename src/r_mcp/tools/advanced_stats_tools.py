"""Advanced statistics — ANOVA, mixed models, bootstrap, outliers, normality."""

import json

from mcp.server.fastmcp import FastMCP, Context


def register_advanced_stats_tools(mcp: FastMCP) -> None:
    """Register advanced statistical analysis tools."""

    @mcp.tool()
    async def anova_test(
        ctx: Context,
        file_path: str,
        formula: str,
        type: int = 2,
        post_hoc: bool = True,
    ) -> str:
        """Run ANOVA (one-way or multi-way) with optional post-hoc tests.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            formula: R formula, e.g. "y ~ group" or "y ~ A * B".
            type: Sum of squares type — 1, 2 (default), or 3.
            post_hoc: Run Tukey HSD post-hoc test (default True).

        Returns:
            JSON with ANOVA table, effect sizes, and post-hoc comparisons.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            import os
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".tsv":
                read_cmd = f'df <- read.delim("{file_path}")'
            elif ext == ".rds":
                read_cmd = f'df <- readRDS("{file_path}")'
            else:
                read_cmd = f'df <- read.csv("{file_path}")'

            posthoc = ""
            if post_hoc:
                posthoc = (
                    'if (length(attr(terms(model), "term.labels")) == 1) {\n'
                    '    th <- TukeyHSD(model)\n'
                    '    result$post_hoc <- lapply(th, as.data.frame)\n'
                    '    result$post_hoc_text <- capture.output(th)\n'
                    '}\n'
                )

            code = (
                'library(jsonlite)\nlibrary(car)\n'
                f'{read_cmd}\n'
                f'model <- aov({formula}, data = df)\n'
                f'if ({type} > 1) {{\n'
                f'    at <- car::Anova(model, type = {type})\n'
                '    anova_df <- as.data.frame(at)\n'
                '} else {\n'
                '    at <- anova(model)\n'
                '    anova_df <- as.data.frame(at)\n'
                '}\n'
                'anova_df$term <- rownames(anova_df)\n'
                'result <- list(\n'
                f'    formula = "{formula}",\n'
                f'    ss_type = {type},\n'
                '    anova_table = anova_df,\n'
                '    summary_text = capture.output(summary(model))\n'
                ')\n'
                f'{posthoc}'
                'cat(toJSON(result, auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "ANOVA failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def mixed_effects_model(
        ctx: Context,
        file_path: str,
        formula: str,
    ) -> str:
        """Fit a linear mixed-effects model using lme4.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            formula: lme4 formula with random effects, e.g.
                     "y ~ x + (1|group)" or "y ~ x + (x|subject)".

        Returns:
            JSON with fixed effects, random effects variance, ICC,
            AIC/BIC, and model summary.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            import os
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".tsv":
                read_cmd = f'df <- read.delim("{file_path}")'
            elif ext == ".rds":
                read_cmd = f'df <- readRDS("{file_path}")'
            else:
                read_cmd = f'df <- read.csv("{file_path}")'

            code = (
                'library(jsonlite)\nlibrary(lme4)\n'
                f'{read_cmd}\n'
                f'model <- lmer({formula}, data = df)\n'
                's <- summary(model)\n'
                'fe <- as.data.frame(s$coefficients)\n'
                'fe$term <- rownames(fe)\n'
                'vc <- as.data.frame(VarCorr(model))\n'
                '# ICC\n'
                'vars <- as.data.frame(VarCorr(model))\n'
                'icc <- vars$vcov[1] / sum(vars$vcov)\n'
                'cat(toJSON(list(\n'
                f'    formula = "{formula}",\n'
                '    fixed_effects = fe,\n'
                '    random_effects_var = vc,\n'
                '    icc = round(icc, 4),\n'
                '    aic = AIC(model), bic = BIC(model),\n'
                '    n_obs = nobs(model),\n'
                '    n_groups = sapply(ranef(model), nrow),\n'
                '    summary_text = capture.output(s)\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Mixed model failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def bootstrap_ci(
        ctx: Context,
        code: str,
        n_boot: int = 2000,
        conf_level: float = 0.95,
    ) -> str:
        """Compute bootstrap confidence intervals for a statistic.

        The code must define: (1) a data object `x`, and (2) a function
        `stat_fn(data, indices)` that returns the statistic.

        Args:
            code: R code defining `x` (data) and `stat_fn(data, indices)`.
                  Example: 'x <- mtcars$mpg; stat_fn <- function(d, i) mean(d[i])'
            n_boot: Number of bootstrap replications (default 2000).
            conf_level: Confidence level (default 0.95).

        Returns:
            JSON with original estimate, bootstrap SE, bias, and CI bounds.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            wrapped = (
                'library(boot)\nlibrary(jsonlite)\n'
                f'{code}\n'
                f'b <- boot(x, stat_fn, R = {n_boot})\n'
                f'ci <- boot.ci(b, conf = {conf_level}, type = c("norm", "perc", "bca"))\n'
                'cat(toJSON(list(\n'
                '    original = b$t0,\n'
                '    bias = mean(b$t) - b$t0,\n'
                '    std_error = sd(b$t),\n'
                f'    conf_level = {conf_level},\n'
                f'    n_boot = {n_boot},\n'
                '    ci_normal = ci$normal[2:3],\n'
                '    ci_percentile = ci$percent[4:5],\n'
                '    ci_bca = if (!is.null(ci$bca)) ci$bca[4:5] else NULL\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=120)
            if rc != 0:
                return json.dumps({"error": stderr or "Bootstrap failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def normality_tests(
        ctx: Context,
        code: str,
        filename: str = "normality.png",
    ) -> str:
        """Run multiple normality tests and produce a Q-Q plot.

        The code must create a numeric vector named `x`.

        Args:
            code: R code that creates a numeric vector `x`.
            filename: Output Q-Q plot filename.

        Returns:
            JSON with Shapiro-Wilk, Anderson-Darling (if available),
            Jarque-Bera results, skewness, kurtosis, and Q-Q plot path.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)

            wrapped = (
                'library(jsonlite)\n'
                f'{code}\n'
                'x <- x[!is.na(x)]\n'
                '# Shapiro-Wilk (max 5000 obs)\n'
                'sw <- shapiro.test(head(x, 5000))\n'
                '# Basic moments\n'
                'n <- length(x); m <- mean(x); s <- sd(x)\n'
                'skew <- sum((x-m)^3) / (n * s^3)\n'
                'kurt <- sum((x-m)^4) / (n * s^4) - 3\n'
                '# Jarque-Bera\n'
                'jb_stat <- (n/6) * (skew^2 + kurt^2/4)\n'
                'jb_p <- 1 - pchisq(jb_stat, df = 2)\n'
                f'png("{out_path}", width = 1024, height = 500, res = 150)\n'
                'par(mfrow = c(1, 2))\n'
                'hist(x, breaks = "Sturges", col = "#457B9D", border = "white",\n'
                '    main = "Histogram", xlab = "x", probability = TRUE)\n'
                'curve(dnorm(x, m, s), add = TRUE, col = "#E63946", lwd = 2)\n'
                'qqnorm(x, pch = 19, col = "#457B9D", cex = 0.6,\n'
                '    main = "Q-Q Plot")\n'
                'qqline(x, col = "#E63946", lwd = 2)\n'
                'dev.off()\n'
                'cat(toJSON(list(\n'
                '    n = n,\n'
                '    shapiro_wilk = list(statistic = sw$statistic,\n'
                '        p_value = sw$p.value,\n'
                '        normal = sw$p.value > 0.05),\n'
                '    jarque_bera = list(statistic = jb_stat,\n'
                '        p_value = jb_p,\n'
                '        normal = jb_p > 0.05),\n'
                '    skewness = round(skew, 4),\n'
                '    kurtosis = round(kurt, 4),\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Normality tests failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def outlier_detection(
        ctx: Context,
        file_path: str,
        method: str = "iqr",
        columns: str = "",
        threshold: float = 1.5,
    ) -> str:
        """Detect outliers in numeric columns of a data file.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            method: Detection method — "iqr" (default, uses threshold * IQR),
                    "zscore" (threshold = z-score cutoff, default 3),
                    "mahalanobis" (multivariate, chi-squared threshold).
            columns: Comma-separated columns (empty = all numeric).
            threshold: Method-specific threshold (IQR: 1.5, z-score: 3).

        Returns:
            JSON with outlier indices, counts per column, and summary.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
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

            if method == "mahalanobis":
                detect_code = (
                    'complete <- na.omit(nums)\n'
                    'md <- mahalanobis(complete, colMeans(complete), cov(complete))\n'
                    f'cutoff <- qchisq({threshold}, df = ncol(complete))\n'
                    'outlier_idx <- which(md > cutoff)\n'
                    'result <- list(method = "mahalanobis",\n'
                    '    n_outliers = length(outlier_idx),\n'
                    '    outlier_rows = outlier_idx,\n'
                    '    cutoff = cutoff,\n'
                    '    max_distance = max(md))\n'
                )
            elif method == "zscore":
                detect_code = (
                    'result <- list(method = "zscore",\n'
                    f'    threshold = {threshold}, per_column = list())\n'
                    'total <- 0\n'
                    'for (col in names(nums)) {\n'
                    '    x <- nums[[col]]\n'
                    '    z <- abs(scale(x))\n'
                    f'    idx <- which(z > {threshold})\n'
                    '    total <- total + length(idx)\n'
                    '    result$per_column[[col]] <- list(\n'
                    '        n_outliers = length(idx), rows = idx)\n'
                    '}\n'
                    'result$total_outliers <- total\n'
                )
            else:
                detect_code = (
                    'result <- list(method = "iqr",\n'
                    f'    threshold = {threshold}, per_column = list())\n'
                    'total <- 0\n'
                    'for (col in names(nums)) {\n'
                    '    x <- nums[[col]]\n'
                    '    q <- quantile(x, c(0.25, 0.75), na.rm = TRUE)\n'
                    '    iqr <- q[2] - q[1]\n'
                    f'    lo <- q[1] - {threshold} * iqr\n'
                    f'    hi <- q[2] + {threshold} * iqr\n'
                    '    idx <- which(x < lo | x > hi)\n'
                    '    total <- total + length(idx)\n'
                    '    result$per_column[[col]] <- list(\n'
                    '        n_outliers = length(idx), rows = idx,\n'
                    '        lower_fence = lo, upper_fence = hi)\n'
                    '}\n'
                    'result$total_outliers <- total\n'
                )

            code = (
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'{col_filter}'
                f'{detect_code}'
                'result$n_rows <- nrow(df)\n'
                'cat(toJSON(result, auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Outlier detection failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def quantile_regression(
        ctx: Context,
        file_path: str,
        formula: str,
        taus: str = "0.25, 0.5, 0.75",
    ) -> str:
        """Fit quantile regression models at specified quantiles.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            formula: R formula, e.g. "y ~ x1 + x2".
            taus: Comma-separated quantile levels (default "0.25, 0.5, 0.75").

        Returns:
            JSON with coefficients at each quantile and summary.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            import os
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".tsv":
                read_cmd = f'df <- read.delim("{file_path}")'
            elif ext == ".rds":
                read_cmd = f'df <- readRDS("{file_path}")'
            else:
                read_cmd = f'df <- read.csv("{file_path}")'

            tau_r = f'c({taus})'
            code = (
                'library(quantreg)\nlibrary(jsonlite)\n'
                f'{read_cmd}\n'
                f'taus <- {tau_r}\n'
                'results <- lapply(taus, function(tau) {\n'
                f'    model <- rq({formula}, tau = tau, data = df)\n'
                '    s <- summary(model)\n'
                '    coefs <- as.data.frame(s$coefficients)\n'
                '    coefs$term <- rownames(coefs)\n'
                '    list(tau = tau, coefficients = coefs,\n'
                '         summary = capture.output(s))\n'
                '})\n'
                'cat(toJSON(list(\n'
                f'    formula = "{formula}",\n'
                '    quantiles = results\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Quantile regression failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def survival_analysis(
        ctx: Context,
        file_path: str,
        time_col: str,
        event_col: str,
        group_col: str = "",
        filename: str = "survival.png",
    ) -> str:
        """Fit Kaplan-Meier survival curves with optional log-rank test.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            time_col: Column name for time-to-event.
            event_col: Column name for event indicator (1 = event, 0 = censored).
            group_col: Optional grouping column for comparing curves.
            filename: Output plot filename.

        Returns:
            JSON with median survival, log-rank test (if grouped), and plot path.
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

            if group_col:
                formula = f'Surv({time_col}, {event_col}) ~ {group_col}'
            else:
                formula = f'Surv({time_col}, {event_col}) ~ 1'

            code = (
                'library(survival)\nlibrary(jsonlite)\n'
                f'{read_cmd}\n'
                f'fit <- survfit({formula}, data = df)\n'
                f'png("{out_path}", width = 1024, height = 600, res = 150)\n'
                'plot(fit, col = 1:10, lwd = 2, xlab = "Time",\n'
                '    ylab = "Survival Probability", main = "Kaplan-Meier Curve")\n'
            )
            if group_col:
                code += (
                    f'legend("topright", legend = levels(factor(df${group_col})),\n'
                    '    col = 1:10, lwd = 2)\n'
                )
            code += (
                'dev.off()\n'
                'result <- list(\n'
                '    n = fit$n,\n'
                '    events = sum(fit$n.event),\n'
                '    median_survival = summary(fit)$table[,"median"],\n'
                '    summary_text = capture.output(fit)\n'
                ')\n'
            )
            if group_col:
                code += (
                    f'lr <- survdiff({formula}, data = df)\n'
                    'result$logrank_chisq <- lr$chisq\n'
                    'result$logrank_p <- 1 - pchisq(lr$chisq, length(lr$n) - 1)\n'
                )
            code += (
                f'result$plot <- "{out_path}"\n'
                'cat(toJSON(result, auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Survival analysis failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})
