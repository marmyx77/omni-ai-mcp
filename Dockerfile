# omni-ai-mcp — MCP server (stdio) in a container
#
#   docker build -t omni-ai-mcp .
#   docker run -i --rm -e GEMINI_API_KEY -v "$PWD:/workspace" omni-ai-mcp
#
# MCP clients start it per session with `docker run -i --rm ...` (see README → Docker).

FROM python:3.12-slim

# Security: run as an unprivileged user
RUN useradd --create-home --shell /usr/sbin/nologin omni
WORKDIR /opt/omni-ai-mcp

# Install the package (metadata first for better layer caching)
COPY pyproject.toml README.md LICENSE ./
COPY app ./app
RUN pip install --no-cache-dir . && rm -rf /root/.cache

ENV PYTHONUNBUFFERED=1 \
    GEMINI_SANDBOX_ROOT=/workspace \
    GEMINI_SANDBOX_ENABLED=true \
    GEMINI_ACTIVITY_LOG=true \
    GEMINI_LOG_DIR=/logs

RUN mkdir -p /workspace /logs && chown omni:omni /workspace /logs
USER omni

# Files the tools read/write (sandbox root) and logs + SQLite conversations
VOLUME ["/workspace", "/logs"]

# The server speaks MCP over stdin/stdout; this only checks the package imports
HEALTHCHECK --interval=60s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import app; print(app.__version__)" || exit 1

ENTRYPOINT ["omni-ai-mcp"]
