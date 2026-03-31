"""Entry point: python -m r_mcp"""
from r_mcp.server import mcp

mcp.run(transport="stdio")
