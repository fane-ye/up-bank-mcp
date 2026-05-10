# ADR 001 — Use MCPB for server distribution

**Date:** 2026-05-10
**Status:** Accepted

## Context

The Up Bank MCP server needs to be distributed to users who want to connect their Up Bank account to an AI assistant. The primary target audience includes non-technical users who should not need to install Python, manage virtual environments, or edit config files manually.

The server must also securely handle the user's Up Bank personal access token (PAT), which grants full read access to their banking data.

## Decision

Distribute the server as an **MCPB bundle** (`.mcpb` file).

## Rationale

MCPB was chosen for the following reasons:

**Zero-friction installation for non-technical users.** Installation requires only dragging the `.mcpb` file into Claude Desktop or double-clicking it. No terminal, no Python install, no package managers. This is equivalent to installing a browser extension or a mobile app.

**Managed runtime.** With `server.type: "uv"`, Claude Desktop automatically manages the Python runtime and all dependencies. The user never needs to install or configure anything beyond the app itself.

**Secure token handling.** Claude Desktop's MCPB integration surfaces a native UI prompt for the Up Bank PAT during installation and [encyrpts it using the OS keychain](https://support.claude.com/en/articles/10949351-getting-started-with-local-mcp-servers-on-claude-desktop#h_c93f75cb39). The token is never written to a plaintext config file and is injected into the server process as an environment variable at runtime. 

**Single known compatible client.** At the time of writing, Claude Desktop (macOS, Windows) is the only client the author is aware of that supports MCPB installation and the associated secure `user_config` token flow. This is an accepted constraint — the MCPB format is an emerging standard.

## Consequences

- Users on other MCP clients (Claude Code, Cursor, Zed, etc.) must configure the server manually using the instructions in the README. This is an acceptable trade-off as those users are generally more technical.
- The bundle must be repacked (`mcpb pack`) after any changes to the server code before distributing a new version.
- Distribution currently requires sharing the `.mcpb` file directly (e.g. via GitHub Releases). There is no centralised MCPB marketplace at this time.

## Alternatives considered

**Local stdio via manual JSON config** — requires users to edit config files and manage the token as plaintext in JSON. Rejected for non-technical users due to friction and security concerns.

**Remote HTTP server** — would enable Claude web access but requires hosting infrastructure, exposes UP PAT to a server the end user does not control, and significantly increases operational complexity. Rejected as out of scope for a personal tool.

**Node.js rewrite** — Node ships with Claude Desktop, eliminating the uv dependency. Rejected because the server is already implemented in Python and `server.type: "uv"` achieves the same zero-dependency outcome.
