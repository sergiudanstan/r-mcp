"""Subprocess wrapper for the Rscript CLI."""

import asyncio
import logging
import os
import shutil
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_WORKSPACE = Path.home() / "r-mcp-workspace"
DEFAULT_TIMEOUT = 60  # seconds
MAX_OUTPUT = 50_000  # characters — truncate beyond this


class RClient:
    """Manages Rscript CLI invocations."""

    def __init__(self, workspace: Path | None = None) -> None:
        self.workspace = workspace or DEFAULT_WORKSPACE
        self.binary: str | None = None

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def discover_binary(self) -> str:
        """Find the Rscript binary on this system."""
        found = shutil.which("Rscript")
        if found:
            return found

        homebrew = "/opt/homebrew/bin/Rscript"
        if os.path.isfile(homebrew):
            return homebrew

        raise FileNotFoundError(
            "Rscript binary not found. Install R from https://cran.r-project.org/ "
            "or via 'brew install r'."
        )

    def ensure_ready(self) -> None:
        """Verify binary exists and workspace directory is created."""
        if self.binary is None:
            self.binary = self.discover_binary()
        self.workspace.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Core runners
    # ------------------------------------------------------------------

    async def run_code(
        self,
        code: str,
        timeout: float = DEFAULT_TIMEOUT,
        cwd: str | None = None,
    ) -> tuple[int, str, str]:
        """Run inline R code via Rscript --vanilla -e.

        Returns (returncode, stdout, stderr).
        """
        wrapped = self._wrap_code(code)
        proc = await asyncio.create_subprocess_exec(
            self.binary, "--vanilla", "-e", wrapped,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or str(self.workspace),
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise TimeoutError(f"R code timed out after {timeout}s.")

        stdout = self._truncate(stdout_b.decode(errors="replace"))
        stderr = self._truncate(stderr_b.decode(errors="replace"))
        return proc.returncode, stdout, stderr

    async def run_file(
        self,
        filepath: str,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> tuple[int, str, str]:
        """Run an .R script file via Rscript --vanilla <path>.

        Returns (returncode, stdout, stderr).
        """
        proc = await asyncio.create_subprocess_exec(
            self.binary, "--vanilla", filepath,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(Path(filepath).parent),
        )
        try:
            stdout_b, stderr_b = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise TimeoutError(f"R script timed out after {timeout}s.")

        stdout = self._truncate(stdout_b.decode(errors="replace"))
        stderr = self._truncate(stderr_b.decode(errors="replace"))
        return proc.returncode, stdout, stderr

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    def resolve_path(self, filename: str) -> Path:
        """Resolve a filename relative to the workspace.

        Prevents path traversal outside workspace.
        """
        path = (self.workspace / filename).resolve()
        if not str(path).startswith(str(self.workspace.resolve())):
            raise ValueError(f"Path traversal not allowed: {filename}")
        return path

    def write_temp_file(self, code: str, suffix: str = ".R") -> str:
        """Write code to a temp file in workspace, return the path."""
        fd, path = tempfile.mkstemp(suffix=suffix, dir=str(self.workspace))
        with os.fdopen(fd, "w") as f:
            f.write(code)
        return path

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap_code(code: str) -> str:
        """Wrap user code in tryCatch for clean error reporting."""
        return (
            'tryCatch({\n'
            f'{code}\n'
            '}, error = function(e) {\n'
            '    cat("R_ERROR:", conditionMessage(e), "\\n", file=stderr())\n'
            '})'
        )

    @staticmethod
    def _truncate(text: str) -> str:
        """Truncate output if it exceeds MAX_OUTPUT."""
        if len(text) > MAX_OUTPUT:
            return text[:MAX_OUTPUT] + f"\n... (truncated, {len(text)} chars total)"
        return text
