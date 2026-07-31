# syntax=docker/dockerfile:1
#
# LinkedIn AI Agent — MCP Server
#
# Build:  docker compose build
# Run:    docker compose run --rm linkedin-mcp-server
#
# NOTE: HITL (Human in the Loop) flows require a visible browser on the host.
# This image packages the MCP server and its Python dependencies for:
#   - Environment reproducibility (CI, testing, evaluation)
#   - Running the MCP server in headless mode (tool validation)
#   - Verifying dependency resolution and build correctness
#
# For the full HITL flow (login, 2FA, manual publish), run locally:
#   pip install -e ".[dev]"
#   playwright install chromium
#   python run_test_flow.py

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies required by Playwright's Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libdbus-1-3 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY mcp/ mcp/
COPY src/ src/

# Install Python dependencies
RUN pip install --no-cache-dir -e ".[dev]"

# Install Playwright Chromium browser
RUN python -m playwright install chromium

# Default command: start the MCP server in stdio mode
CMD ["python", "-m", "mcp.linkedin_server.server"]
