"""Visualization tools — plotting, rendering, and package management."""

import json
import os

from mcp.server.fastmcp import FastMCP, Context


def register_viz_tools(mcp: FastMCP) -> None:
    """Register visualization and utility tools with the MCP server."""

    @mcp.tool()
    async def create_r_plot(
        ctx: Context,
        code: str,
        filename: str = "plot.png",
        width: int = 1024,
        height: int = 768,
    ) -> str:
        """Execute R plotting code and save the result as a PNG file.

        The code should contain plotting commands (e.g. plot(), ggplot()).
        The plot device is opened and closed automatically — do NOT call
        png() or dev.off() in your code.

        Args:
            code: R plotting code.
            filename: Output filename (saved in ~/r-mcp-workspace/).
            width: Image width in pixels (default 1024).
            height: Image height in pixels (default 768).

        Returns:
            JSON with the absolute path to the saved PNG file.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            out_path = client.resolve_path(filename)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            wrapped = (
                f'png("{out_path}", width = {width}, height = {height}, res = 150)\n'
                f'{code}\n'
                'dev.off()\n'
                f'cat("Saved plot: {out_path}\\n")\n'
            )
            rc, stdout, stderr = await client.run_code(wrapped, timeout=60)
            if rc != 0 or not out_path.exists():
                return json.dumps({
                    "error": stderr or "Plot generation failed",
                    "output": stdout,
                })
            return json.dumps({
                "path": str(out_path),
                "message": f"Plot saved to {out_path}",
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def render_rmarkdown(
        ctx: Context,
        file_path: str,
        output_format: str = "html_document",
        timeout: float = 120.0,
    ) -> str:
        """Render an R Markdown (.Rmd) file to HTML or PDF.

        Requires the rmarkdown package. Uses pandoc bundled with RStudio
        if available.

        Args:
            file_path: Absolute path to the .Rmd file.
            output_format: Output format — "html_document" (default) or "pdf_document".
            timeout: Maximum render time in seconds (default 120).

        Returns:
            JSON with input path, output path, and format.
        """
        try:
            if not os.path.isfile(file_path):
                return json.dumps({"error": f"File not found: {file_path}"})

            client = ctx.request_context.lifespan_context["client"]
            code = (
                'if (!requireNamespace("rmarkdown", quietly = TRUE)) {\n'
                '    cat("ERROR: rmarkdown package not installed. '
                'Use install_r_package to install it.\\n", file=stderr())\n'
                '    quit(status = 1)\n'
                '}\n'
                '# Use RStudio bundled pandoc if available\n'
                'rstudio_pandoc <- "/Applications/RStudio.app/Contents/'
                'Resources/app/quarto/bin/tools/aarch64"\n'
                'if (dir.exists(rstudio_pandoc)) {\n'
                '    Sys.setenv(RSTUDIO_PANDOC = rstudio_pandoc)\n'
                '}\n'
                f'output <- rmarkdown::render("{file_path}",\n'
                f'    output_format = "{output_format}", quiet = TRUE)\n'
                'cat(output)\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=timeout)
            if rc != 0:
                return json.dumps({"error": stderr or "Render failed", "output": stdout})
            output_path = stdout.strip()
            return json.dumps({
                "input": file_path,
                "output": output_path,
                "format": output_format,
            })
        except TimeoutError as e:
            return json.dumps({"error": str(e)})
        except Exception as e:
            return json.dumps({"error": str(e)})

    @mcp.tool()
    async def install_r_package(
        ctx: Context,
        package_name: str,
        repos: str = "https://cloud.r-project.org",
    ) -> str:
        """Install an R package from CRAN.

        Args:
            package_name: Name of the CRAN package to install.
            repos: CRAN mirror URL (default: cloud.r-project.org).

        Returns:
            JSON with package name, installation status, and output.
        """
        try:
            client = ctx.request_context.lifespan_context["client"]
            code = (
                f'install.packages("{package_name}",\n'
                f'    repos = "{repos}", quiet = TRUE)\n'
                f'if (requireNamespace("{package_name}", quietly = TRUE)) {{\n'
                f'    cat("SUCCESS: {package_name} installed\\n")\n'
                '} else {\n'
                f'    cat("FAILED: {package_name} could not be loaded after install\\n",\n'
                '        file = stderr())\n'
                '}\n'
            )
            rc, stdout, stderr = await client.run_code(code, timeout=120)
            success = "SUCCESS" in stdout
            return json.dumps({
                "package": package_name,
                "installed": success,
                "output": stdout,
                "errors": stderr,
            })
        except TimeoutError as e:
            return json.dumps({"error": str(e)})
        except Exception as e:
            return json.dumps({"error": str(e)})
