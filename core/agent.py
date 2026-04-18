"""
NimbusCLI - Agent Core
The ReAct (Reasoning + Acting) agentic loop.
Handles the Think -> Act -> Observe cycle.
"""

import json
from core.llm import create_provider
from core.session import Session
from skills import get_all_tools_schema, execute_skill

# Maximum number of tool call iterations before forcing a final answer
MAX_TOOL_ITERATIONS = 100

SYSTEM_PROMPT = """You are NimbusCLI, a powerful personal AI agent running in the user's terminal.
You are both a helpful assistant AND a capable agent that can take real actions on the user's system.

Your capabilities through tools:
- execute_python: Run Python code for calculations, scripting, data processing
- execute_bash: Run shell/bash commands for system operations
- web_search: Search the web for current information (uses Tavily API)
- scrape_url: Read and extract content from web pages
- file_manager: Full file system access (read, write, delete, list, move, copy, mkdir)
- create_skill: Create brand new tools/skills on the fly when the user needs something custom

Guidelines:
1. Use tools proactively when needed. Don't just describe what you would do -- actually do it.
2. When asked to create files, write code, or perform system tasks, USE the appropriate tools.
3. For web questions, search first to get accurate, up-to-date info.
4. You can chain multiple tool calls to accomplish complex tasks.
5. When the user asks you to create a new tool/skill, use create_skill to write and register it.
6. Always report what you did and the results clearly.
7. Be concise but thorough. Show relevant output from tool executions.
8. Respond in the same language the user uses.
"""


class Agent:
    """The core agent that orchestrates LLM calls and tool execution."""

    def __init__(self, provider_id: str, model: str, session: Session = None):
        self.provider_id = provider_id
        self.model = model
        
        from core.config import load_config
        config = load_config()
        routing = config.get("openrouter_routing", "") if provider_id == "openrouter" else ""
        
        self.provider = create_provider(provider_id, model, routing=routing)
        
        self.session = session or Session()
        self.session.provider = provider_id
        self.session.model = model

    def _build_messages(self) -> list[dict]:
        """Build the full message list including system prompt."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(self.session.get_messages_for_api())
        return messages

    def run(self, user_input: str, on_thinking=None, on_tool_call=None, on_tool_result=None) -> str:
        """
        Process a user message through the ReAct loop.

        Args:
            user_input: The user's message.
            on_thinking: Callback when agent starts thinking. fn()
            on_tool_call: Callback when a tool is called. fn(name, args)
            on_tool_result: Callback when tool returns result. fn(name, result)

        Returns:
            The agent's final text response.
        """
        # Add user message to session
        self.session.add_message("user", user_input)

        tools_schema = get_all_tools_schema()
        iteration = 0

        while iteration < MAX_TOOL_ITERATIONS:
            iteration += 1

            if on_thinking:
                on_thinking()

            # Call the LLM
            messages = self._build_messages()
            try:
                response = self.provider.chat(messages, tools=tools_schema if tools_schema else None)
                if usage := response.get("usage"):
                    self.session.add_usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            except Exception as e:
                error_msg = f"[LLM Error] {type(e).__name__}: {str(e)}"
                self.session.add_message("assistant", error_msg)
                return error_msg

            # If no tool calls, return the text response
            if not response.get("tool_calls"):
                content = response.get("content") or "[No response from model]"
                self.session.add_message("assistant", content)
                return content

            # Process tool calls
            # First, record the assistant's response (may have content + tool_calls)
            assistant_msg = {
                "role": "assistant",
                "content": response.get("content"),
                "tool_calls": response["tool_calls"],
            }
            self.session.messages.append({
                **assistant_msg,
                "timestamp": __import__("time").time(),
            })

            # Execute each tool call
            for tc in response["tool_calls"]:
                tool_name = tc["name"]
                tool_args = tc["arguments"]
                tool_id = tc.get("id", tool_name)

                if on_tool_call:
                    on_tool_call(tool_name, tool_args)

                # Execute the skill
                result = execute_skill(tool_name, tool_args)

                if on_tool_result:
                    on_tool_result(tool_name, result)

                # Add tool result to session
                self.session.messages.append({
                    "role": "tool",
                    "name": tool_name,
                    "tool_call_id": tool_id,
                    "content": result,
                    "timestamp": __import__("time").time(),
                })

        # If we hit max iterations, force a response
        self.session.add_message("user", "[System: Maximum tool iterations reached. Please provide your final response.]")
        messages = self._build_messages()
        try:
            response = self.provider.chat(messages)
            if usage := response.get("usage"):
                self.session.add_usage(usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
            content = response.get("content") or "[Agent reached maximum iterations]"
        except Exception:
            content = "[Agent reached maximum tool call iterations without a final response]"

        self.session.add_message("assistant", content)
        return content

    def run_stream(self, user_input: str, on_thinking=None) -> str:
        """
        Stream a simple (non-tool) response.
        For tool-calling, use run() instead.

        Yields text chunks.
        """
        self.session.add_message("user", user_input)

        if on_thinking:
            on_thinking()

        messages = self._build_messages()
        full_response = ""

        try:
            for chunk in self.provider.stream_chat(messages):
                full_response += chunk
                yield chunk
        except Exception as e:
            error = f"\n[Stream Error] {type(e).__name__}: {str(e)}"
            full_response += error
            yield error

        self.session.add_message("assistant", full_response)
