"""Regression tools — robust regression, polynomial fits, prediction intervals,
   TukeyHSD, Kruskal-Wallis, power analysis."""

import json

from mcp.server.fastmcp import FastMCP, Context


def register_regression_tools(mcp: FastMCP) -> None:
    """Register regression and post-hoc tools with the MCP server."""

    @mcp.tool()
    async def robust_regression(
        ctx: Context,
        file_path: str,
        formula: str,
        method: str = "rlm",
        filename: str = "robust_regression.png",
    ) -> str:
        """Fit a robust regression model resistant to outliers.

        Uses MASS::rlm (M-estimation) or MASS::lqs (least trimmed squares).

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            formula: R formula, e.g. "y ~ x1 + x2".
            method: "rlm" (default, M-estimation) or "lqs" (least trimmed squares).
            filename: Output comparison plot filename.

        Returns:
            JSON with coefficients, weights, and comparison with OLS.
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

            code = (
                'library(MASS)\nlibrary(jsonlite)\n'
                f'{read_cmd}\n'
                f'ols <- lm({formula}, data = df)\n'
                f'rob <- {method}({formula}, data = df)\n'
                f'# Plot comparison\n'
                f'resp <- all.vars({formula})[1]\n'
                f'pred <- all.vars({formula})[2]\n'
                f'png("{out_path}", width = 900, height = 600, res = 150)\n'
                'plot(df[[pred]], df[[resp]], pch = 19, col = "gray60",\n'
                '    xlab = pred, ylab = resp,\n'
                '    main = "OLS vs Robust Regression")\n'
                'abline(ols, col = "#457B9D", lwd = 2, lty = 2)\n'
                'abline(rob, col = "#E63946", lwd = 2)\n'
                'legend("topright", c("OLS", "Robust"),\n'
                '    col = c("#457B9D", "#E63946"), lwd = 2, lty = c(2, 1))\n'
                'dev.off()\n'
                'cat(toJSON(list(\n'
                f'    method = "{method}",\n'
                '    ols_coef = as.list(coef(ols)),\n'
                '    robust_coef = as.list(coef(rob)),\n'
                '    ols_r_squared = summary(ols)$r.squared,\n'
                '    robust_summary = capture.output(summary(rob)),\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Robust regression failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def polynomial_regression(
        ctx: Context,
        file_path: str,
        x_col: str,
        y_col: str,
        degrees: str = "1,2,3",
        filename: str = "polynomial_fit.png",
    ) -> str:
        """Fit polynomial regression models of various degrees and compare.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            x_col: Predictor column name.
            y_col: Response column name.
            degrees: Comma-separated polynomial degrees to fit (default "1,2,3").
            filename: Output comparison plot filename.

        Returns:
            JSON with coefficients, R-squared, AIC for each degree, and plot path.
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

            degs = [d.strip() for d in degrees.split(",")]
            degs_r = f"c({','.join(degs)})"

            code = (
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'x <- df${x_col}\ny <- df${y_col}\n'
                f'degrees <- {degs_r}\n'
                'models <- list()\nresults <- list()\n'
                'colors <- c("#457B9D","#E63946","#2A9D8F","#E9C46A","#264653")\n'
                f'png("{out_path}", width = 900, height = 600, res = 150)\n'
                f'plot(x, y, pch = 19, col = "gray60",\n'
                f'    xlab = "{x_col}", ylab = "{y_col}",\n'
                '    main = "Polynomial Regression Comparison")\n'
                'xseq <- seq(min(x), max(x), length.out = 200)\n'
                'for (i in seq_along(degrees)) {\n'
                '    d <- degrees[i]\n'
                '    if (d == 1) {\n'
                '        m <- lm(y ~ x)\n'
                '    } else {\n'
                '        m <- lm(y ~ poly(x, d, raw = TRUE))\n'
                '    }\n'
                '    models[[i]] <- m\n'
                '    yhat <- predict(m, data.frame(x = xseq))\n'
                '    lines(xseq, yhat, col = colors[i], lwd = 2, lty = i)\n'
                '    results[[i]] <- list(\n'
                '        degree = d,\n'
                '        r_squared = summary(m)$r.squared,\n'
                '        adj_r_squared = summary(m)$adj.r.squared,\n'
                '        aic = AIC(m),\n'
                '        coefficients = as.list(coef(m))\n'
                '    )\n'
                '}\n'
                'legend("topright",\n'
                '    paste0("degree ", degrees, ", R²=",\n'
                '        round(sapply(results, "[[", "r_squared"), 4)),\n'
                '    col = colors[seq_along(degrees)],\n'
                '    lwd = 2, lty = seq_along(degrees))\n'
                'dev.off()\n'
                'cat(toJSON(list(\n'
                '    models = results,\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Polynomial regression failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def predict_with_ci(
        ctx: Context,
        file_path: str,
        formula: str,
        new_data: str,
        conf_level: float = 0.95,
        filename: str = "prediction.png",
    ) -> str:
        """Make predictions from a linear model with confidence and prediction intervals.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            formula: R formula for the linear model, e.g. "y ~ x".
            new_data: R code for new data, e.g. "data.frame(x = c(50, 60, 70))".
            conf_level: Confidence level (default 0.95).
            filename: Output plot filename.

        Returns:
            JSON with predictions, confidence intervals, prediction intervals,
            and plot path.
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

            code = (
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'model <- lm({formula}, data = df)\n'
                f'newdf <- {new_data}\n'
                f'ci <- predict(model, newdf, interval = "confidence", level = {conf_level})\n'
                f'pi <- predict(model, newdf, interval = "prediction", level = {conf_level})\n'
                '# Plot with bands\n'
                f'resp <- all.vars({formula})[1]\n'
                f'pred <- all.vars({formula})[2]\n'
                'xord <- order(df[[pred]])\n'
                f'ci_all <- predict(model, data.frame({pred[0]}=sort(df[[pred]])),\n'
                f'    interval = "confidence", level = {conf_level})\n'
                f'pi_all <- predict(model, data.frame({pred[0]}=sort(df[[pred]])),\n'
                f'    interval = "prediction", level = {conf_level})\n'
            )
            # Simpler approach - avoid variable name issues
            code = (
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'model <- lm({formula}, data = df)\n'
                f'newdf <- {new_data}\n'
                f'ci <- predict(model, newdf, interval = "confidence", level = {conf_level})\n'
                f'pi <- predict(model, newdf, interval = "prediction", level = {conf_level})\n'
                f'png("{out_path}", width = 900, height = 600, res = 150)\n'
                f'resp <- all.vars({formula})[1]\n'
                f'pred_var <- all.vars({formula})[2]\n'
                'plot(df[[pred_var]], df[[resp]], pch = 19, col = "gray60",\n'
                '    xlab = pred_var, ylab = resp,\n'
                '    main = "Regression with Confidence & Prediction Bands")\n'
                'abline(model, col = "#E63946", lwd = 2)\n'
                '# Add confidence band\n'
                'xsort <- sort(df[[pred_var]])\n'
                'nd <- setNames(data.frame(xsort), pred_var)\n'
                f'ci_band <- predict(model, nd, interval = "confidence", level = {conf_level})\n'
                f'pi_band <- predict(model, nd, interval = "prediction", level = {conf_level})\n'
                'lines(xsort, ci_band[,"lwr"], col = "#457B9D", lty = 2, lwd = 1.5)\n'
                'lines(xsort, ci_band[,"upr"], col = "#457B9D", lty = 2, lwd = 1.5)\n'
                'lines(xsort, pi_band[,"lwr"], col = "#2A9D8F", lty = 3, lwd = 1.5)\n'
                'lines(xsort, pi_band[,"upr"], col = "#2A9D8F", lty = 3, lwd = 1.5)\n'
                '# Mark predictions\n'
                'points(newdf[[pred_var]], ci[,"fit"], pch = 17, col = "red", cex = 1.5)\n'
                'legend("topright", c("Fit", "95% CI", "95% PI", "Predictions"),\n'
                '    col = c("#E63946","#457B9D","#2A9D8F","red"),\n'
                '    lty = c(1,2,3,NA), pch = c(NA,NA,NA,17), lwd = c(2,1.5,1.5,NA))\n'
                'dev.off()\n'
                'cat(toJSON(list(\n'
                '    predictions = as.data.frame(ci),\n'
                '    prediction_intervals = as.data.frame(pi),\n'
                '    model_summary = capture.output(summary(model)),\n'
                f'    conf_level = {conf_level},\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Prediction failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def tukey_hsd(
        ctx: Context,
        file_path: str,
        formula: str,
        filename: str = "tukey_hsd.png",
    ) -> str:
        """Perform Tukey's Honest Significant Difference post-hoc test after ANOVA.

        Compares all pairs of group means.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            formula: R formula, e.g. "score ~ group".
            filename: Output plot filename.

        Returns:
            JSON with pairwise comparisons, adjusted p-values, and plot.
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

            code = (
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'# Make grouping variable a factor\n'
                f'grp <- all.vars({formula})[2]\n'
                'df[[grp]] <- factor(df[[grp]])\n'
                f'aov_model <- aov({formula}, data = df)\n'
                'tukey <- TukeyHSD(aov_model)\n'
                f'png("{out_path}", width = 900, height = 600, res = 150)\n'
                'par(mar = c(5, 10, 4, 2))\n'
                'plot(tukey, las = 1)\n'
                'dev.off()\n'
                'results <- tukey[[1]]\n'
                'cat(toJSON(list(\n'
                '    anova_p = summary(aov_model)[[1]]$"Pr(>F)"[1],\n'
                '    comparisons = as.data.frame(results),\n'
                '    comparison_names = rownames(results),\n'
                '    significant = rownames(results)[results[,"p adj"] < 0.05],\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "TukeyHSD failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def kruskal_wallis_test(
        ctx: Context,
        file_path: str,
        formula: str,
    ) -> str:
        """Run a Kruskal-Wallis rank sum test — nonparametric alternative to one-way ANOVA.

        Tests whether samples come from the same distribution.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            formula: R formula, e.g. "value ~ group".

        Returns:
            JSON with test statistic, df, p-value, and group medians.
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
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'resp <- all.vars({formula})[1]\n'
                f'grp <- all.vars({formula})[2]\n'
                'df[[grp]] <- factor(df[[grp]])\n'
                f'result <- kruskal.test({formula}, data = df)\n'
                'medians <- tapply(df[[resp]], df[[grp]], median)\n'
                'cat(toJSON(list(\n'
                '    method = result$method,\n'
                '    statistic = result$statistic,\n'
                '    df = result$parameter,\n'
                '    p_value = result$p.value,\n'
                '    group_medians = as.list(medians),\n'
                '    group_sizes = as.list(table(df[[grp]])),\n'
                '    summary = capture.output(result)\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=15)
            if rc != 0:
                return json.dumps({"error": stderr or "Kruskal-Wallis failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def power_analysis(
        ctx: Context,
        test: str = "t.test",
        n: str = "",
        delta: float = 0.5,
        sd: float = 1.0,
        sig_level: float = 0.05,
        power: float = 0.8,
        alternative: str = "two.sided",
    ) -> str:
        """Compute statistical power or required sample size.

        Leave one of n or power empty to solve for it.

        Args:
            test: "t.test" (default) or "prop.test".
            n: Sample size per group (leave empty to solve for n).
            delta: Effect size — difference in means for t.test,
                   difference in proportions for prop.test.
            sd: Standard deviation (for t.test only, default 1.0).
            sig_level: Significance level (default 0.05).
            power: Desired power (default 0.8, leave empty to solve for power).
            alternative: "two.sided" (default), "one.sided".

        Returns:
            JSON with computed n or power and a power curve.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]

            if test == "t.test":
                n_arg = f"n = {n}" if n else "n = NULL"
                p_arg = f"power = {power}" if not n else f"power = {power}"
                if not n:
                    p_arg = f"power = {power}"
                else:
                    p_arg = "power = NULL"

                code = (
                    'library(jsonlite)\n'
                    f'result <- power.t.test(\n'
                    f'    {n_arg},\n'
                    f'    delta = {delta},\n'
                    f'    sd = {sd},\n'
                    f'    sig.level = {sig_level},\n'
                    f'    {p_arg},\n'
                    f'    alternative = "{alternative}",\n'
                    '    type = "two.sample")\n'
                    'cat(toJSON(list(\n'
                    '    test = "t.test",\n'
                    '    n = result$n,\n'
                    '    delta = result$delta,\n'
                    '    sd = result$sd,\n'
                    '    sig_level = result$sig.level,\n'
                    '    power = result$power,\n'
                    f'    alternative = "{alternative}",\n'
                    '    summary = capture.output(result)\n'
                    '), auto_unbox = TRUE))\n'
                )
            else:
                n_arg = f"n = {n}" if n else "n = NULL"
                p_arg = f"power = {power}" if not n else "power = NULL"
                p1 = 0.5
                p2 = p1 + delta

                code = (
                    'library(jsonlite)\n'
                    f'result <- power.prop.test(\n'
                    f'    {n_arg},\n'
                    f'    p1 = {p1}, p2 = {p2},\n'
                    f'    sig.level = {sig_level},\n'
                    f'    {p_arg},\n'
                    f'    alternative = "{alternative}")\n'
                    'cat(toJSON(list(\n'
                    '    test = "prop.test",\n'
                    '    n = result$n,\n'
                    '    p1 = result$p1, p2 = result$p2,\n'
                    '    sig_level = result$sig.level,\n'
                    '    power = result$power,\n'
                    '    summary = capture.output(result)\n'
                    '), auto_unbox = TRUE))\n'
                )

            rc, stdout, stderr = await client.run_code(code, timeout=15)
            if rc != 0:
                return json.dumps({"error": stderr or "Power analysis failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})
