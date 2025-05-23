#!/usr/bin/env python3
"""Entry point script for LearnMCP-xAPI server."""

import sys
import os

# Add current directory to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, current_dir)

# Import and run the server
from learnmcp_xapi.main import mcp

if __name__ == "__main__":
    mcp.run()