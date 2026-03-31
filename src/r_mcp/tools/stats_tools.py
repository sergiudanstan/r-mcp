"""Statistical analysis tools — regression, correlation, hypothesis tests, PCA."""

import json

from mcp.server.fastmcp import FastMCP, Context


def register_stats_tools(mcp: FastMCP) -> None:
    """Register statistical analysis tools with the MCP server."""

    @mcp.tool()
    async def fit_linear_model(
        ctx: Context,
        file_path: str,
        formula: str,
        family: str = "gaussian",
    ) -> str:
        """Fit a linear or generalized linear model and return the summary.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            formula: R formula string, e.g. "y ~ x1 + x2".
            family: GLM family — "gaussian" (default, = lm), "binomial",
                    "poisson", "Gamma", "inverse.gaussian".

        Returns:
            JSON with coefficients, R-squared, p-values, AIC, and residual stats.
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

            if family == "gaussian":
                fit_cmd = f'model <- lm({formula}, data = df)'
            else:
                fit_cmd = f'model <- glm({formula}, data = df, family = {family})'

            code = (
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'{fit_cmd}\n'
                's <- summary(model)\n'
                'coefs <- as.data.frame(s$coefficients)\n'
                'coefs$term <- rownames(coefs)\n'
                'result <- list(\n'
                '    formula = deparse(formula(model)),\n'
                '    family = "' + family + '",\n'
                '    coefficients = coefs,\n'
                '    aic = AIC(model),\n'
                '    bic = BIC(model),\n'
                '    residual_summary = as.list(summary(residuals(model))),\n'
                '    n_obs = nobs(model),\n'
                '    summary_text = capture.output(s)\n'
                ')\n'
                'if (!is.null(s$r.squared)) {\n'
                '    result$r_squared <- s$r.squared\n'
                '    result$adj_r_squared <- s$adj.r.squared\n'
                '    result$f_statistic <- s$fstatistic[1]\n'
                '}\n'
                'cat(toJSON(result, auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Model fitting failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def correlation_matrix(
        ctx: Context,
        file_path: str,
        method: str = "pearson",
        columns: str = "",
    ) -> str:
        """Compute a correlation matrix for numeric columns in a data file.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            method: Correlation method — "pearson" (default), "spearman", or "kendall".
            columns: Comma-separated column names to include (empty = all numeric).

        Returns:
            JSON with the correlation matrix, p-values, and column names.
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
                col_filter = f'df <- df[, c({col_r}), drop = FALSE]\n'

            code = (
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'{col_filter}'
                'nums <- df[, sapply(df, is.numeric), drop = FALSE]\n'
                'if (ncol(nums) < 2) stop("Need at least 2 numeric columns")\n'
                f'cor_mat <- cor(nums, use = "pairwise.complete.obs", method = "{method}")\n'
                '# P-values\n'
                'n <- ncol(nums)\n'
                'pmat <- matrix(NA, n, n)\n'
                'for (i in 1:(n-1)) {\n'
                '    for (j in (i+1):n) {\n'
                f'        test <- cor.test(nums[[i]], nums[[j]], method = "{method}")\n'
                '        pmat[i,j] <- test$p.value\n'
                '        pmat[j,i] <- test$p.value\n'
                '    }\n'
                '}\n'
                'colnames(pmat) <- rownames(pmat) <- colnames(cor_mat)\n'
                'cat(toJSON(list(\n'
                f'    method = "{method}",\n'
                '    columns = colnames(cor_mat),\n'
                '    correlation = cor_mat,\n'
                '    p_values = pmat,\n'
                '    n_obs = nrow(nums)\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Correlation failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def hypothesis_test(
        ctx: Context,
        test_type: str,
        code: str,
    ) -> str:
        """Run a statistical hypothesis test and return structured results.

        Args:
            test_type: Type of test — "t.test", "wilcox.test", "chisq.test",
                       "shapiro.test", "ks.test", "var.test", "fisher.test",
                       "prop.test", "aov" (ANOVA).
            code: R code that defines the data and calls the test.
                  Must assign the result to a variable called `result`.
                  Example: "x <- c(1,2,3,4); y <- c(2,3,4,6); result <- t.test(x, y)"

        Returns:
            JSON with test name, statistic, p-value, confidence interval,
            and method description.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            wrapped = (
                'library(jsonlite)\n'
                f'{code}\n'
                'out <- list(\n'
                '    method = result$method,\n'
                '    statistic = as.numeric(result$statistic),\n'
                '    p_value = result$p.value,\n'
                '    alternative = result$alternative\n'
                ')\n'
                'if (!is.null(result$conf.int)) out$conf_int <- as.numeric(result$conf.int)\n'
                'if (!is.null(result$estimate)) out$estimate <- as.numeric(result$estimate)\n'
                'if (!is.null(result$parameter)) out$df <- as.numeric(result$parameter)\n'
                'out$full_output <- capture.output(print(result))\n'
                'cat(toJSON(out, auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Test failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def descriptive_stats(
        ctx: Context,
        file_path: str,
        columns: str = "",
    ) -> str:
        """Compute detailed descriptive statistics for a data file.

        Returns mean, median, sd, min, max, quartiles, skewness, kurtosis,
        missing count, and unique count for each numeric column.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            columns: Comma-separated column names (empty = all columns).

        Returns:
            JSON with per-column statistics.
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
                col_filter = f'df <- df[, c({col_r}), drop = FALSE]\n'

            code = (
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'{col_filter}'
                'stats_list <- lapply(names(df), function(col) {\n'
                '    x <- df[[col]]\n'
                '    info <- list(column = col, class = class(x)[1],\n'
                '                 n = length(x), n_missing = sum(is.na(x)),\n'
                '                 n_unique = length(unique(x)))\n'
                '    if (is.numeric(x)) {\n'
                '        x <- x[!is.na(x)]\n'
                '        q <- quantile(x, probs = c(0.25, 0.5, 0.75))\n'
                '        info$mean <- mean(x)\n'
                '        info$median <- median(x)\n'
                '        info$sd <- sd(x)\n'
                '        info$min <- min(x)\n'
                '        info$max <- max(x)\n'
                '        info$q1 <- q[1]; info$q3 <- q[3]\n'
                '        info$iqr <- IQR(x)\n'
                '        n <- length(x); m <- mean(x); s <- sd(x)\n'
                '        info$skewness <- sum((x-m)^3) / (n * s^3)\n'
                '        info$kurtosis <- sum((x-m)^4) / (n * s^4) - 3\n'
                '    } else if (is.character(x) || is.factor(x)) {\n'
                '        tb <- sort(table(x), decreasing = TRUE)\n'
                '        info$top_values <- head(as.list(tb), 5)\n'
                '    }\n'
                '    info\n'
                '})\n'
                'cat(toJSON(list(n_rows = nrow(df), n_cols = ncol(df),\n'
                '                columns = stats_list),\n'
                '           auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Stats computation failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def pca_analysis(
        ctx: Context,
        file_path: str,
        n_components: int = 5,
        scale: bool = True,
        columns: str = "",
    ) -> str:
        """Run Principal Component Analysis on numeric columns of a data file.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            n_components: Max number of principal components to report (default 5).
            scale: Whether to scale variables to unit variance (default True).
            columns: Comma-separated column names (empty = all numeric).

        Returns:
            JSON with eigenvalues, variance explained, and loadings.
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
                col_filter = f'df <- df[, c({col_r}), drop = FALSE]\n'

            scale_r = "TRUE" if scale else "FALSE"
            code = (
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'{col_filter}'
                'nums <- df[, sapply(df, is.numeric), drop = FALSE]\n'
                'nums <- na.omit(nums)\n'
                f'pca <- prcomp(nums, center = TRUE, scale. = {scale_r})\n'
                's <- summary(pca)\n'
                f'k <- min({n_components}, ncol(nums))\n'
                'loadings <- as.data.frame(pca$rotation[, 1:k])\n'
                'loadings$variable <- rownames(loadings)\n'
                'cat(toJSON(list(\n'
                '    n_obs = nrow(nums),\n'
                '    n_vars = ncol(nums),\n'
                '    sdev = pca$sdev[1:k],\n'
                '    variance_explained = s$importance[2, 1:k],\n'
                '    cumulative_variance = s$importance[3, 1:k],\n'
                '    loadings = loadings,\n'
                '    summary_text = capture.output(s)\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "PCA failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})
