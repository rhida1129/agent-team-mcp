"""Agent Team MCP server.

Hosts four agents (frontend, backend, ui-ux, code-review) defined as markdown
files in ./agents. Any MCP client can list them, fetch their system prompts,
or run them against any OpenAI-compatible model (Ollama, LM Studio,
llama.cpp server, vLLM, etc.) so they can be used by local models too.

Config (environment variables):
  AGENTS_DIR         folder of agent .md files      (default: ./agents)
  AGENT_LLM_BASE_URL OpenAI-compatible base URL     (default: http://localhost:11434/v1)
  AGENT_LLM_MODEL    model name                     (default: llama3.1)
  AGENT_LLM_API_KEY  API key if needed              (default: none)
"""
import os
from pathlib import Path
from typing import Dict, Optional

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

AGENTS_DIR = Path(os.environ.get("AGENTS_DIR", Path(__file__).parent / "agents"))
BASE_URL = os.environ.get("AGENT_LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/")
MODEL = os.environ.get("AGENT_LLM_MODEL", "llama3.1")
API_KEY = os.environ.get("AGENT_LLM_API_KEY", "")
PIPELINE = ["ui-ux-agent", "backend-agent", "frontend-agent", "code-review-agent"]

mcp = FastMCP("agent_team_mcp")


def _parse(path: Path) -> Dict[str, str]:
    """Split a markdown file into frontmatter fields and the prompt body."""
    text = path.read_text(encoding="utf-8")
    meta: Dict[str, str] = {}
    body = text
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            body = text[end + 4:].strip()
    meta.setdefault("name", path.stem)
    meta["prompt"] = body
    return meta


def _agents() -> Dict[str, Dict[str, str]]:
    # Re-read every call so edits to the .md files apply without a restart.
    return {a["name"]: a for a in (_parse(p) for p in sorted(AGENTS_DIR.glob("*.md")))}


def _get(name: str) -> Dict[str, str]:
    agents = _agents()
    if name not in agents:
        raise ValueError(f"Unknown agent '{name}'. Available: {', '.join(agents) or 'none'}. "
                         f"Call agent_team_list to see them.")
    return agents[name]


async def _chat(system: str, user: str) -> str:
    headers = {"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
    payload = {"model": MODEL, "messages": [
        {"role": "system", "content": system}, {"role": "user", "content": user}]}
    try:
        async with httpx.AsyncClient(timeout=300) as client:
            r = await client.post(f"{BASE_URL}/chat/completions", json=payload, headers=headers)
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    except httpx.ConnectError:
        raise RuntimeError(f"Could not reach the model server at {BASE_URL}. Start it (for example "
                           f"`ollama serve`) or set AGENT_LLM_BASE_URL.")
    except httpx.HTTPStatusError as e:
        raise RuntimeError(f"Model server returned {e.response.status_code}: {e.response.text[:200]}. "
                           f"Check that model '{MODEL}' exists (set AGENT_LLM_MODEL).")


READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
RUN = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=False, openWorldHint=True)


@mcp.tool(name="agent_team_list", annotations=READ)
async def agent_team_list() -> str:
    """List all available agents with their names and descriptions."""
    return "\n".join(f"- {n}: {a.get('description', '')}" for n, a in _agents().items())


@mcp.tool(name="agent_team_get_prompt", annotations=READ)
async def agent_team_get_prompt(
    name: str = Field(description="Agent name, e.g. 'backend-agent'")) -> str:
    """Return an agent's system prompt so any model or client can use it directly."""
    return _get(name)["prompt"]


@mcp.tool(name="agent_team_run", annotations=RUN)
async def agent_team_run(
    name: str = Field(description="Agent name, e.g. 'frontend-agent'"),
    task: str = Field(description="What the agent should do"),
    context: Optional[str] = Field(default=None, description="Optional code, specs, or prior agent output")) -> str:
    """Run one agent on a task using the configured local model and return its answer."""
    user = task if not context else f"{task}\n\n--- Context ---\n{context}"
    return await _chat(_get(name)["prompt"], user)


@mcp.tool(name="agent_team_pipeline", annotations=RUN)
async def agent_team_pipeline(
    task: str = Field(description="The feature or app to build, described in plain language")) -> str:
    """Run all four agents in order (ui-ux, backend, frontend, code-review), passing each output to the next."""
    agents = _agents()
    context, sections = "", []
    for name in PIPELINE:
        if name not in agents:
            continue
        user = task if not context else f"{task}\n\n--- Work so far ---\n{context}"
        out = await _chat(agents[name]["prompt"], user)
        sections.append(f"## {name}\n{out}")
        context += f"\n\n[{name}]\n{out}"
    return "\n\n".join(sections)


@mcp.resource("agent://{name}")
def agent_resource(name: str) -> str:
    """An agent's system prompt as a resource."""
    return _get(name)["prompt"]


@mcp.prompt(name="use_agent")
def use_agent(name: str, task: str) -> str:
    """Prompt template: apply an agent's role to a task."""
    return f"{_get(name)['prompt']}\n\nTask: {task}"


if __name__ == "__main__":
    mcp.run()  # stdio transport
