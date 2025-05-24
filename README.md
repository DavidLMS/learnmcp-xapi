# learnmcp-xapi v1.0

MCP proxy server for xAPI Learning Record Store integration.

## Features

- **xAPI 1.0.3 compliant** statement recording and retrieval
- **JWT authentication** with RS256/HS256 support
- **Rate limiting** (30 requests/minute per IP)
- **Privacy by design** (hashed actor UUIDs in logs)
- **LRS retry logic** with exponential backoff
- **FastMCP integration** for easy LLM tool integration

## Quick Start

1. **Install dependencies**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your LRS and JWT settings
   ```

3. **Run locally**:
   ```bash
   python -m learnmcp_xapi.main
   ```

4. **Test the server**:
   The server runs as an MCP server and will be accessible to Claude Desktop when properly configured (see below).

## MCP Tools

- `record_xapi_statement` - Record learning evidence
- `get_xapi_statements` - Retrieve actor's statements  
- `list_available_verbs` - Get available verb aliases

## Testing

```bash
pytest -q
```

## Docker

```bash
docker build -t learnmcp-xapi:1.0 .
docker run -it --env-file .env learnmcp-xapi:1.0
```

## LRS Setup Example: LRSQL

This application works with any xAPI 1.0.3 compliant LRS. Here's how to set up [LRSQL](https://github.com/yetanalytics/lrsql) as an example:

### 1. Download and Start LRSQL

```bash
# Download latest release
wget https://github.com/yetanalytics/lrsql/releases/latest/download/lrsql-1.2.17-standalone.tar.gz
tar -xzf lrsql-1.2.17-standalone.tar.gz
cd lrsql-1.2.17-standalone

# Start with SQLite (simplest option)
./bin/run_sqlite.sh
```

### 2. Create API Credentials

1. Open http://localhost:8080 in your browser
2. Login with default admin credentials (check startup logs)
3. Navigate to "Credentials" → "Create New Credential"
4. Note down the **API Key** and **API Secret**

### 3. Configure learnmcp-xapi

Update your `.env` file:

```env
LRS_ENDPOINT=http://localhost:8080
LRS_KEY=your-api-key-here
LRS_SECRET=your-api-secret-here
JWT_ALGORITHM=HS256
JWT_SECRET=test-secret-key-for-development
```

### 4. Test Integration

1. **Start LRSQL** (see setup above)
2. **Start learnmcp-xapi**: `python -m learnmcp_xapi.main`  
3. **Configure Claude Desktop** with the JSON above
4. **Restart Claude Desktop**
5. **Test in Claude**: Ask Claude to "Record that I practiced Linear Algebra with level 2"

The statement should appear in LRSQL's web interface under "Statements".

### Other LRS Compatibility

This application follows xAPI 1.0.3 standards and should work with:
- **Learning Locker** (Community/Commercial)
- **TinCan LRS** 
- **Watershed LRS**
- **Any xAPI-compliant LRS**

Simply update `LRS_ENDPOINT`, `LRS_KEY`, and `LRS_SECRET` in your `.env` file.

## Configuration

See `.env.example` for all available environment variables.

## Connecting to Claude Desktop

To use this MCP server with Claude Desktop app:

### 1. Locate Claude Desktop Config

Find your Claude Desktop configuration file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### 2. Add MCP Server Configuration

Edit the config file to include the learnmcp-xapi server. **Important**: Use the absolute path to your Python executable and project directory:

**Option 1: Using the run_server.py script (Recommended)**

```json
{
  "mcpServers": {
    "learnmcp-xapi": {
      "command": "/path/to/your/python",
      "args": [
        "/absolute/path/to/learnmcp-xapi/run_server.py"
      ],
      "env": {
        "LRS_ENDPOINT": "http://localhost:8080",
        "LRS_KEY": "your-api-key-here",
        "LRS_SECRET": "your-api-secret-here",
        "JWT_ALGORITHM": "HS256",
        "JWT_SECRET": "test-secret-key-for-development"
      }
    }
  }
}
```

**Option 2: Using module import**

```json
{
  "mcpServers": {
    "learnmcp-xapi": {
      "command": "/path/to/your/python",
      "args": [
        "-m", "learnmcp_xapi.main"
      ],
      "cwd": "/absolute/path/to/learnmcp-xapi",
      "env": {
        "PYTHONPATH": "/absolute/path/to/learnmcp-xapi",
        "LRS_ENDPOINT": "http://localhost:8080",
        "LRS_KEY": "your-api-key-here",
        "LRS_SECRET": "your-api-secret-here",
        "JWT_ALGORITHM": "HS256",
        "JWT_SECRET": "test-secret-key-for-development"
      }
    }
  }
}
```

**How to find your paths:**

**macOS/Linux:**
- **Python path**: `which python3` or `which python`
- **Project path**: `pwd` inside the learnmcp-xapi directory
- **Common Python locations**:
  - Homebrew (macOS): `/opt/homebrew/bin/python3`
  - Anaconda: `/Users/username/anaconda3/bin/python`
  - System: `/usr/bin/python3`

**Windows:**
- **Python path**: `where python` in Command Prompt
- **Project path**: `cd` to learnmcp-xapi folder, then `echo %cd%`
- **Common Python locations**:
  - Anaconda: `C:\Users\username\anaconda3\python.exe`
  - Python.org: `C:\Users\username\AppData\Local\Programs\Python\Python311\python.exe`
  - Microsoft Store: `C:\Users\username\AppData\Local\Microsoft\WindowsApps\python.exe`

**Example for Windows:**
```json
{
  "mcpServers": {
    "learnmcp-xapi": {
      "command": "C:\\Users\\username\\anaconda3\\python.exe",
      "args": [
        "C:\\path\\to\\learnmcp-xapi\\run_server.py"
      ],
      "env": {
        "LRS_ENDPOINT": "http://localhost:8080",
        "LRS_KEY": "your-api-key-here",
        "LRS_SECRET": "your-api-secret-here",
        "JWT_ALGORITHM": "HS256",
        "JWT_SECRET": "test-secret-key-for-development"
      }
    }
  }
}
```

### 3. Restart Claude Desktop

1. **Quit** Claude Desktop completely
2. **Restart** the application
3. Look for the **🔨 hammer icon** in the input area

### 4. Test the Connection

1. **Look for the hammer icon** 🔨 in Claude Desktop's input area
2. **Test with a simple request**: "List available learning verbs"
3. **Record a learning activity**: "Record that I achieved mastery of Linear Algebra with level 3"

**Example conversation:**
```
You: List the available learning verbs
Claude: [Uses list_available_verbs tool to show: experienced, practiced, achieved, mastered]

You: Record that I achieved mastery of Python basics with level 3
Claude: [Uses record_xapi_statement tool] I've successfully recorded your achievement of Python basics with mastery level 3 in the learning record store.
```

The statement should appear in LRSQL's web interface under "Statements" at `http://localhost:8080/admin/ui/browser`.

### Available Tools in Claude

Once connected, Claude will have access to:

- **📝 record_xapi_statement**: Log learning activities and achievements
- **📊 get_xapi_statements**: Retrieve your learning history  
- **📋 list_available_verbs**: See available learning verbs

### Troubleshooting

#### Common Issues

**No 🔨 hammer icon appears:**
- Verify JSON syntax in `claude_desktop_config.json` is valid
- Use absolute paths for `command` and file paths (no `~` or relative paths)
- Ensure Python dependencies are installed: `pip install -r requirements.txt`
- Check Python path with `which python` or `which python3`

**"spawn python ENOENT" error:**
- Use full path to Python executable (e.g., `/usr/bin/python3`)
- Don't use just `python` - specify the complete path

**"ModuleNotFoundError: No module named 'learnmcp_xapi'":**
- Use Option 1 with `run_server.py` script (recommended)
- Or add `PYTHONPATH` environment variable as shown in Option 2

**"LRS unavailable" error:**
- Verify LRSQL is running on `http://localhost:8080`
- Check API credentials are correct in LRSQL admin interface
- Test endpoint: `curl -u "key:secret" http://localhost:8080/xapi/statements`

**Connection issues:**
- Restart Claude Desktop after config changes
- Check logs: `~/Library/Logs/Claude/mcp.log` (macOS) or `%APPDATA%\Claude\logs\mcp.log` (Windows)
- Verify LRS is running and accessible

## License

MIT