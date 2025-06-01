# Documentation

This directory contains auto-generated documentation for LearnMCP-xAPI.

## ⚠️ Important: Documentation Update Required

The documentation in this directory was generated before the plugin architecture implementation and needs to be regenerated to reflect the new plugin system.

## Plugin Architecture Changes

The following modules have been updated and their documentation should be regenerated:

- **New Plugin System**:
  - `learnmcp_xapi.plugins.base` - Base plugin interface
  - `learnmcp_xapi.plugins.registry` - Plugin registry
  - `learnmcp_xapi.plugins.factory` - Plugin factory
  - `learnmcp_xapi.plugins.lrsql` - LRS SQL plugin
  - `learnmcp_xapi.plugins.ralph` - Ralph LRS plugin

- **Updated Core Modules**:
  - `learnmcp_xapi.config` - Now supports plugin configuration
  - `learnmcp_xapi.mcp.core` - Now uses plugin system instead of direct LRS client
  - `learnmcp_xapi.main` - Now registers and manages plugins

- **Legacy Modules** (deprecated but maintained for compatibility):
  - `learnmcp_xapi.mcp.lrs_client` - Replaced by plugin system

## Regenerating Documentation

To regenerate the documentation after the plugin architecture changes:

```bash
# Install documentation dependencies if needed
pip install pdoc3  # or whatever documentation generator is used

# Generate new documentation
# (Replace with actual command used for this project)
pdoc --html --output-dir docs learnmcp_xapi

# Or if using a different tool, use the appropriate command
```

## New Documentation Topics to Include

The updated documentation should cover:

1. **Plugin Architecture Overview**
2. **Available LRS Plugins** (LRS SQL, Ralph)
3. **Plugin Configuration** (environment variables, config files)
4. **Authentication Methods** (Basic Auth, OIDC)
5. **Creating Custom Plugins**
6. **Migration Guide** from legacy configuration
7. **Docker Deployment** with different plugins

## Configuration Examples

The documentation should include examples for:

- LRS SQL plugin configuration
- Ralph plugin with Basic Auth
- Ralph plugin with OIDC
- File-based configuration
- Docker deployment scenarios