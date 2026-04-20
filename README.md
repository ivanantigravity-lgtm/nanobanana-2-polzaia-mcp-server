# Nano Banana 2 Polza MCP Server

`mcp-name: io.github.ivanantigravity-lgtm/nanobanana-2-polzaia-mcp-server`

MCP server for image generation and editing through `Polza`, using:

- `google/gemini-3.1-flash-image-preview` as the default Nano Banana 2 model
- `google/gemini-3-pro-image-preview` for higher-quality compositions
- `google/gemini-2.5-flash-image` for faster draft generation

This project exposes MCP tools like:

- `generate_image`
- `upload_file`
- `output_stats`
- `maintenance`

## What Users Need

- `Claude Code` or another MCP client
- `uv`
- `Python 3.11+`
- a `POLZA_AI_API_KEY`

## Local Development

```bash
git clone https://github.com/ivanantigravity-lgtm/nanobanana-2-polzaia-mcp-server.git
cd nanobanana-2-polzaia-mcp-server
uv sync
cp .env.example .env
```

Set at minimum:

```env
POLZA_AI_API_KEY=your_polza_api_key
POLZA_BASE_URL=https://polza.ai/api
IMAGE_OUTPUT_DIR=/absolute/path/to/output
```

Run locally:

```bash
uv run python -m nanobanana_mcp_server.server
```

## Claude Code / VS Code

If the package is published to PyPI, the easy install path is a project-level `.mcp.json`:

```json
{
  "mcpServers": {
    "nanobanana-polza": {
      "command": "uvx",
      "args": ["nanobanana-2-polzaia-mcp-server@latest"],
      "env": {
        "POLZA_AI_API_KEY": "your-polza-api-key-here",
        "POLZA_BASE_URL": "https://polza.ai/api",
        "IMAGE_OUTPUT_DIR": "/Users/demo/Documents/nanobanana"
      }
    }
  }
}
```

If the user runs from source instead of a published package:

```json
{
  "mcpServers": {
    "nanobanana-polza-local": {
      "command": "uv",
      "args": ["run", "python", "-m", "nanobanana_mcp_server.server"],
      "cwd": "/absolute/path/to/nanobanana-2-polzaia-mcp-server",
      "env": {
        "POLZA_AI_API_KEY": "your-polza-api-key-here",
        "POLZA_BASE_URL": "https://polza.ai/api",
        "IMAGE_OUTPUT_DIR": "/absolute/path/to/output"
      }
    }
  }
}
```

## Claude Desktop

On macOS, add the same server to:

`~/Library/Application Support/Claude/claude_desktop_config.json`

Example:

```json
{
  "mcpServers": {
    "nanobanana-polza": {
      "command": "uvx",
      "args": ["nanobanana-2-polzaia-mcp-server@latest"],
      "env": {
        "POLZA_AI_API_KEY": "your-polza-api-key-here",
        "POLZA_BASE_URL": "https://polza.ai/api",
        "IMAGE_OUTPUT_DIR": "/Users/demo/Documents/nanobanana"
      }
    }
  }
}
```

## What Still Needs To Be Published

To make installation as easy as the screenshot flow:

1. Publish the Python package to `PyPI`
2. Update repository URLs in `pyproject.toml` and `server.json`
3. Publish `server.json` to the `MCP Registry`

The registry only stores metadata. The actual package still needs to exist on PyPI.

## Publish Checklist

Before publishing:

1. Create the GitHub repo `ivanantigravity-lgtm/nanobanana-2-polzaia-mcp-server`
2. Bump the version
3. Build and test:

```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall nanobanana_mcp_server tests
uv build
```

4. Publish to PyPI

```bash
uv publish
```

5. Publish `server.json` with `mcp-publisher`

```bash
brew install mcp-publisher
mcp-publisher login
mcp-publisher publish
```

## Backend Notes

This server uses:

- `POST /v1/media`
- `GET /v1/media/{id}`
- `POST /v1/storage/upload`
- `GET /v1/storage/files/{id}`
- `DELETE /v1/storage/files/{id}`

through the Polza API.
