"""ggplot2 visualization tools — high-level plotting with grammar of graphics."""

import json

from mcp.server.fastmcp import FastMCP, Context


def register_ggplot_tools(mcp: FastMCP) -> None:
    """Register ggplot2-based visualization tools with the MCP server."""

    @mcp.tool()
    async def create_ggplot(
        ctx: Context,
        code: str,
        filename: str = "ggplot.png",
        width: int = 1024,
        height: int = 768,
        theme: str = "minimal",
    ) -> str:
        """Create a plot using ggplot2 and save as PNG.

        The code should build a ggplot object. The theme and ggsave are
        applied automatically — do NOT call ggsave() in your code.
        The last expression must be the ggplot object (or assign to `p`).

        Args:
            code: R code using ggplot2. The final expression should be a ggplot.
            filename: Output filename (saved in ~/r-mcp-workspace/).
            width: Image width in pixels (default 1024).
            height: Image height in pixels (default 768).
            theme: ggplot2 theme — "minimal", "classic", "bw", "light",
                   "dark", "void", "gray" (default "minimal").

        Returns:
            JSON with the absolute path to the saved PNG.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            w_in = round(width / 150, 2)
            h_in = round(height / 150, 2)

            wrapped = (
                'library(ggplot2)\n'
                f'{code}\n'
                '# Capture the last ggplot object\n'
                'if (exists("p") && inherits(p, "gg")) {\n'
                '    plt <- p\n'
                '} else {\n'
                '    plt <- last_plot()\n'
                '}\n'
                f'plt <- plt + theme_{theme}()\n'
                f'ggsave("{out_path}", plt, width = {w_in}, height = {h_in},\n'
                '       dpi = 150, bg = "white")\n'
                f'cat("Saved: {out_path}\\n")\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=60)
            if rc != 0 or not out_path.exists():
                return json.dumps({
                    "error": stderr or "ggplot generation failed",
                    "output": stdout,
                })
            return json.dumps({
                "path": str(out_path),
                "message": f"ggplot saved to {out_path}",
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def create_correlation_heatmap(
        ctx: Context,
        file_path: str,
        filename: str = "correlation_heatmap.png",
        method: str = "pearson",
        columns: str = "",
        width: int = 1024,
        height: int = 900,
    ) -> str:
        """Generate a correlation heatmap from a data file using ggplot2.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            filename: Output filename (saved in ~/r-mcp-workspace/).
            method: Correlation method — "pearson", "spearman", "kendall".
            columns: Comma-separated column names (empty = all numeric).
            width: Image width in pixels (default 1024).
            height: Image height in pixels (default 900).

        Returns:
            JSON with path to the saved heatmap PNG.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)
            out_path.parent.mkdir(parents=True, exist_ok=True)
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

            w_in = round(width / 150, 2)
            h_in = round(height / 150, 2)

            code = (
                'library(ggplot2)\n'
                f'{read_cmd}\n'
                f'{col_filter}'
                'nums <- df[, sapply(df, is.numeric), drop = FALSE]\n'
                f'cor_mat <- cor(nums, use = "pairwise.complete.obs", method = "{method}")\n'
                '# Melt to long format\n'
                'cor_df <- as.data.frame(as.table(cor_mat))\n'
                'names(cor_df) <- c("Var1", "Var2", "value")\n'
                'p <- ggplot(cor_df, aes(Var1, Var2, fill = value)) +\n'
                '    geom_tile(color = "white") +\n'
                '    geom_text(aes(label = sprintf("%.2f", value)), size = 3) +\n'
                '    scale_fill_gradient2(low = "#457B9D", mid = "white",\n'
                '        high = "#E63946", midpoint = 0, limits = c(-1, 1)) +\n'
                f'    labs(title = "Correlation Matrix ({method})",\n'
                '         fill = "Correlation") +\n'
                '    theme_minimal() +\n'
                '    theme(axis.text.x = element_text(angle = 45, hjust = 1),\n'
                '          axis.title = element_blank())\n'
                f'ggsave("{out_path}", p, width = {w_in}, height = {h_in},\n'
                '       dpi = 150, bg = "white")\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0 or not out_path.exists():
                return json.dumps({"error": stderr or "Heatmap failed", "output": stdout})
            return json.dumps({
                "path": str(out_path),
                "message": f"Correlation heatmap saved to {out_path}",
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def create_multi_plot(
        ctx: Context,
        code: str,
        filename: str = "multi_plot.png",
        width: int = 1200,
        height: int = 900,
        ncol: int = 2,
    ) -> str:
        """Create a multi-panel figure from multiple ggplot objects.

        The code should create ggplot objects named p1, p2, p3, etc.
        They will be arranged using patchwork (if available) or gridExtra.

        Args:
            code: R code that creates ggplot objects p1, p2, p3, ...
            filename: Output filename (saved in ~/r-mcp-workspace/).
            width: Image width in pixels (default 1200).
            height: Image height in pixels (default 900).
            ncol: Number of columns in the layout (default 2).

        Returns:
            JSON with path to the saved multi-panel PNG.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            w_in = round(width / 150, 2)
            h_in = round(height / 150, 2)

            wrapped = (
                'library(ggplot2)\n'
                f'{code}\n'
                '# Collect all p1, p2, p3, ... objects\n'
                'plots <- list()\n'
                'for (i in 1:20) {\n'
                '    nm <- paste0("p", i)\n'
                '    if (exists(nm) && inherits(get(nm), "gg")) {\n'
                '        plots[[length(plots)+1]] <- get(nm)\n'
                '    } else break\n'
                '}\n'
                'if (length(plots) == 0) stop("No ggplot objects p1, p2, ... found")\n'
                'if (requireNamespace("patchwork", quietly = TRUE)) {\n'
                '    library(patchwork)\n'
                '    combined <- wrap_plots(plots, ncol = ' + str(ncol) + ')\n'
                '} else if (requireNamespace("gridExtra", quietly = TRUE)) {\n'
                '    combined <- gridExtra::arrangeGrob(grobs = plots,\n'
                '        ncol = ' + str(ncol) + ')\n'
                '} else {\n'
                '    stop("Install patchwork or gridExtra for multi-panel plots")\n'
                '}\n'
                f'ggsave("{out_path}", combined, width = {w_in}, height = {h_in},\n'
                '       dpi = 150, bg = "white")\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=60)
            if rc != 0 or not out_path.exists():
                return json.dumps({"error": stderr or "Multi-plot failed", "output": stdout})
            return json.dumps({
                "path": str(out_path),
                "message": f"Multi-panel plot saved to {out_path}",
            })
        except Exception as e:
            return json.dumps({"error": str(e)})
