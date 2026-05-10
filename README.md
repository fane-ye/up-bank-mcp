# Up Bank MCP (Unofficial)

MCP server exposing the full Up Bank API as tools — balances, transactions, categories, tags, webhooks.
https://developer.up.com.au/

## Architecture

This server runs **locally on your device**. All requests to the Up Bank API are made directly from your machine — your personal access token never leaves your device and is never sent to a third party.

However, to answer your questions, the LLM you connect this server to will retrieve your banking data (account balances, transactions, etc.) and include it in the conversation. This data is sent to whichever LLM provider you are using (e.g. Anthropic's servers if using Claude). You should be comfortable with your LLM provider's data handling and privacy policy before using this tool.

**For maximum privacy**, consider connecting to a locally running LLM such as [Ollama](https://ollama.com), which keeps all data — your token, your banking data, and your conversation — entirely on your own device.

```
Your Device
┌─────────────────────────────────────────────────┐
│                                                 │
│   Claude Desktop / MCP Client                  │
│          │                                      │
│          │  MCP (stdio)                         │
│          ▼                                      │
│   Up Bank MCP Server  ──────────────────────►  │  Up Bank API
│   (this server)       HTTPS + your token        │  (api.up.com.au)
│          │                                      │
└──────────┼──────────────────────────────────────┘
           │ banking data
           ▼
    LLM Provider
    (Anthropic / local Ollama / etc.)
```

## Tools

| Tool | Description |
|---|---|
| `ping` | Verify token and API connectivity |
| `list_accounts` | List all accounts (filter by type/ownership) |
| `get_account` | Get a single account by ID |
| `list_transactions` | List transactions across all accounts (auto-paginated) |
| `get_transaction` | Get a single transaction by ID |
| `list_account_transactions` | List transactions for a specific account (auto-paginated) |
| `list_categories` | List all spending categories |
| `get_category` | Get a single category by ID |
| `update_transaction_category` | Set or clear the category on a transaction |
| `list_tags` | List all tags (auto-paginated) |
| `add_tags_to_transaction` | Add tags to a transaction |
| `remove_tags_from_transaction` | Remove tags from a transaction |
| `list_attachments` | List all receipt attachments (auto-paginated) |
| `get_attachment` | Get a single attachment by ID |
| `list_webhooks` | List configured webhooks |
| `get_webhook` | Get a single webhook by ID |
| `create_webhook` | Create a new webhook |
| `delete_webhook` | Delete a webhook |
| `ping_webhook` | Send a test ping to a webhook |
| `list_webhook_delivery_logs` | Get delivery history for a webhook |

## Setup

### Option 1 — Claude Desktop (MCPB bundle, recommended)

1. Get your Up Bank token from [api.up.com.au](https://api.up.com.au)
2. Drag `up-bank-0.1.0.mcpb` onto Claude Desktop
3. Enter your token in the install dialog — stored securely in your OS keychain
4. Done — no Python or uv install required

To rebuild the bundle after making changes:
```bash
mcpb pack
```

### Option 2 — Any MCP client (manual config)

Add to your MCP client's config (e.g. Claude Desktop `claude_desktop_config.json` or Claude Code):

```json
{
  "mcpServers": {
    "up-bank": {
      "command": "uv",
      "args": ["--directory", "/path/to/up-bank-mcp", "run", "python", "server/main.py"],
      "env": {
        "UP_PAT": "up:yeah:your-token-here"
      }
    }
  }
}
```

### Option 3 — Run directly

```bash
cd up-bank-mcp
export UP_PAT="up:yeah:your-token-here"
uv run python server/main.py
```

## Auth

All options use the `UP_PAT` environment variable. Get your token at [api.up.com.au](https://api.up.com.au) — it looks like `up:yeah:xxxxxxxxxxxx`.

## Development

### Prerequisites

**uv** — Python package manager (replaces pip + venv):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**mcpb** — MCP bundle CLI:
```bash
npm install -g @anthropic-ai/mcpb
```

**Node.js** is required for mcpb. Install via [nodejs.org](https://nodejs.org) or `brew install node`.

### Run locally

```bash
cd up-bank-mcp
uv sync                            # install dependencies into .venv
export UP_PAT="up:yeah:your-token-here"
uv run python server/main.py       # start the MCP server over stdio
```

To test interactively with the MCP inspector:
```bash
npx @modelcontextprotocol/inspector uv run python server/main.py
```

### Pack the MCPB bundle

```bash
mcpb validate manifest.json        # check manifest against schema
mcpb pack                          # produces up-bank-0.1.0.mcpb
```

The `.mcpb` file can be dragged into Claude Desktop to install. Re-pack after any code changes before distributing.
