# learnmcp-xapi v1.0

MCP (Model Context Protocol) server for xAPI Learning Record Store integration with simple configuration.

## Features

- **xAPI 1.0.3 compliant** statement recording and retrieval
- **Simple configuration** with unique actor UUID per client
- **LRS security** via API key authentication
- **Rate limiting** (30 requests/minute per IP)
- **Privacy by design** (configurable actor UUID)
- **LRS retry logic** with exponential backoff
- **MCP tools** for seamless LLM integration

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
   # Edit .env with your LRS settings and unique ACTOR_UUID
   ```

3. **Run the server**:
   ```bash
   python -m learnmcp_xapi.main
   ```
   
   The server will start as an MCP server with:
   - Health check at http://localhost:8000/health
   - MCP tools accessible via MCP protocol

4. **Test the server**:
   ```bash
   # Health check
   curl http://localhost:8000/health
   
   # For MCP tool testing, use Claude Desktop
   # See "Connecting to Claude Desktop" section below
   ```

## MCP Tools

- `record_xapi_statement` - Record learning evidence
- `get_xapi_statements` - Retrieve actor's statements
- `list_available_verbs` - Get available verb aliases

## Additional Endpoints

- `GET /health` - Health check endpoint

## Testing

```bash
pytest -q
```

## Docker Deployment

```bash
# Build image
docker build -t learnmcp-xapi:1.0 .

# Run with environment variables
docker run -p 8000:8000 \
  -e LRS_ENDPOINT=http://localhost:8080 \
  -e LRS_KEY=your-lrs-key \
  -e LRS_SECRET=your-lrs-secret \
  -e ACTOR_UUID=student-unique-id-here \
  learnmcp-xapi:1.0
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
ENV=development
LRS_ENDPOINT=http://localhost:8080
LRS_KEY=your-api-key-here
LRS_SECRET=your-api-secret-here
ACTOR_UUID=student-alice-12345
```

### 4. Test Integration

1. **Start LRSQL** (see setup above)
2. **Start learnmcp-xapi**: `python -m learnmcp_xapi.main`  
3. **Configure Claude Desktop** (see below)
4. **Test via Claude Desktop**:
   - Ask Claude: "Record that I practiced Linear Algebra with level 2"
   - Claude will use the MCP tools to record the statement

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

### 1. Locate Claude Desktop Config

Find your Claude Desktop configuration file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

### 2. Add MCP Server Configuration

Edit the config file to include the learnmcp-xapi server:

```json
{
  "mcpServers": {
    "learnmcp-xapi": {
      "command": "/absolute/path/to/python",
      "args": [
        "/absolute/path/to/learnmcp-xapi/run_server.py"
      ],
      "env": {
        "ENV": "development",
        "LRS_ENDPOINT": "http://localhost:8080",
        "LRS_KEY": "your-lrsql-api-key",
        "LRS_SECRET": "your-lrsql-api-secret",
        "ACTOR_UUID": "student-alice-12345",
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

**Important**: Each student should use a **unique ACTOR_UUID** in their configuration. This UUID identifies the student in the learning records.

**How to find your paths:**
- **Python path**: `which python3` (macOS/Linux) or `where python` (Windows)
- **Project path**: `pwd` inside the learnmcp-xapi directory

### 3. Testing the Connection

1. **Start your LRS** (e.g., LRSQL on port 8080)
2. **Start learnmcp-xapi server**: `python -m learnmcp_xapi.main`
3. **Restart Claude Desktop** after config changes
4. **Look for the 🔨 hammer icon** in Claude Desktop's input area
5. **Test the tools**:
   - "List available learning verbs"
   - "Record that I practiced Python with level 2"

### 4. Available Tools in Claude

Once connected, Claude will have access to:

- **📝 record_xapi_statement**: Log learning activities and achievements
  - Params: verb, object_id, level (optional), extras (optional)
  
- **📊 get_xapi_statements**: Retrieve your learning history
  - Params: verb, object_id, since, until, limit (all optional)
  
- **📋 list_available_verbs**: See available learning verbs
  - Returns: {"experienced": "http://...", "practiced": "http://...", ...}

### 5. Multiple Students Setup

Each student should have their own unique configuration:

**Student Alice:**
```json
{
  "env": {
    "ACTOR_UUID": "student-alice-12345",
    "LRS_ENDPOINT": "https://school.edu/lrs"
  }
}
```

**Student Bob:**
```json
{
  "env": {
    "ACTOR_UUID": "student-bob-67890",
    "LRS_ENDPOINT": "https://school.edu/lrs"
  }
}
```

This way, each student's learning activities are tracked separately in the same LRS.

### 6. Troubleshooting

**No 🔨 hammer icon appears:**
- Verify JSON syntax in claude_desktop_config.json
- Use absolute paths (no ~ or relative paths)
- Check Python path: `which python3`
- Ensure dependencies installed: `pip install -r requirements.txt`

**"ACTOR_UUID is required" error:**
- Make sure ACTOR_UUID is set in your Claude Desktop config
- Use a unique identifier for each student
- Restart Claude Desktop after config changes

**"LRS unavailable" errors:**
- Verify LRS is running (LRSQL: http://localhost:8080)
- Check LRS_KEY and LRS_SECRET are correct
- Test LRS directly: `curl -u "key:secret" http://localhost:8080/xAPI/statements`

**Configuration issues:**
- Check server logs for startup errors
- Verify health endpoint: `curl http://localhost:8000/health`
- Check Claude logs: `~/Library/Logs/Claude/mcp.log` (macOS)

## Security Model

### How Student Identity Works

1. **Physical Isolation**: Each student runs Claude Desktop on their own device
2. **Local Configuration**: Each student sets their unique ACTOR_UUID in their local config
3. **LRS Protection**: The LRS is protected by API keys and HTTPS
4. **Statement Tracking**: Each statement is tagged with the student's ACTOR_UUID

### Security Benefits

- ✅ **No shared secrets**: No JWT tokens to manage or expire
- ✅ **Simple setup**: Just configure ACTOR_UUID per student
- ✅ **LRS security**: Existing LRS authentication protects the data
- ✅ **Audit trail**: Each statement clearly identifies the student
- ✅ **Self-contained**: Each student's setup is independent

### Production Recommendations

- Use **HTTPS** for LRS_ENDPOINT in production
- Use **unique ACTOR_UUIDs** for each student (e.g., student ID numbers)
- Configure **strong LRS credentials** and rotate them regularly
- Monitor **LRS access logs** for unusual activity
- Use **institutional LRS** rather than local development setup

## Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ENV` | No | `development` | Environment (development/production) |
| `LRS_ENDPOINT` | Yes | - | LRS base URL (use HTTPS in production) |
| `LRS_KEY` | Yes | - | LRS API key |
| `LRS_SECRET` | Yes | - | LRS API secret |
| `ACTOR_UUID` | Yes | - | Unique student identifier |
| `RATE_LIMIT_PER_MINUTE` | No | `30` | Requests per minute per IP |
| `MAX_BODY_SIZE` | No | `16384` | Max request body size (bytes) |
| `LOG_LEVEL` | No | `INFO` | Logging level |

## Integration with MCP Clients

This MCP server can be integrated with any MCP-compatible client:

- **Claude Desktop** (recommended)
- **Custom MCP clients**
- **Educational platforms** using MCP protocol
- **AI tutoring systems** via MCP

**MCP Client Requirements:**
1. Support MCP protocol (SSE + JSON-RPC)
2. Set unique ACTOR_UUID in environment configuration
3. Handle MCP tool call/response format
4. Support async tool execution

## Production Deployment

### Docker Compose

```yaml
version: '3.8'
services:
  learnmcp-xapi:
    build: .
    ports:
      - "8000:8000"
    environment:
      - ENV=production
      - LRS_ENDPOINT=https://your-production-lrs.com
      - LRS_KEY=${LRS_KEY}
      - LRS_SECRET=${LRS_SECRET}
      - ACTOR_UUID=${ACTOR_UUID}
    restart: unless-stopped
```

### Environment-Specific Setup

**Development:**
```bash
export ENV=development
export LRS_ENDPOINT=http://localhost:8080
export ACTOR_UUID=dev-student-12345
```

**Production:**
```bash
export ENV=production
export LRS_ENDPOINT=https://lrs.school.edu
export ACTOR_UUID=student-alice-institutional-id
```

## License

MIT