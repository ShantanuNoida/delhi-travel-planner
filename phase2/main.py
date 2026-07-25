"""
Phase 2 entry points.

  python main.py test              — run all Phase 2 tests
  python main.py poi               — start POI Search MCP server (stdio)
  python main.py itinerary         — start Itinerary Builder MCP server (stdio)
  python main.py travel            — start Travel Time MCP server (stdio)
  python main.py weather           — start Weather Adjustment MCP server (stdio)

In Phase 3, the agent will launch each server as a subprocess and
communicate over stdio using the MCP protocol.
"""

import sys


def usage():
    print(__doc__)
    sys.exit(0)


def main():
    if len(sys.argv) < 2:
        usage()

    cmd = sys.argv[1].lower()

    if cmd == "test":
        from test_tools import run_all
        run_all()

    elif cmd == "poi":
        from poi_search import mcp
        mcp.run()

    elif cmd == "itinerary":
        from itinerary_builder import mcp
        mcp.run()

    elif cmd == "travel":
        from travel_time import mcp
        mcp.run()

    elif cmd == "weather":
        from weather import mcp
        mcp.run()

    else:
        print(f"Unknown command: {cmd}")
        usage()


if __name__ == "__main__":
    main()
