"""Execution tools — run R code and scripts."""

import json
import os

from mcp.server.fastmcp import FastMCP, Context


def register_execution_tools(mcp: FastMCP) -> None:
    """Register execution tools with the MCP server."""

    @mcp.tool()
    async def evaluate_r_code(ctx: Context, code: str, timeout: float = 60.0) -> str:
        """Execute inline R code and return the console output.

        Use this for any R computation — statistics, data manipulation,
        package loading, or printing results. The code runs in a fresh
        R session via Rscript --vanilla.

        Args:
            code: R code to execute.
            timeout: Maximum execution time in seconds (default 60).

        Returns:
            JSON with stdout, stderr, and return_code.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            rc, stdout, stderr = await client.run_code(code, timeout=timeout)
            return json.dumps({
                "return_code": rc,
                "output": stdout,
                "errors": stderr,
            })
        except TimeoutError as e:
            return json.dumps({"error": str(e)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def run_r_file(ctx: Context, file_path: str, timeout: float = 60.0) -> str:
        """Execute an .R script file and return its output.

        Args:
            file_path: Absolute path to the .R script.
            timeout: Maximum execution time in seconds (default 60).

        Returns:
            JSON with file path, stdout, stderr, and return_code.
        """
        try:
            if not os.path.isfile(file_path):
                return json.dumps({"error": f"File not found: {file_path}"})
            if not file_path.lower().endswith((".r", ".R")):
                return json.dumps({"error": f"Not an R file: {file_path}"})

            client = ctx.request_context.lifespan_context["client"]
            rc, stdout, stderr = await client.run_file(file_path, timeout=timeout)
            return json.dumps({
                "file": file_path,
                "return_code": rc,
                "output": stdout,
                "errors": stderr,
            })
        except TimeoutError as e:
            return json.dumps({"error": str(e)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def run_r_test_file(ctx: Context, file_path: str, timeout: float = 120.0) -> str:
        """Run a testthat test file and return pass/fail results.

        The file should contain testthat test_that() blocks.
        Requires the testthat package to be installed.

        Args:
            file_path: Absolute path to the test .R file.
            timeout: Maximum execution time in seconds (default 120).

        Returns:
            JSON with file path, test output, and pass/fail status.
        """
        try:
            if not os.path.isfile(file_path):
                return json.dumps({"error": f"File not found: {file_path}"})

            client = ctx.request_context.lifespan_context["client"]
            code = (
                'if (!requireNamespace("testthat", quietly = TRUE)) {\n'
                '    cat("ERROR: testthat package not installed. '
                'Use install_r_package to install it.\\n", file=stderr())\n'
                '    quit(status = 1)\n'
                '}\n'
                'library(testthat)\n'
                f'test_file("{file_path}", reporter = "summary")\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=timeout)
            passed = rc == 0 and "FAILED" not in stdout and "Error" not in stderr
            return json.dumps({
                "file": file_path,
                "return_code": rc,
                "passed": passed,
                "output": stdout,
                "errors": stderr,
            })
        except TimeoutError as e:
            return json.dumps({"error": str(e)})
        except Exception as e:
            return json.dumps({"error": str(e)})
