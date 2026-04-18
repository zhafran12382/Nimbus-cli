"""
NimbusCLI - NimbusTeam Engine
Multi-agent delegation system with 3-tier hierarchy:
  Boss (strategic planning) -> Managers (coordination) -> Workers (execution)
"""

import json
import time
from pathlib import Path
from core.config import CONFIG_DIR, PROVIDERS, get_api_key, load_config
from core.llm import create_provider
from core.session import Session
from skills import get_all_tools_schema, execute_skill

TEAM_CONFIG_FILE = CONFIG_DIR / "team_config.json"

# ─── Default Role System Prompts ────────────────────────────────────
DEFAULT_BOSS_PROMPT = """You are the Boss (CEO) of NimbusTeam. Your job is to:
1. Analyze the user's request at the highest strategic level.
2. Break it down into clear subtasks.
3. Assign each subtask to the most suitable manager or worker based on their specialty.
4. After receiving all results, synthesize them into ONE coherent, comprehensive final answer.

You have these team members available:
{member_list}

IMPORTANT RULES:
- Respond ONLY in valid JSON format.
- During PLANNING phase, respond with:
  {{"phase": "plan", "subtasks": [{{"member_id": 0, "task": "description"}}, ...]}}
- During SYNTHESIS phase (after receiving all results), respond with:
  {{"phase": "final", "response": "your comprehensive final answer here"}}
- Assign tasks intelligently based on each member's role and specialty.
- If the task is simple enough for one member, assign it to just one.
- Respond in the same language the user uses.
"""

DEFAULT_MANAGER_PROMPT = """You are a Manager in NimbusTeam. Your role is to:
- Receive tasks from the Boss and coordinate execution using available tools.
- Break complex tasks into smaller steps if needed.
- Execute tasks yourself using all available tools.
- Deliver clear, structured results back to the Boss.
Be thorough, organized, and results-oriented."""

DEFAULT_WORKER_PROMPTS = {
    "researcher": """You are a Research Specialist in NimbusTeam. Your expertise:
- Web searching for accurate, up-to-date information
- Scraping and extracting data from websites
- Fact-checking and source verification
- Summarizing findings clearly
Be thorough but concise. Always cite your sources when possible.""",

    "coder": """You are a Code Specialist in NimbusTeam. Your expertise:
- Writing, debugging, and optimizing code (Python, Bash, etc.)
- File system operations (create, read, modify, delete files)
- System administration and automation scripts
- Technical problem solving
Write clean, working code. Test it when possible.""",

    "analyst": """You are an Analysis Specialist in NimbusTeam. Your expertise:
- Data analysis and interpretation
- Comparing options and making recommendations
- Breaking down complex problems into clear explanations
- Creating summaries, reports, and structured outputs
Be analytical, objective, and data-driven.""",

    "creative": """You are a Creative Specialist in NimbusTeam. Your expertise:
- Writing compelling content (articles, emails, stories, copy)
- Brainstorming ideas and creative solutions
- UI/UX suggestions and design thinking
- Communication and presentation
Be creative, engaging, and original.""",

    "general": """You are a General-Purpose Agent in NimbusTeam.
You can handle any task assigned to you. Use all available tools effectively.
Be thorough and report your results clearly.""",
}


class TeamConfig:
    """Stores NimbusTeam configuration with Boss/Manager/Worker hierarchy."""

    def __init__(self):
        self.enabled = False
        self.boss_provider = ""
        self.boss_model = ""
        self.boss_prompt = ""  # empty = use default
        self.boss_routing = ""  # custom routing for boss (openrouter)
        self.managers: list[dict] = []
        # Each manager: {"id": 0, "name": "...", "provider": "...", "model": "...", 
        #                "prompt": "", "routing": ""}
        self.workers: list[dict] = []
        # Each worker: {"id": 0, "name": "Worker-1", "role": "researcher",
        #               "provider": "openrouter", "model": "...", "prompt": "", "routing": ""}

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "boss_provider": self.boss_provider,
            "boss_model": self.boss_model,
            "boss_prompt": self.boss_prompt,
            "boss_routing": self.boss_routing,
            "managers": self.managers,
            "workers": self.workers,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TeamConfig":
        tc = cls()
        tc.enabled = data.get("enabled", False)
        tc.boss_provider = data.get("boss_provider", "")
        tc.boss_model = data.get("boss_model", "")
        tc.boss_prompt = data.get("boss_prompt", "")
        tc.boss_routing = data.get("boss_routing", "")
        tc.managers = data.get("managers", [])
        tc.workers = data.get("workers", [])
        return tc

    def save(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(TEAM_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load(cls) -> "TeamConfig":
        if TEAM_CONFIG_FILE.exists():
            with open(TEAM_CONFIG_FILE, "r", encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        return cls()

    def get_all_members(self) -> list[dict]:
        """Return combined list of managers + workers with their tier label."""
        members = []
        for m in self.managers:
            members.append({**m, "tier": "manager"})
        for w in self.workers:
            members.append({**w, "tier": "worker"})
        return members

    def get_boss_system_prompt(self) -> str:
        members = self.get_all_members()
        member_list = "\n".join(
            f"  - Member #{m['id']}: {m['name']} (Tier: {m['tier'].upper()}, "
            f"Role: {m.get('role', 'manager')}, Model: {m['model']})"
            for m in members
        )
        if self.boss_prompt:
            return self.boss_prompt.replace("{member_list}", member_list)
        return DEFAULT_BOSS_PROMPT.replace("{member_list}", member_list)

    def get_member_prompt(self, member: dict) -> str:
        if member.get("prompt"):
            return member["prompt"]
        if member.get("tier") == "manager":
            return DEFAULT_MANAGER_PROMPT
        role = member.get("role", "general")
        return DEFAULT_WORKER_PROMPTS.get(role, DEFAULT_WORKER_PROMPTS["general"])


class NimbusTeam:
    """Multi-agent orchestration engine with Boss/Manager/Worker hierarchy."""

    def __init__(self, config: TeamConfig):
        self.config = config
        sys_cfg = load_config()
        self.global_routing = sys_cfg.get("openrouter_routing", "")

        # Boss uses its own routing, falling back to global
        boss_routing = config.boss_routing or self.global_routing
        self.boss_provider = create_provider(
            config.boss_provider,
            config.boss_model,
            routing=boss_routing if config.boss_provider == "openrouter" else ""
        )

    def _get_member_routing(self, member: dict) -> str:
        """Get routing preference for a member: member-specific > global."""
        if member.get("provider") != "openrouter":
            return ""
        return member.get("routing", "") or self.global_routing

    def run(self, user_task: str, session: Session = None, on_status=None, on_worker_start=None,
            on_worker_done=None, on_boss_thinking=None,
            on_worker_tool_call=None, on_worker_tool_result=None) -> str:
        """
        Execute a team task:
        1. Boss plans and decomposes
        2. Members (Managers + Workers) execute subtasks
        3. Boss synthesizes final answer

        Callbacks:
            on_status(msg): General status update
            on_worker_start(worker_name, task): Member begins
            on_worker_done(worker_name, result_preview): Member finishes
            on_boss_thinking(): Boss is processing
            on_worker_tool_call(worker_name, tool_name, args): Member uses a tool
            on_worker_tool_result(worker_name, tool_name, result): Member tool finishes
        """
        all_members = self.config.get_all_members()
        if not all_members:
            return "[Team Error] No team members configured. Run /configure nimbus-team first."

        # ── Phase 1: Boss Plans ──
        if on_boss_thinking:
            on_boss_thinking()
        if on_status:
            on_status("Boss is analyzing and planning subtasks...")

        boss_system = self.config.get_boss_system_prompt()
        plan_messages = [
            {"role": "system", "content": boss_system},
            {"role": "user", "content": f"Plan subtasks for this request:\n\n{user_task}"},
        ]

        try:
            plan_response = self.boss_provider.chat(plan_messages)
            if session and (usage := plan_response.get("usage")):
                session.add_usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            plan_text = plan_response.get("content", "")
        except Exception as e:
            return f"[Team Error] Boss failed to plan: {str(e)}"

        # Parse the plan
        subtasks = self._parse_plan(plan_text)
        if not subtasks:
            # If boss couldn't produce structured plan, treat as single-member task
            subtasks = [{"member_id": 0, "task": user_task}]

        if on_status:
            on_status(f"Plan ready: {len(subtasks)} subtask(s) assigned.")

        # ── Phase 2: Members Execute ──
        member_results = []
        tools_schema = get_all_tools_schema()

        for st in subtasks:
            mid = st.get("member_id", st.get("worker_id", 0))
            task_desc = st["task"]

            # Find the member config (clamp to valid range)
            if mid >= len(all_members):
                mid = mid % len(all_members)

            member_cfg = all_members[mid]
            member_name = member_cfg["name"]
            member_tier = member_cfg.get("tier", "worker").upper()

            if on_worker_start:
                on_worker_start(f"[{member_tier}] {member_name}", task_desc)

            # Create member provider with per-member routing
            try:
                member_routing = self._get_member_routing(member_cfg)
                member_provider = create_provider(
                    member_cfg["provider"],
                    member_cfg["model"],
                    routing=member_routing
                )
                member_system = self.config.get_member_prompt(member_cfg)

                member_messages = [
                    {"role": "system", "content": member_system},
                    {"role": "user", "content": task_desc},
                ]

                # Members get tool access -- run a mini ReAct loop (max 30 iterations)
                result = self._member_execute(
                    member_provider,
                    member_messages,
                    tools_schema,
                    member_name,
                    session,
                    on_worker_tool_call,
                    on_worker_tool_result,
                    max_iter=30
                )

            except Exception as e:
                result = f"[Member Error] {member_name}: {str(e)}"

            member_results.append({
                "member": member_name,
                "tier": member_tier,
                "task": task_desc,
                "result": result,
            })

            if on_worker_done:
                preview = result[:150] + "..." if len(result) > 150 else result
                on_worker_done(f"[{member_tier}] {member_name}", preview)

        # ── Phase 3: Boss Synthesizes ──
        if on_boss_thinking:
            on_boss_thinking()
        if on_status:
            on_status("Boss is synthesizing all results...")

        results_text = "\n\n".join(
            f"--- {mr['tier']}: {mr['member']} ---\nTask: {mr['task']}\nResult:\n{mr['result']}"
            for mr in member_results
        )

        synthesis_messages = [
            {"role": "system", "content": boss_system},
            {"role": "user", "content": f"Original request: {user_task}"},
            {"role": "assistant", "content": plan_text},
            {"role": "user", "content": (
                f"All team members have completed their tasks. Here are their results:\n\n"
                f"{results_text}\n\n"
                f"Now synthesize these results into ONE comprehensive, well-structured final answer. "
                f"Respond in JSON: {{\"phase\": \"final\", \"response\": \"your answer\"}}"
            )},
        ]

        try:
            synth_response = self.boss_provider.chat(synthesis_messages)
            if session and (usage := synth_response.get("usage")):
                session.add_usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            synth_text = synth_response.get("content", "")
        except Exception as e:
            # Fallback: just concat member results
            return f"[Boss synthesis failed: {str(e)}]\n\nRaw member results:\n{results_text}"

        # Parse final response
        final = self._parse_final(synth_text)
        return final or synth_text

    def _member_execute(self, provider, messages, tools_schema, member_name, session=None,
                        on_tool_call=None, on_tool_result=None, max_iter=30) -> str:
        """Mini ReAct loop for a single team member (manager or worker)."""
        for _ in range(max_iter):
            try:
                response = provider.chat(messages, tools=tools_schema if tools_schema else None)
                if session and (usage := response.get("usage")):
                    session.add_usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            except Exception as e:
                return f"[Error] {str(e)}"

            if not response.get("tool_calls"):
                content = response.get("content")
                if not content:
                    return "[Task completed but model generated no textual response.]"
                return content

            # Process tool calls
            assistant_msg = {
                "role": "assistant",
                "content": response.get("content") or None,
                "tool_calls": [
                    {
                        "id": tc.get("id", tc["name"]),
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc["arguments"]) if isinstance(tc["arguments"], dict) else tc["arguments"],
                        },
                    }
                    for tc in response["tool_calls"]
                ],
            }
            messages.append(assistant_msg)

            for tc in response["tool_calls"]:
                tool_name = tc["name"]
                tool_args = tc["arguments"]

                if on_tool_call:
                    on_tool_call(member_name, tool_name, tool_args)

                result = execute_skill(tool_name, tool_args)

                if on_tool_result:
                    on_tool_result(member_name, tool_name, result)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", tc["name"]),
                    "content": result,
                })

        # If max iterations hit, force a final text answer
        try:
            messages.append({"role": "user", "content": "Please provide your final answer now."})
            response = provider.chat(messages)
            if session and (usage := response.get("usage")):
                session.add_usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            return response.get("content") or "[Member reached max iterations]"
        except Exception:
            return "[Member reached max iterations without response]"

    def _parse_plan(self, text: str) -> list[dict]:
        """Parse boss's JSON plan into subtasks list."""
        try:
            # Try to extract JSON from the text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                if data.get("phase") == "plan" and "subtasks" in data:
                    return data["subtasks"]
        except (json.JSONDecodeError, KeyError):
            pass

        # Try array directly
        try:
            start = text.find("[")
            end = text.rfind("]") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, KeyError):
            pass

        return []

    def _parse_final(self, text: str) -> str:
        """Parse boss's final synthesis JSON."""
        try:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
                if "response" in data:
                    return data["response"]
        except (json.JSONDecodeError, KeyError):
            pass
        return ""
