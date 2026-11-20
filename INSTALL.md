# Meraki Magic MCP - Complete Installation Guide

This guide provides step-by-step installation instructions for both macOS and Windows.

---

## Table of Contents
- [Prerequisites](#prerequisites)
- [macOS Installation](#macos-installation)
- [Windows Installation](#windows-installation)
- [Configuration](#configuration)
- [Claude Desktop Setup](#claude-desktop-setup)
- [HTTP Transport Mode](#http-transport-mode)
- [Docker Deployment](#docker-deployment)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

---

## Prerequisites

### For Both Platforms:
- **Python 3.13 or higher** installed
- **Claude Desktop** installed ([Download here](https://claude.ai/download))
- **Meraki Dashboard API Key** ([Get one here](https://documentation.meraki.com/General_Administration/Other_Topics/Cisco_Meraki_Dashboard_API))
- **Meraki Organization ID** (found in Dashboard → Organization → Settings)

### Check Python Version:

**macOS/Linux:**
```bash
python3 --version
```

**Windows (Command Prompt):**
```cmd
python --version
```

**Windows (PowerShell):**
```powershell
python --version
```

If Python is not installed or version is < 3.13:
- **macOS:** Install from [python.org](https://www.python.org/downloads/) or use Homebrew: `brew install python`
- **Windows:** Install from [python.org](https://www.python.org/downloads/) (check "Add Python to PATH" during installation)

---

## macOS Installation

### Step 1: Open Terminal
- Press `Cmd + Space`, type "Terminal", press Enter

### Step 2: Clone the Repository
```bash
cd ~
git clone https://github.com/CiscoDevNet/meraki-magic-mcp-community.git
cd meraki-magic-mcp-community
```

**If you don't have git:**
```bash
# Install Homebrew first (if needed)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install git
brew install git

# Then clone
git clone https://github.com/CiscoDevNet/meraki-magic-mcp-community.git
cd meraki-magic-mcp-community
```

### Step 3: Create Virtual Environment
```bash
python3 -m venv .venv
```

### Step 4: Activate Virtual Environment
```bash
source .venv/bin/activate
```

**You should see `(.venv)` appear in your terminal prompt.**

### Step 5: Install Dependencies
```bash
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed meraki-X.X.X fastmcp-X.X.X ...
```

### Step 6: Prepare Environment Variables

Do not create a project `.env` file. The MCP server reads credentials from the process environment.

For Claude Desktop / Cursor (stdio), add them in the client config `env` block in [Claude Desktop Setup](#claude-desktop-setup).

For CLI, HTTP, or Docker, export them in your shell:

```bash
export MERAKI_API_KEY="your_actual_api_key_here"
export MERAKI_ORG_ID="your_org_id_here"
export MERAKI_BASE_URL="https://api.meraki.com/api/v1"
export MERAKI_PYTHON_SDK_CALLER="MagicMCP CiscoDevNet"
export READ_ONLY_MODE=true
```

Optional tuning: `ENABLE_CACHING`, `CACHE_TTL_SECONDS`, `CACHE_MAX_ITEMS`, `ENABLE_FILE_CACHING`, `MAX_RESPONSE_TOKENS`, `MAX_PER_PAGE`, `RESPONSE_CACHE_DIR`, `RESPONSE_CACHE_MAX_AGE_HOURS`, `RESPONSE_CACHE_MAX_MB`.

`READ_ONLY_MODE` defaults to `true`. Set it to `false` only when you intend to make changes. Delete/remove calls also require `confirm_destructive_action=true`.

`MERAKI_PYTHON_SDK_CALLER` defaults to `MagicMCP CiscoDevNet` and identifies MCP requests in Meraki API usage records. Custom values must follow the [Meraki user agent format](https://developer.cisco.com/meraki/api-v1/user-agents-overview/).

### Step 7: Get Absolute Path for Claude Config
```bash
pwd
```

**Copy the output** (e.g., `/Users/yourname/meraki-magic-mcp-community`)

---

## Windows Installation

### Step 1: Open Terminal

**Option A: Command Prompt**
- Press `Win + R`, type `cmd`, press Enter

**Option B: PowerShell (Recommended)**
- Press `Win + X`, select "Windows PowerShell" or "Terminal"

### Step 2: Navigate to Your Home Directory
**Command Prompt:**
```cmd
cd %USERPROFILE%
```

**PowerShell:**
```powershell
cd ~
```

### Step 3: Clone the Repository

**If you have git installed:**
```cmd
git clone https://github.com/CiscoDevNet/meraki-magic-mcp-community.git
cd meraki-magic-mcp-community
```

**If you don't have git:**
1. Download git from [git-scm.com](https://git-scm.com/download/win)
2. Install with default options
3. Restart terminal and run clone command above

**OR download as ZIP:**
1. Go to: https://github.com/CiscoDevNet/meraki-magic-mcp-community
2. Click green "Code" button → "Download ZIP"
3. Extract to `C:\Users\YourName\meraki-magic-mcp-community`
4. Navigate there in terminal:
   ```cmd
   cd %USERPROFILE%\meraki-magic-mcp-community
   ```

### Step 4: Create Virtual Environment
**Command Prompt & PowerShell:**
```cmd
python -m venv .venv
```

### Step 5: Activate Virtual Environment

**Command Prompt:**
```cmd
.venv\Scripts\activate.bat
```

**PowerShell:**
```powershell
.venv\Scripts\Activate.ps1
```

**If you get an execution policy error in PowerShell:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.venv\Scripts\Activate.ps1
```

**You should see `(.venv)` appear in your terminal prompt.**

### Step 6: Install Dependencies
```cmd
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed meraki-X.X.X fastmcp-X.X.X ...
```

### Step 7: Prepare Environment Variables

Do not create a project `.env` file. The MCP server reads credentials from the process environment.

For Claude Desktop / Cursor (stdio), add them in the client config `env` block in [Claude Desktop Setup](#claude-desktop-setup).

For CLI, HTTP, or Docker, set them in your shell:

**Command Prompt:**
```cmd
set MERAKI_API_KEY=your_actual_api_key_here
set MERAKI_ORG_ID=your_org_id_here
set MERAKI_BASE_URL=https://api.meraki.com/api/v1
set READ_ONLY_MODE=true
```

**PowerShell:**
```powershell
$env:MERAKI_API_KEY="your_actual_api_key_here"
$env:MERAKI_ORG_ID="your_org_id_here"
$env:MERAKI_BASE_URL="https://api.meraki.com/api/v1"
$env:READ_ONLY_MODE="true"
```

Optional settings: `ENABLE_CACHING`, `CACHE_TTL_SECONDS`, `READ_ONLY_MODE`.

`MERAKI_BASE_URL` can be changed for regional Meraki Dashboard API deployments.

### Step 8: Get Absolute Path for Claude Config

**Command Prompt:**
```cmd
cd
```

**PowerShell:**
```powershell
pwd
```

**Copy the output** (e.g., `C:\Users\YourName\meraki-magic-mcp-community`)

**Note:** For Windows paths, you'll need to convert backslashes to forward slashes in the Claude config:
- Windows path: `C:\Users\YourName\meraki-magic-mcp-community`
- Claude config: `C:/Users/YourName/meraki-magic-mcp-community`

---

## Configuration

### Getting Your Meraki Credentials

#### API Key:
1. Log into [Meraki Dashboard](https://dashboard.meraki.com)
2. Go to: **Organization → Settings → Dashboard API access**
3. Click **Enable API access** (if not already enabled)
4. Click **Generate new API key**
5. **Copy the key** (you won't be able to see it again!)
6. Paste into the MCP client `env` block (see [Claude Desktop Setup](#claude-desktop-setup))

#### Organization ID:
1. In Meraki Dashboard, go to **Organization → Settings**
2. Look for **Organization ID** near the top
3. Copy the ID (format: `123456` or similar)
4. Paste into the MCP client `env` block (see [Claude Desktop Setup](#claude-desktop-setup))

---

## Claude Desktop Setup

### Step 1: Locate Claude Desktop Config File

**macOS:**
```bash
# Open config file location
open ~/Library/Application\ Support/Claude/
```

Config file: `claude_desktop_config.json`

**Windows:**
```cmd
# Navigate to config location
cd %APPDATA%\Claude
```

Config file: `claude_desktop_config.json`

**If file doesn't exist**, create it:
- **macOS:** `touch ~/Library/Application\ Support/Claude/claude_desktop_config.json`
- **Windows:** `type nul > %APPDATA%\Claude\claude_desktop_config.json`

### Step 2: Edit Claude Desktop Config

**macOS Example:**
```json
{
  "mcpServers": {
    "Meraki_Magic_MCP": {
      "command": "/Users/yourname/meraki-magic-mcp-community/.venv/bin/fastmcp",
      "args": [
        "run",
        "-t", "stdio",
        "/Users/yourname/meraki-magic-mcp-community/meraki-mcp-dynamic.py"
      ],
      "env": {
        "MERAKI_API_KEY": "your_api_key_here",
        "MERAKI_ORG_ID": "your_org_id_here",
        "MERAKI_BASE_URL": "https://api.meraki.com/api/v1",
        "MERAKI_PYTHON_SDK_CALLER": "MagicMCP CiscoDevNet",
        "READ_ONLY_MODE": "true"
      }
    }
  }
}
```

**Windows Example:**
```json
{
  "mcpServers": {
    "Meraki_Magic_MCP": {
      "command": "C:/Users/YourName/meraki-magic-mcp-community/.venv/Scripts/fastmcp.exe",
      "args": [
        "run",
        "-t", "stdio",
        "C:/Users/YourName/meraki-magic-mcp-community/meraki-mcp-dynamic.py"
      ],
      "env": {
        "MERAKI_API_KEY": "your_api_key_here",
        "MERAKI_ORG_ID": "your_org_id_here",
        "MERAKI_BASE_URL": "https://api.meraki.com/api/v1",
        "MERAKI_PYTHON_SDK_CALLER": "MagicMCP CiscoDevNet",
        "READ_ONLY_MODE": "true"
      }
    }
  }
}
```

**Important for Windows:**
- Use forward slashes `/` (not backslashes `\`) in JSON
- Include `.exe` extension for fastmcp
- Replace `YourName` with your actual Windows username
- If your path has spaces, use quotes around the whole path

### Step 3: Restart Claude Desktop

**macOS:**
- Press `Cmd + Q` to quit Claude Desktop
- Reopen Claude Desktop from Applications

**Windows:**
- Right-click Claude in system tray → Exit
- Reopen Claude Desktop from Start Menu

---

## HTTP Transport Mode

By default, the MCP server uses **stdio** transport for direct local connections (Claude Desktop, Cursor). For remote or containerized deployments, you can use **HTTP (StreamableHTTP)** transport.

### Transport Options

| Transport | Use Case | Config Value |
|-----------|----------|-------------|
| **stdio** | Local Claude Desktop / Cursor (default) | `MCP_TRANSPORT=stdio` |
| **http** | Remote/Docker deployments via StreamableHTTP | `MCP_TRANSPORT=http` |
| **sse** | Clients that only support Server-Sent Events | `MCP_TRANSPORT=sse` |

### Securing HTTP mode

The HTTP and SSE transports expose every tool, with your Meraki API key, to anyone who can reach the port. Set `MCP_AUTH_TOKEN` to require a bearer token on every request:

```bash
# Generate a random token once and keep it somewhere safe
export MCP_AUTH_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
```

Requests without `Authorization: Bearer <token>` get `401 Unauthorized`. Clients then need the same token; the mcp-remote examples below show how.

- Keep `MCP_HOST=127.0.0.1` (the default) unless other machines must connect. The server warns at startup when it listens on another address without a token.
- The token is sent in plain text over HTTP. For access across a network, put the server behind a reverse proxy that terminates TLS (HTTPS).
- Both servers enforce `MCP_AUTH_TOKEN` for Streamable HTTP and SSE when started with Python, the FastMCP CLI, or the exported ASGI app.

### Running in HTTP Mode (Local)

**Step 1: Export environment variables**

```bash
export MERAKI_API_KEY="your_api_key_here"
export MERAKI_ORG_ID="your_org_id_here"
export MCP_TRANSPORT=http
export MCP_HOST=127.0.0.1
export MCP_PORT=8000
export MCP_AUTH_TOKEN="your_token_here"  # optional on 127.0.0.1, required for remote access
```

**Step 2: Start the server**
```bash
# Activate virtual environment first
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate.bat  # Windows

python meraki-mcp-dynamic.py
```

The server starts on `http://127.0.0.1:8000/mcp`.

**Step 3: Connect Claude Desktop via mcp-remote**

Requires [Node.js](https://nodejs.org/) installed. Edit Claude Desktop config:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "Meraki_Magic_MCP": {
      "command": "npx",
      "args": [
        "-y", "mcp-remote", "http://127.0.0.1:8000/mcp",
        "--header", "Authorization:${AUTH_HEADER}"
      ],
      "env": {
        "AUTH_HEADER": "Bearer your_token_here"
      }
    }
  }
}
```

Replace `your_token_here` with the value of `MCP_AUTH_TOKEN`. Without a token, drop the `--header` arguments and the `env` block. The header argument has no space after the colon because some clients (including Claude Desktop on Windows) mangle spaces in `args`.

Restart Claude Desktop after updating the config.

### Remote / Network Deployment

To accept connections from other machines, bind to all interfaces and require a token:

```bash
export MCP_TRANSPORT=http
export MCP_HOST=0.0.0.0
export MCP_PORT=8000
export MCP_AUTH_TOKEN="your_token_here"
```

Remote clients connect via `http://<server-ip>:8000/mcp` with `Authorization: Bearer <token>`. Use a reverse proxy with TLS so the token and Meraki data are not sent in plain text.

---

## Docker Deployment

Docker provides the simplest way to deploy the MCP server remotely.

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) installed and running

### Quick Start

**Step 1: Export your credentials**
```bash
export MERAKI_API_KEY="your_api_key_here"
export MERAKI_ORG_ID="your_org_id_here"
```

Do not keep credentials in a project `.env` file. Compose interpolates `MERAKI_API_KEY` from the host environment (a leftover `.env` in the project directory is Compose's default interpolation source, not used by the Python server).

**Step 2: Build and run**
```bash
docker compose up -d
```

The server starts on `http://localhost:8000/mcp` using the dynamic MCP (full API). The default `docker-compose.yml` publishes the port on the host's loopback interface only, so other machines cannot connect.

To accept connections from other machines, publish on all interfaces and require a token:
```bash
export MCP_PUBLISH_HOST=0.0.0.0
export MCP_AUTH_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
docker compose up -d
```

**Step 3: Verify**
```bash
curl -s -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer $MCP_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}},"id":1}'
```

You should see a JSON response with `serverInfo.name` = "Meraki Magic MCP - Full API". Leave out the `Authorization` line if `MCP_AUTH_TOKEN` is not set.

**Step 4: Connect Claude Desktop**

Use the mcp-remote configuration from [Running in HTTP Mode](#running-in-http-mode-local) with the URL `http://localhost:8000/mcp`.

The container runs as UID 10001 with a private home directory for the Meraki SDK’s rate-limit cache. If you upgrade from an image that ran as root and the existing `meraki-cache` volume already holds cached files, it stays owned by root: the server logs a warning and runs without file caching. Recreate the volume with `docker compose down -v` (cached files are disposable) to restore it.

### Docker Configuration

Environment variables can be exported in the host shell (used by `docker compose`) or passed via `docker run -e`:

| Variable | Default | Description |
|----------|---------|-------------|
| `MCP_TRANSPORT` | `http` | Transport mode (http, stdio, sse) |
| `MCP_HOST` | `0.0.0.0` | Bind address inside the container |
| `MCP_AUTH_TOKEN` | *(unset)* | Bearer token required on every HTTP request; strongly recommended |
| `RESPONSE_CACHE_MAX_AGE_HOURS` | `24` | Maximum age of cached responses in hours. Use `0` to disable age-based cleanup. |
| `RESPONSE_CACHE_MAX_MB` | `100` | Response file quota in MiB. Use `0` to disable size-based cleanup. |
| `MCP_PUBLISH_HOST` | `127.0.0.1` | Host interface `docker compose` publishes port 8000 on; set `0.0.0.0` for remote access |
| `MCP_PORT` | `8000` | Bind port |
| `MCP_SERVER` | `dynamic` | Server file: `dynamic` (full API) or `manual` (curated tools) |
| `MERAKI_API_KEY` | *(required)* | Your Meraki Dashboard API key |
| `MERAKI_ORG_ID` | *(optional)* | Default organization ID |
| `MERAKI_BASE_URL` | `https://api.meraki.com/api/v1` | Dashboard API base URI for regional deployments |
| `MERAKI_PYTHON_SDK_CALLER` | `MagicMCP CiscoDevNet` | Identifier added to API request user agents |
| `READ_ONLY_MODE` | `true` | Blocks write operations unless explicitly set to `false` |

### Docker Commands

```bash
# Build image
docker build -t meraki-magic-mcp-community .

# Run with docker compose
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down

# Run manually (without compose); publishes on the host's loopback interface only
docker run -d --name meraki-mcp \
  -p 127.0.0.1:8000:8000 \
  -e MCP_AUTH_TOKEN="your-token" \
  -e MERAKI_API_KEY="your-key" \
  -e MERAKI_ORG_ID="your-org-id" \
  meraki-magic-mcp-community

# Use the manual (curated) server instead
docker run -d --name meraki-mcp \
  -p 127.0.0.1:8000:8000 \
  -e MCP_AUTH_TOKEN="your-token" \
  -e MERAKI_API_KEY="your-key" \
  -e MCP_SERVER=manual \
  meraki-magic-mcp-community
```

---

## Verification

### Test in Claude Desktop:

**1. Check MCP is loaded:**
```
What MCP servers are available?
```

You should see "Meraki_Magic_MCP" listed.

**2. Test basic query:**
```
Get a list of my Meraki organizations
```

**3. Test a more complex query:**
```
Show me all admins in my Meraki organization
```

**4. Check configuration:**
```
Use get_mcp_config to show me the MCP configuration
```

Expected response includes:
- `mode: "hybrid"`
- `pre_registered_tools`: a list of 12 tool names
- `total_available_methods`: the number of SDK methods (1039 with Meraki SDK 4.7)
- `api_key_configured: true`

### Common Test Queries:

```
Get all networks in my organization

Show me devices in my network named "Main Office"

Get switch ports for device serial ABC123

Show me network events for the last hour

List all wireless SSIDs
```

---

## Troubleshooting

### Issue: "Module 'meraki' not found"

**Solution:**
```bash
# Make sure virtual environment is activated
# macOS:
source .venv/bin/activate

# Windows (CMD):
.venv\Scripts\activate.bat

# Windows (PowerShell):
.venv\Scripts\Activate.ps1

# Then reinstall
pip install -r requirements.txt
```

### Issue: "MCP server not showing up in Claude"

**Solutions:**
1. **Verify config file location:**
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`

2. **Verify JSON is valid:**
   - Use [jsonlint.com](https://jsonlint.com) to validate
   - Check for missing commas, quotes, brackets

3. **Verify paths are correct:**
   - Use absolute paths (not relative like `~/` or `.`)
   - Windows: Use forward slashes `/` and include `.exe`

4. **Restart Claude Desktop completely:**
   - Quit from menu/system tray, don't just close window

### Issue: "API Key Invalid" or "401 Unauthorized"

**Solutions:**
1. **Regenerate API key:**
   - Go to Meraki Dashboard → Organization → Settings → Dashboard API access
   - Generate new key
   - Update `MERAKI_API_KEY` in the MCP client `env` block (stdio) or re-export it in your shell (CLI/Docker)

2. **Check the process environment:**
   ```bash
   # macOS/Linux:
   echo "$MERAKI_API_KEY"

   # Windows (Command Prompt):
   echo %MERAKI_API_KEY%

   # Windows (PowerShell):
   echo $env:MERAKI_API_KEY
   ```

   For Claude Desktop / Cursor, confirm `MERAKI_API_KEY` is set in the client config `env` object.

3. **Verify no extra spaces in the client `env` value:**
   ```json
   "MERAKI_API_KEY": "abc123"
   ```
   Avoid leading/trailing spaces in the JSON string.

### Issue: Python version too old

**Check version:**
```bash
python --version
# or
python3 --version
```

**Needs to be 3.13 or higher.**

**Upgrade Python:**
- **macOS:** `brew upgrade python` or download from python.org
- **Windows:** Download latest from python.org

### Issue: "fastmcp: command not found" or "fastmcp.exe not found"

**Solution:**
```bash
# Verify fastmcp is installed
# macOS:
ls .venv/bin/fastmcp

# Windows:
dir .venv\Scripts\fastmcp.exe

# If missing, reinstall:
pip install --force-reinstall fastmcp
```

### Issue: macOS "Operation not permitted" when Claude Desktop starts the server

**Symptom** (in the Claude Desktop MCP log):
```
Fatal Python error: init_import_site: Failed to import the site module
PermissionError: [Errno 1] Operation not permitted: '.../Documents/.../.venv/pyvenv.cfg'
```

**Cause:** macOS privacy protection blocks Claude Desktop from reading protected folders such as `Documents`, `Desktop` and `Downloads`, so Python cannot read the virtual environment.

**Solution:** Keep the project outside those folders (for example `~/meraki-magic-mcp-community`), or grant Claude access under System Settings → Privacy & Security → Files and Folders. If you move the project, recreate the virtual environment as described in the next issue.

### Issue: "spawn .../.venv/bin/fastmcp ENOENT" after moving the project folder

**Cause:** A virtual environment stores absolute paths, so it breaks when the project folder is moved or renamed.

**Solution:** Recreate it in the new location and update the paths in `claude_desktop_config.json`:
```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Issue: "Read-only file system: '.meraki_cache'" or a cache directory warning

**Cause:** Large responses are saved under `RESPONSE_CACHE_DIR`, which defaults to `.meraki_cache` inside the project folder. Some MCP hosts run servers in a sandbox where that folder is not writable.

**Behavior:** The server still starts. It logs `WARNING: response cache directory ... is unusable` and runs with file caching disabled, so large responses are returned in full instead of being saved and previewed. Lower `MAX_PER_PAGE` or use narrower queries if they are too large for the conversation.

**Solution:** Point the cache at a writable location in the MCP client `env` block, or turn file caching off:
```json
"env": {
  "RESPONSE_CACHE_DIR": "/tmp/meraki_cache"
}
```
```json
"env": {
  "ENABLE_FILE_CACHING": "false"
}
```

### Issue: Windows PowerShell execution policy error

**Solution:**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

Then try activating virtual environment again.

### Issue: "Network timeout" or "Rate limit exceeded"

**Solutions:**
1. **Check internet connection**

2. **Verify API key has proper permissions**

3. **Enable rate limit handling** (already enabled by default):
   ```bash
   # Already the default; set in MCP client env or process environment if needed
   ENABLE_CACHING=true
   ```

4. **Increase cache TTL to reduce API calls:**
   ```bash
   export CACHE_TTL_SECONDS=600  # 10 minutes instead of 5
   ```

### Issue: Hitting conversation length limits in Claude

**This should be fixed in the current version!**

If you still experience this:
1. **Verify you're using `meraki-mcp-dynamic.py`** (not the old version)
2. **Restart Claude Desktop** after any changes
3. **Check the version has `call_meraki_api` tool:**
   ```
   Use search_methods with keyword="test" to verify
   ```

---

## Getting Help

### Check Logs

**macOS:**
```bash
# Claude Desktop logs
tail -f ~/Library/Logs/Claude/mcp*.log
```

**Windows:**
```cmd
# Navigate to logs
cd %LOCALAPPDATA%\Claude\logs
dir
```

### Enable Debug Output

Add `DEBUG=true` to the MCP client `env` block (or export it in the process environment):
```json
"DEBUG": "true"
```

Restart Claude Desktop and check logs for detailed output.

### Report Issues

If you encounter issues:
1. Check [Troubleshooting](#troubleshooting) section above
2. Search existing [GitHub Issues](https://github.com/CiscoDevNet/meraki-magic-mcp-community/issues)
3. Create new issue with:
   - Operating system and version
   - Python version (`python --version`)
   - Error message (full text)
   - Steps to reproduce

---

## Next Steps

Once installed:
- Read [QUICKSTART.md](QUICKSTART.md) for usage examples
- See [OPTIMIZATIONS.md](OPTIMIZATIONS.md) for performance features
- Check [UPDATE_GUIDE.md](UPDATE_GUIDE.md) to keep MCP current

**Welcome to Meraki Magic MCP!** 🎉
