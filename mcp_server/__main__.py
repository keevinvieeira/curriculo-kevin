"""Entry point: `python -m mcp_server` from the repo, or `python <repo>/mcp_server` from anywhere
(what Claude Desktop runs — it does not set the working directory)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mcp_server.server import server  # noqa: E402

if __name__ == "__main__":
    server.run("stdio")
