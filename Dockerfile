# syntax=docker/dockerfile:1
#
# LinkedIn AI Agent — Servidor MCP
#
# Build:  docker compose build
# Run:    docker compose run --rm linkedin-mcp-server
#
# NOTA: Los flujos HITL (Human in the Loop) requieren un navegador visible en el host.
# Esta imagen empaqueta el servidor MCP y sus dependencias de Python para:
#   - Reproducibilidad del entorno (CI, testing, evaluación)
#   - Ejecutar el servidor MCP en modo headless (validación de tools)
#   - Verificar la resolución de dependencias y la corrección del build
#
# Para el flujo HITL completo (login, 2FA), ejecutar localmente:
#   pip install -e ".[dev]"
#   playwright install chromium
#   python run_test_flow.py

FROM python:3.11-slim

WORKDIR /app

# Instalar las dependencias de sistema que requiere Chromium de Playwright
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

# Copiar los archivos del proyecto
COPY pyproject.toml .
COPY mcp/ mcp/
COPY src/ src/

# Instalar las dependencias de Python
RUN pip install --no-cache-dir -e ".[dev]"

# Instalar el navegador Chromium de Playwright
RUN python -m playwright install chromium

# Comando por defecto: iniciar el servidor MCP en modo stdio
CMD ["python", "-m", "mcp.linkedin_server.server"]
