"""Tests for r_mcp: path confinement, output limits, tool registry and a real Rscript run."""

import asyncio
import json
import os
import shutil
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from r_mcp.client import MAX_OUTPUT, RClient


@pytest.fixture()
def client(tmp_path: Path) -> RClient:
    ws = tmp_path / "ws"
    ws.mkdir()
    c = RClient(workspace=ws)
    c.ensure_ready()
    return c


@pytest.fixture()
def rscript(client: RClient) -> RClient:
    """A client wired to a real Rscript. CI sets REQUIRE_R=1 so a missing R fails loudly."""
    if shutil.which("Rscript") is None:
        if os.environ.get("REQUIRE_R"):
            pytest.fail("REQUIRE_R is set but Rscript is not on PATH")
        pytest.skip("Rscript not installed")
    return client


def _ctx(client: RClient) -> MagicMock:
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"client": client}
    return ctx


def _tool(name: str):
    from r_mcp.server import mcp

    return mcp._tool_manager._tools[name].fn


class TestResolvePath:
    def test_inside_workspace(self, client: RClient) -> None:
        assert client.resolve_path("a/b.csv") == client.workspace.resolve() / "a" / "b.csv"

    def test_parent_traversal_rejected(self, client: RClient) -> None:
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            client.resolve_path("../outside.csv")

    def test_absolute_outside_rejected(self, client: RClient) -> None:
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            client.resolve_path("/etc/passwd")

    def test_sibling_with_same_prefix_rejected(self, client: RClient) -> None:
        """A directory next to the workspace whose name starts with the same text is outside it."""
        sibling = client.workspace.parent / (client.workspace.name + "-evil")
        sibling.mkdir()
        with pytest.raises(ValueError, match="Path traversal not allowed"):
            client.resolve_path(f"../{sibling.name}/x.csv")


class TestHelpers:
    def test_truncate_keeps_short_output(self) -> None:
        assert RClient._truncate("abc") == "abc"

    def test_truncate_cuts_long_output(self) -> None:
        out = RClient._truncate("x" * (MAX_OUTPUT + 10))
        assert out.startswith("x" * MAX_OUTPUT)
        assert f"truncated, {MAX_OUTPUT + 10} chars total" in out

    def test_wrap_code_reports_errors_on_stderr(self) -> None:
        wrapped = RClient._wrap_code("stop('boom')")
        assert wrapped.startswith("tryCatch({") and "R_ERROR:" in wrapped and "stop('boom')" in wrapped

    def test_write_temp_file_lands_in_workspace(self, client: RClient) -> None:
        path = Path(client.write_temp_file("1+1"))
        assert path.parent == client.workspace and path.read_text() == "1+1"


class TestToolRegistry:
    def test_server_registers_all_62_tools(self) -> None:
        from r_mcp.server import mcp

        names = {t.name for t in mcp._tool_manager.list_tools()}
        assert len(names) == 62
        assert {"evaluate_r_code", "run_r_file", "run_r_test_file", "install_r_package"} <= names


class TestRealRscript:
    def test_evaluate_r_code(self, rscript: RClient) -> None:
        result = json.loads(asyncio.run(_tool("evaluate_r_code")(_ctx(rscript), code="cat(6 * 7)")))
        assert result["return_code"] == 0
        assert result["output"].strip() == "42"

    def test_r_error_is_reported(self, rscript: RClient) -> None:
        result = json.loads(asyncio.run(_tool("evaluate_r_code")(_ctx(rscript), code="stop('boom')")))
        assert "R_ERROR: boom" in result["errors"]

    def test_timeout_kills_the_process(self, rscript: RClient) -> None:
        result = json.loads(
            asyncio.run(_tool("evaluate_r_code")(_ctx(rscript), code="Sys.sleep(30)", timeout=1.0))
        )
        assert "timed out" in result["error"]

    def test_run_r_file(self, rscript: RClient) -> None:
        script = rscript.workspace / "hello.R"
        script.write_text("cat('hello from file')")
        result = json.loads(asyncio.run(_tool("run_r_file")(_ctx(rscript), file_path=str(script))))
        assert result["return_code"] == 0 and result["output"] == "hello from file"

    def test_run_r_file_rejects_non_r_extension(self, rscript: RClient) -> None:
        other = rscript.workspace / "notes.txt"
        other.write_text("x")
        result = json.loads(asyncio.run(_tool("run_r_file")(_ctx(rscript), file_path=str(other))))
        assert "Not an R file" in result["error"]


class TestPredictWithCi:
    def test_builds_r_code_instead_of_raising(self, client: RClient) -> None:
        """Regression test: the tool used to raise NameError ('pred') before reaching R."""
        seen: dict = {}

        async def fake_run_code(code: str, timeout: float = 60.0, cwd=None):
            seen["code"] = code
            return 0, '{"ok":true}', ""

        client.run_code = fake_run_code  # type: ignore[method-assign]
        data = client.workspace / "d.csv"
        data.write_text("x,y\n1,2\n2,4\n3,6.5\n")
        out = asyncio.run(
            _tool("predict_with_ci")(
                _ctx(client), file_path=str(data), formula="y ~ x", new_data="data.frame(x = 4)"
            )
        )
        assert out == '{"ok":true}'
        assert "lm(y ~ x" in seen["code"] and "pred_var" in seen["code"]
