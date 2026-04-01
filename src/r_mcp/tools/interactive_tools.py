"""Interactive and publication-ready visualization tools — plotly, ggpubr, corrplot."""

import json

from mcp.server.fastmcp import FastMCP, Context


def register_interactive_tools(mcp: FastMCP) -> None:
    """Register interactive and publication visualization tools."""

    @mcp.tool()
    async def create_plotly(
        ctx: Context,
        code: str,
        filename: str = "interactive.html",
    ) -> str:
        """Create an interactive plotly visualization saved as HTML.

        The code should produce a plotly object (via plot_ly() or
        ggplotly()). Assign the final plot to `p`.

        Args:
            code: R code that creates a plotly object named `p`.
                  Example: 'library(plotly); p <- plot_ly(mtcars, x=~wt, y=~mpg)'
            filename: Output HTML filename (saved in ~/r-mcp-workspace/).

        Returns:
            JSON with the absolute path to the saved HTML file.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            wrapped = (
                'library(plotly)\nlibrary(htmlwidgets)\n'
                f'{code}\n'
                f'saveWidget(p, "{out_path}", selfcontained = TRUE)\n'
                f'cat("Saved: {out_path}\\n")\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=60)
            if rc != 0 or not out_path.exists():
                return json.dumps({"error": stderr or "Plotly failed", "output": stdout})
            return json.dumps({
                "path": str(out_path),
                "message": f"Interactive plot saved to {out_path}",
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def create_publication_plot(
        ctx: Context,
        code: str,
        filename: str = "publication.png",
        width: int = 1200,
        height: int = 900,
    ) -> str:
        """Create publication-ready plots using ggpubr.

        ggpubr adds statistical comparisons, p-values, and journal-ready
        themes on top of ggplot2. The code should use ggpubr functions.
        Assign the final plot to `p`.

        Args:
            code: R code using ggpubr (ggboxplot, ggscatter, ggbarplot,
                  gghistogram, ggdensity, ggviolin, ggerrorplot, etc.).
            filename: Output filename.
            width: Image width in pixels (default 1200).
            height: Image height in pixels (default 900).

        Returns:
            JSON with path to saved PNG.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            w_in = round(width / 150, 2)
            h_in = round(height / 150, 2)

            wrapped = (
                'library(ggpubr)\n'
                f'{code}\n'
                f'ggsave("{out_path}", p, width = {w_in}, height = {h_in},\n'
                '       dpi = 150, bg = "white")\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=60)
            if rc != 0 or not out_path.exists():
                return json.dumps({"error": stderr or "ggpubr failed", "output": stdout})
            return json.dumps({
                "path": str(out_path),
                "message": f"Publication plot saved to {out_path}",
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def create_corrplot(
        ctx: Context,
        file_path: str,
        method: str = "circle",
        cor_method: str = "pearson",
        order: str = "hclust",
        columns: str = "",
        filename: str = "corrplot.png",
    ) -> str:
        """Create a correlation plot using the corrplot package.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            method: Visualization — "circle" (default), "square", "ellipse",
                    "number", "shade", "color", "pie".
            cor_method: "pearson", "spearman", or "kendall".
            order: Ordering — "hclust" (default), "AOE", "FPC", "alphabet", "original".
            columns: Comma-separated columns (empty = all numeric).
            filename: Output filename.

        Returns:
            JSON with path to saved corrplot PNG.
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
                'library(corrplot)\n'
                f'{read_cmd}\n'
                f'{col_filter}'
                f'cor_mat <- cor(nums, use = "pairwise.complete.obs", method = "{cor_method}")\n'
                f'png("{out_path}", width = 900, height = 900, res = 150)\n'
                f'corrplot(cor_mat, method = "{method}", order = "{order}",\n'
                '    tl.cex = 0.8, tl.col = "black",\n'
                '    col = colorRampPalette(c("#457B9D","white","#E63946"))(200))\n'
                'dev.off()\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0 or not out_path.exists():
                return json.dumps({"error": stderr or "corrplot failed", "output": stdout})
            return json.dumps({
                "path": str(out_path),
                "message": f"Corrplot saved to {out_path}",
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def create_paired_comparison_plot(
        ctx: Context,
        file_path: str,
        x: str,
        y: str,
        test: str = "t.test",
        plot_type: str = "boxplot",
        filename: str = "comparison.png",
    ) -> str:
        """Create a group comparison plot with statistical significance using ggpubr.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            x: Column name for grouping variable.
            y: Column name for numeric response variable.
            test: Statistical test — "t.test", "wilcox.test", "anova", "kruskal.test".
            plot_type: "boxplot", "violin", "bar", "dot".
            filename: Output filename.

        Returns:
            JSON with plot path and test results.
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

            plot_fn = {
                "boxplot": "ggboxplot",
                "violin": "ggviolin",
                "bar": "ggbarplot",
                "dot": "ggdotplot",
            }.get(plot_type, "ggboxplot")

            code = (
                'library(ggpubr)\nlibrary(rstatix)\nlibrary(jsonlite)\n'
                f'{read_cmd}\n'
                f'df${x} <- factor(df${x})\n'
                f'groups <- levels(df${x})\n'
                f'p <- {plot_fn}(df, x = "{x}", y = "{y}",\n'
                '    color = "' + x + '", add = "jitter",\n'
                '    palette = "jco") +\n'
                f'    stat_compare_means(method = "{test}") +\n'
                '    theme(legend.position = "none")\n'
                '# If exactly 2 groups, add pairwise\n'
                'if (length(groups) == 2) {\n'
                '    p <- p + stat_compare_means(\n'
                '        comparisons = list(groups),\n'
                f'        method = "{test}", label = "p.signif")\n'
                '}\n'
                f'ggsave("{out_path}", p, width = 7, height = 6,\n'
                '       dpi = 150, bg = "white")\n'
                '# Test results\n'
                f'test_res <- compare_means({y} ~ {x}, data = df,\n'
                f'    method = "{test}")\n'
                'cat(toJSON(list(\n'
                f'    plot = "{out_path}",\n'
                '    test_results = as.data.frame(test_res)\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Comparison plot failed", "output": stdout})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def create_diagnostic_plots(
        ctx: Context,
        file_path: str,
        formula: str,
        filename: str = "diagnostics.png",
    ) -> str:
        """Create regression diagnostic plots (residuals, Q-Q, scale-location, leverage).

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            formula: R formula for linear model, e.g. "y ~ x1 + x2".
            filename: Output filename.

        Returns:
            JSON with plot path and key diagnostic statistics.
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
                f'png("{out_path}", width = 1200, height = 1000, res = 150)\n'
                'par(mfrow = c(2, 2))\n'
                'plot(model)\n'
                'dev.off()\n'
                '# Diagnostic tests\n'
                'sw <- shapiro.test(residuals(model))\n'
                'cat(toJSON(list(\n'
                f'    plot = "{out_path}",\n'
                '    residual_normality_p = sw$p.value,\n'
                '    r_squared = summary(model)$r.squared,\n'
                '    durbin_watson = car::durbinWatsonTest(model)$dw,\n'
                '    vif = if (length(coef(model)) > 2)\n'
                '        as.list(car::vif(model)) else NULL\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Diagnostics failed", "output": stdout})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})
