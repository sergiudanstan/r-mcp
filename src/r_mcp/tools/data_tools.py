"""Data wrangling tools — read, write, reshape, merge, sample datasets."""

import json
import os

from mcp.server.fastmcp import FastMCP, Context


def register_data_tools(mcp: FastMCP) -> None:
    """Register data wrangling tools with the MCP server."""

    @mcp.tool()
    async def read_data(
        ctx: Context,
        file_path: str,
        n_rows: int = 0,
        sheet: str = "",
    ) -> str:
        """Read data from CSV, TSV, Excel (.xlsx), JSON, or RDS files.

        Returns dimensions, column types, and a preview of the data.

        Args:
            file_path: Absolute path to the data file.
            n_rows: Max rows to return in preview (0 = first 20 rows).
            sheet: Sheet name for Excel files (default = first sheet).

        Returns:
            JSON with dimensions, column classes, and data preview.
        """
        try:
            if not os.path.isfile(file_path):
                return json.dumps({"error": f"File not found: {file_path}"})

            client = ctx.request_context.lifespan_context["client"]
            ext = os.path.splitext(file_path)[1].lower()
            preview_n = n_rows if n_rows > 0 else 20

            if ext in (".xls", ".xlsx"):
                sheet_arg = f', sheet = "{sheet}"' if sheet else ""
                read_cmd = (
                    'if (!requireNamespace("readxl", quietly = TRUE)) '
                    'stop("readxl package required. Use install_r_package.")\n'
                    f'df <- readxl::read_excel("{file_path}"{sheet_arg})\n'
                    'df <- as.data.frame(df)\n'
                )
            elif ext == ".json":
                read_cmd = (
                    'library(jsonlite)\n'
                    f'df <- as.data.frame(fromJSON("{file_path}"))\n'
                )
            elif ext == ".tsv":
                read_cmd = f'df <- read.delim("{file_path}")\n'
            elif ext == ".rds":
                read_cmd = f'df <- readRDS("{file_path}")\n'
            elif ext == ".parquet":
                read_cmd = (
                    'if (!requireNamespace("arrow", quietly = TRUE)) '
                    'stop("arrow package required. Use install_r_package.")\n'
                    f'df <- as.data.frame(arrow::read_parquet("{file_path}"))\n'
                )
            else:
                read_cmd = f'df <- read.csv("{file_path}")\n'

            code = (
                'library(jsonlite)\n'
                f'{read_cmd}'
                f'preview <- head(df, {preview_n})\n'
                'cat(toJSON(list(\n'
                '    file = "' + file_path + '",\n'
                '    dimensions = list(rows = nrow(df), cols = ncol(df)),\n'
                '    column_classes = sapply(df, function(x) class(x)[1]),\n'
                '    column_names = names(df),\n'
                '    preview = preview\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Failed to read file"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def write_data(
        ctx: Context,
        code: str,
        output_path: str,
        format: str = "csv",
    ) -> str:
        """Execute R code that produces a data frame and save it to a file.

        The code must assign the result to a variable called `df`.

        Args:
            code: R code that creates a data frame named `df`.
            output_path: Output filename (saved in ~/r-mcp-workspace/).
            format: Output format — "csv" (default), "tsv", "rds", "json".

        Returns:
            JSON with the absolute path and row/column counts.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out = client.resolve_path(output_path)
            out.parent.mkdir(parents=True, exist_ok=True)

            if format == "tsv":
                write_cmd = f'write.table(df, "{out}", sep = "\\t", row.names = FALSE)'
            elif format == "rds":
                write_cmd = f'saveRDS(df, "{out}")'
            elif format == "json":
                write_cmd = f'write(toJSON(df, auto_unbox = TRUE), "{out}")'
            else:
                write_cmd = f'write.csv(df, "{out}", row.names = FALSE)'

            wrapped = (
                'library(jsonlite)\n'
                f'{code}\n'
                'if (!is.data.frame(df)) df <- as.data.frame(df)\n'
                f'{write_cmd}\n'
                'cat(toJSON(list(\n'
                f'    path = "{out}",\n'
                '    rows = nrow(df),\n'
                '    cols = ncol(df),\n'
                f'    format = "{format}"\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Write failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def reshape_data(
        ctx: Context,
        file_path: str,
        operation: str,
        columns: str,
        names_to: str = "name",
        values_to: str = "value",
        names_from: str = "",
        values_from: str = "",
        output_path: str = "reshaped.csv",
    ) -> str:
        """Reshape data between wide and long formats using tidyr.

        Args:
            file_path: Absolute path to a CSV/TSV/RDS data file.
            operation: "longer" (wide-to-long) or "wider" (long-to-wide).
            columns: For "longer": comma-separated columns to pivot.
                     For "wider": ignored (use names_from/values_from).
            names_to: Column name for variable names in long format (default "name").
            values_to: Column name for values in long format (default "value").
            names_from: Column whose values become column names in wide format.
            values_from: Column whose values fill the wide cells.
            output_path: Output filename (saved in ~/r-mcp-workspace/).

        Returns:
            JSON with output path, new dimensions, and data preview.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            import os as _os
            ext = _os.path.splitext(file_path)[1].lower()
            if ext == ".tsv":
                read_cmd = f'df <- read.delim("{file_path}")'
            elif ext == ".rds":
                read_cmd = f'df <- readRDS("{file_path}")'
            else:
                read_cmd = f'df <- read.csv("{file_path}")'

            out = client.resolve_path(output_path)

            if operation == "longer":
                cols = [c.strip() for c in columns.split(",")]
                col_r = ", ".join(f'"{c}"' for c in cols)
                pivot_cmd = (
                    f'result <- tidyr::pivot_longer(df, cols = c({col_r}),\n'
                    f'    names_to = "{names_to}", values_to = "{values_to}")\n'
                )
            else:
                pivot_cmd = (
                    f'result <- tidyr::pivot_wider(df,\n'
                    f'    names_from = "{names_from}", values_from = "{values_from}")\n'
                )

            code = (
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'{pivot_cmd}'
                'result <- as.data.frame(result)\n'
                f'write.csv(result, "{out}", row.names = FALSE)\n'
                'cat(toJSON(list(\n'
                f'    path = "{out}",\n'
                '    rows = nrow(result), cols = ncol(result),\n'
                '    columns = names(result),\n'
                '    preview = head(result, 10)\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Reshape failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def merge_datasets(
        ctx: Context,
        file_left: str,
        file_right: str,
        by: str,
        how: str = "inner",
        output_path: str = "merged.csv",
    ) -> str:
        """Merge (join) two data files on common columns.

        Args:
            file_left: Absolute path to the left data file.
            file_right: Absolute path to the right data file.
            by: Comma-separated column names to join on.
            how: Join type — "inner" (default), "left", "right", "full".
            output_path: Output filename (saved in ~/r-mcp-workspace/).

        Returns:
            JSON with output path, dimensions, and preview.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out = client.resolve_path(output_path)

            def read_cmd(fp, var):
                ext = os.path.splitext(fp)[1].lower()
                if ext == ".tsv":
                    return f'{var} <- read.delim("{fp}")'
                elif ext == ".rds":
                    return f'{var} <- readRDS("{fp}")'
                return f'{var} <- read.csv("{fp}")'

            by_cols = ", ".join(f'"{c.strip()}"' for c in by.split(","))
            all_x = "TRUE" if how in ("left", "full") else "FALSE"
            all_y = "TRUE" if how in ("right", "full") else "FALSE"

            code = (
                'library(jsonlite)\n'
                f'{read_cmd(file_left, "left")}\n'
                f'{read_cmd(file_right, "right")}\n'
                f'result <- merge(left, right, by = c({by_cols}),\n'
                f'    all.x = {all_x}, all.y = {all_y})\n'
                f'write.csv(result, "{out}", row.names = FALSE)\n'
                'cat(toJSON(list(\n'
                f'    path = "{out}",\n'
                f'    join = "{how}",\n'
                '    left_rows = nrow(left), right_rows = nrow(right),\n'
                '    result_rows = nrow(result), result_cols = ncol(result),\n'
                '    columns = names(result),\n'
                '    preview = head(result, 10)\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Merge failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def generate_sample_data(
        ctx: Context,
        dataset: str = "mtcars",
        output_path: str = "",
    ) -> str:
        """Generate or load a built-in R sample dataset and save it as CSV.

        Args:
            dataset: Name of a built-in R dataset — "mtcars", "iris",
                     "airquality", "ToothGrowth", "PlantGrowth", "USArrests",
                     "ChickWeight", "CO2", "diamonds" (ggplot2), "economics" (ggplot2).
            output_path: Output filename (default = dataset name + .csv).

        Returns:
            JSON with path, dimensions, column info, and preview.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            fname = output_path or f"{dataset}.csv"
            out = client.resolve_path(fname)

            code = (
                'library(jsonlite)\n'
                f'if ("{dataset}" %in% c("diamonds", "economics", "mpg")) {{\n'
                '    if (!requireNamespace("ggplot2", quietly = TRUE))\n'
                '        stop("ggplot2 required for this dataset")\n'
                f'    df <- as.data.frame(ggplot2::{dataset})\n'
                '} else {\n'
                f'    df <- as.data.frame(get("{dataset}"))\n'
                '}\n'
                f'write.csv(df, "{out}", row.names = FALSE)\n'
                'cat(toJSON(list(\n'
                f'    path = "{out}",\n'
                f'    dataset = "{dataset}",\n'
                '    rows = nrow(df), cols = ncol(df),\n'
                '    columns = lapply(names(df), function(n)\n'
                '        list(name = n, class = class(df[[n]])[1])),\n'
                '    preview = head(df, 6)\n'
                '), auto_unbox = TRUE, na = "null"))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=15)
            if rc != 0:
                return json.dumps({"error": stderr or "Dataset load failed"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})
