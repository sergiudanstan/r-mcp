"""R MCP Server."""

import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from mcp.server.fastmcp import FastMCP

from r_mcp.client import RClient
from r_mcp.tools.execution_tools import register_execution_tools
from r_mcp.tools.analysis_tools import register_analysis_tools
from r_mcp.tools.viz_tools import register_viz_tools
from r_mcp.tools.stats_tools import register_stats_tools
from r_mcp.tools.data_tools import register_data_tools
from r_mcp.tools.ggplot_tools import register_ggplot_tools

logger = logging.getLogger(__name__)


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[dict]:
    client = RClient()
    client.ensure_ready()
    logger.info("R MCP server starting — Rscript: %s", client.binary)
    try:
        yield {"client": client}
    finally:
        logger.info("R MCP server stopped")


mcp = FastMCP("r", lifespan=server_lifespan)

register_execution_tools(mcp)
register_analysis_tools(mcp)
register_viz_tools(mcp)
register_stats_tools(mcp)
register_data_tools(mcp)
register_ggplot_tools(mcp)
