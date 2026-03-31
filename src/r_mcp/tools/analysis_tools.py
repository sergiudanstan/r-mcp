"""Analysis tools — code checking, data summary, package info."""

import json
import os

from mcp.server.fastmcp import FastMCP, Context


def register_analysis_tools(mcp: FastMCP) -> None:
    """Register analysis tools with the MCP server."""

    @mcp.tool()
    async def check_r_code(ctx: Context, code: str) -> str:
        """Statically analyze R code using the lintr package.

        Checks for style issues, potential bugs, and best-practice
        violations. Requires the lintr package to be installed.

        Args:
            code: R code to analyze.

        Returns:
            JSON with lint results or an error if lintr is not installed.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            tmp_path = client.write_temp_file(code)
            try:
                lint_code = (
                    'if (!requireNamespace("lintr", quietly = TRUE)) {\n'
                    '    cat("ERROR: lintr package not installed. '
                    'Use install_r_package to install it.\\n", file=stderr())\n'
                    '    quit(status = 1)\n'
                    '}\n'
                    'library(lintr)\n'
                    'library(jsonlite)\n'
                    f'results <- lint("{tmp_path}")\n'
                    'issues <- lapply(results, function(x) list(\n'
                    '    line = x$line_number,\n'
                    '    column = x$column_number,\n'
                    '    type = x$type,\n'
                    '    message = x$message,\n'
                    '    linter = x$linter\n'
                    '))\n'
                    'cat(toJSON(list(\n'
                    '    passed = length(issues) == 0,\n'
                    '    issue_count = length(issues),\n'
                    '    issues = issues\n'
                    '), auto_unbox = TRUE))\n'
                )
                rc, stdout, stderr = await client.run_code(lint_code, timeout=30)
                if rc != 0:
                    return json.dumps({"error": stderr or "lintr failed"})
                try:
                    return stdout
                except Exception:
                    return json.dumps({"output": stdout, "errors": stderr})
            finally:
                os.unlink(tmp_path)
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def get_data_summary(
        ctx: Context, file_path: str, n_rows: int = 6
    ) -> str:
        """Load a data file (CSV, TSV, or RDS) and return summary statistics.

        Returns dimensions, column types, summary stats, and a preview
        of the first n_rows.

        Args:
            file_path: Absolute path to the data file.
            n_rows: Number of preview rows (default 6).

        Returns:
            JSON with dim, column classes, summary, and head preview.
        """
        try:
            if not os.path.isfile(file_path):
                return json.dumps({"error": f"File not found: {file_path}"})

            client = ctx.request_context.lifespan_context["client"]
            ext = os.path.splitext(file_path)[1].lower()
            if ext == ".csv":
                read_cmd = f'df <- read.csv("{file_path}")'
            elif ext == ".tsv":
                read_cmd = f'df <- read.delim("{file_path}")'
            elif ext == ".rds":
                read_cmd = f'df <- readRDS("{file_path}")'
            else:
                read_cmd = f'df <- read.csv("{file_path}")'

            code = (
                'library(jsonlite)\n'
                f'{read_cmd}\n'
                f'preview <- head(df, {n_rows})\n'
                'cat(toJSON(list(\n'
                '    file = "' + file_path + '",\n'
                '    dimensions = list(rows = nrow(df), cols = ncol(df)),\n'
                '    column_classes = sapply(df, class),\n'
                '    summary = capture.output(summary(df)),\n'
                '    head = preview\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=30)
            if rc != 0:
                return json.dumps({"error": stderr or "Failed to read data file"})
            try:
                json.loads(stdout)
                return stdout
            except Exception:
                return json.dumps({"output": stdout, "errors": stderr})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def detect_r_packages(ctx: Context) -> str:
        """List all installed R packages with their versions.

        Returns:
            JSON with a list of {package, version} entries and total count.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            code = (
                'library(jsonlite)\n'
                'pkgs <- installed.packages()[, c("Package", "Version")]\n'
                'pkg_list <- lapply(seq_len(nrow(pkgs)), function(i) {\n'
                '    list(package = unname(pkgs[i, "Package"]),\n'
                '         version = unname(pkgs[i, "Version"]))\n'
                '})\n'
                'cat(toJSON(list(packages = pkg_list, count = nrow(pkgs)),\n'
                '           auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=15)
            if rc != 0:
                return json.dumps({"error": stderr or "Failed to list packages"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def get_r_version(ctx: Context) -> str:
        """Return R version string, platform info, and session details.

        Returns:
            JSON with version, platform, and sessionInfo output.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            code = (
                'library(jsonlite)\n'
                'cat(toJSON(list(\n'
                '    version = R.version.string,\n'
                '    platform = R.version$platform,\n'
                '    arch = R.version$arch,\n'
                '    os = R.version$os,\n'
                '    session_info = capture.output(sessionInfo())\n'
                '), auto_unbox = TRUE))\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=10)
            if rc != 0:
                return json.dumps({"error": stderr or "Failed to get R version"})
            return stdout
        except Exception as e:
            return json.dumps({"error": str(e)})
