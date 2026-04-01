"""Proportion and contingency table tools — prop.test, binom.test, fisher.test, chisq.test."""

import json

from mcp.server.fastmcp import FastMCP, Context


def register_proportion_tools(mcp: FastMCP) -> None:
    """Register proportion test and contingency table tools."""

    @mcp.tool()
    async def proportion_test(
        ctx: Context,
        x: str,
        n: str,
        p: float = 0.5,
        alternative: str = "two.sided",
        conf_level: float = 0.95,
    ) -> str:
        """Run a proportion test (one-sample or two-sample) using prop.test.

        For one-sample: test if observed proportion differs from hypothesized p.
        For two-sample: test if two proportions are equal.

        Args:
            x: Number of successes — single value "42" or two-sample "c(45,56)".
            n: Number of trials — single "100" or two-sample "c(80,103)".
            p: Hypothesized proportion for one-sample test (default 0.5).
            alternative: "two.sided" (default), "less", or "greater".
            conf_level: Confidence level (default 0.95).

        Returns:
            JSON with test statistic, p-value, confidence interval, and estimates.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            code = (
                'library(jsonlite)\n'
                f'result <- prop.test({x}, {n}, p = {p},\n'
                f'    alternative = "{alternative}",\n'
                f'    conf.level = {conf_level})\n'
                'cat(toJSON(list(\n'
                '    method = result$method,\n'
                '    statistic = result$statistic,\n'
                '    p_value = result$p.value,\n'
                '    conf_int = result$conf.int,\n'
                f'    conf_level = {conf_level},\n'
                '    estimates = result$estimate,\n'
                f'    alternative = "{alternative}",\n'
                '    summary = capture.output(result)\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=15)
            if rc != 0:
                return json.dumps({"error": stderr or "prop.test failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def binomial_test(
        ctx: Context,
        x: int,
        n: int,
        p: float = 0.5,
        alternative: str = "two.sided",
    ) -> str:
        """Run an exact binomial test using binom.test.

        More accurate than prop.test for small sample sizes.

        Args:
            x: Number of successes.
            n: Number of trials.
            p: Hypothesized probability of success (default 0.5).
            alternative: "two.sided" (default), "less", or "greater".

        Returns:
            JSON with exact p-value, confidence interval, and estimate.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            code = (
                'library(jsonlite)\n'
                f'result <- binom.test({x}, {n}, p = {p},\n'
                f'    alternative = "{alternative}")\n'
                'cat(toJSON(list(\n'
                '    method = result$method,\n'
                '    p_value = result$p.value,\n'
                '    conf_int = result$conf.int,\n'
                '    estimate = result$estimate,\n'
                f'    hypothesized_p = {p},\n'
                '    summary = capture.output(result)\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=15)
            if rc != 0:
                return json.dumps({"error": stderr or "binom.test failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def chi_squared_test(
        ctx: Context,
        code: str,
        test_type: str = "independence",
    ) -> str:
        """Run a chi-squared test for goodness of fit, independence, or homogeneity.

        The code must create either:
        - For goodness of fit: a vector `observed` and optionally `expected_probs`.
        - For independence/homogeneity: a matrix or table named `tab`.

        Args:
            code: R code that creates the test data.
                  Goodness of fit: 'observed <- c(22,21,22,27,22,36)'
                  Independence: 'tab <- matrix(c(12813,647,359,42,65963,4000,2642,303), nrow=2, byrow=TRUE)'
                  From data: 'tab <- table(df$var1, df$var2)'
            test_type: "independence" (default), "goodness_of_fit", or "homogeneity".

        Returns:
            JSON with chi-squared statistic, df, p-value, expected counts,
            and residuals.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]

            if test_type == "goodness_of_fit":
                test_cmd = (
                    'probs <- if (exists("expected_probs")) expected_probs else NULL\n'
                    'result <- chisq.test(observed, p = probs)\n'
                )
            else:
                test_cmd = 'result <- chisq.test(tab)\n'

            wrapped = (
                'library(jsonlite)\n'
                f'{code}\n'
                f'{test_cmd}'
                'cat(toJSON(list(\n'
                '    method = result$method,\n'
                '    statistic = result$statistic,\n'
                '    df = result$parameter,\n'
                '    p_value = result$p.value,\n'
                '    expected = result$expected,\n'
                '    residuals = result$residuals,\n'
                '    summary = capture.output(result)\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=15)
            if rc != 0:
                return json.dumps({"error": stderr or "Chi-squared test failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def fisher_test(
        ctx: Context,
        code: str,
        alternative: str = "two.sided",
    ) -> str:
        """Run Fisher's exact test on a 2x2 contingency table.

        More accurate than chi-squared for small samples.

        Args:
            code: R code that creates a matrix or table named `tab`.
                  Example: 'tab <- matrix(c(10,5,3,12), nrow=2)'
            alternative: "two.sided" (default), "less", or "greater".

        Returns:
            JSON with p-value, odds ratio, and confidence interval.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            wrapped = (
                'library(jsonlite)\n'
                f'{code}\n'
                f'result <- fisher.test(tab, alternative = "{alternative}")\n'
                'cat(toJSON(list(\n'
                '    method = result$method,\n'
                '    p_value = result$p.value,\n'
                '    odds_ratio = result$estimate,\n'
                '    conf_int = result$conf.int,\n'
                '    summary = capture.output(result)\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=15)
            if rc != 0:
                return json.dumps({"error": stderr or "Fisher test failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def contingency_table(
        ctx: Context,
        file_path: str,
        row_var: str,
        col_var: str,
        filename: str = "contingency.png",
    ) -> str:
        """Create a contingency table with chi-squared test and mosaic plot.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            row_var: Column name for rows.
            col_var: Column name for columns.
            filename: Output mosaic plot filename.

        Returns:
            JSON with frequency table, proportions, chi-squared results,
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
                f'tab <- table(df${row_var}, df${col_var})\n'
                'chi <- chisq.test(tab)\n'
                f'png("{out_path}", width = 800, height = 600, res = 150)\n'
                f'mosaicplot(tab, main = "{row_var} vs {col_var}",\n'
                '    color = TRUE, shade = TRUE)\n'
                'dev.off()\n'
                'cat(toJSON(list(\n'
                '    frequencies = as.data.frame.matrix(tab),\n'
                '    row_proportions = as.data.frame.matrix(prop.table(tab, 1)),\n'
                '    col_proportions = as.data.frame.matrix(prop.table(tab, 2)),\n'
                '    chi_squared = chi$statistic,\n'
                '    df = chi$parameter,\n'
                '    p_value = chi$p.value,\n'
                f'    plot = "{out_path}"\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Contingency table failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})
