# Agent Team MCP

Four coding agents — UI/UX, backend, frontend, and a code reviewer that
fixes what it finds — hosted behind an MCP server. Use them from Claude
Code as subagents, or run them against any local model through the MCP
server here.

## Agents (`agents/*.md`)
Each file is a Claude Code subagent: YAML frontmatter + a plain-text system
prompt. Copy `agents/` into `.claude/agents/` in any project (or into
`~/.claude/agents/` to use them everywhere) and restart Claude Code.

- `ui-ux-agent` — flows, layout, color, typography, spacing, interaction states
- `backend-agent` — APIs, schema, auth, business logic
- `frontend-agent` — components, state, routing, styling
- `code-review-agent` — reviews the others' code and fixes what it finds

Suggested order: ui-ux-agent -> backend-agent -> frontend-agent -> code-review-agent.

## MCP server (`server.py`)
Hosts the same four agents so any MCP client, including local models, can
use them — not just Claude Code.

### Setup
    git clone https://github.com/rhida1129/agent-team-mcp.git
    cd agent-team-mcp
    pip install -r requirements.txt
    ollama serve && ollama pull llama3.1     # or any OpenAI-compatible server

### Tools
- `agent_team_list` — list agents
- `agent_team_get_prompt` — get an agent's system prompt
- `agent_team_run` — run one agent on a task
- `agent_team_pipeline` — run all four in order, each seeing the previous output

Also exposes a resource (`agent://<name>`) and a prompt (`use_agent`).

### Connect a client (stdio)
```json
{
  "mcpServers": {
    "agent-team": {
      "command": "python",
      "args": ["/full/path/to/agent-team-mcp/server.py"],
      "env": {
        "AGENT_LLM_BASE_URL": "http://localhost:11434/v1",
        "AGENT_LLM_MODEL": "llama3.1"
      }
    }
  }
}
```
For Claude Code: `claude mcp add agent-team -- python /full/path/to/server.py`

### Editing agents
Edit or add `.md` files in `agents/`. Changes apply immediately — no restart needed.
