from fastmcp import FastMCP

mcp = FastMCP("research-trend-tracker")

# Import tools after mcp is defined — tools.py reads mcp from this module,
# so Python's partial-load behaviour makes this safe (mcp is already bound).
import app.mcp_server.tools  # noqa: E402, F401

if __name__ == "__main__":
    mcp.run()
