#!/usr/bin/env python3
"""
NimbusCLI -- Personal AI Agent
A lightweight, terminal-based AI agent with tool-calling capabilities.
"""

import sys
import os
import argparse
import importlib
import importlib.util
from pathlib import Path

# Ensure project root is in path
sys.path.insert(0, str(Path(__file__).parent))

import questionary
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.styles import Style

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich import print as rprint

from core.config import (
    load_config, save_config, save_api_key, get_api_key,
    PROVIDERS, CONFIG_DIR, ensure_config_dir,
)
from core.session import Session
from core.agent import Agent
from core.llm import create_provider
from providers.openrouter import OpenRouterProvider
from skills import register_skill, SKILL_REGISTRY
from core.team import TeamConfig, NimbusTeam, DEFAULT_WORKER_PROMPTS
import difflib

console = Console()

# ─── ASCII Banner ───────────────────────────────────────────────────
BANNER = """[bold cyan]
 ███╗   ██╗██╗███╗   ███╗██████╗ ██╗   ██╗███████╗
 ████╗  ██║██║████╗ ████║██╔══██╗██║   ██║██╔════╝
 ██╔██╗ ██║██║██╔████╔██║██████╔╝██║   ██║███████╗
 ██║╚██╗██║██║██║╚██╔╝██║██╔══██╗██║   ██║╚════██║
 ██║ ╚████║██║██║ ╚═╝ ██║██████╔╝╚██████╔╝███████║
 ╚═╝  ╚═══╝╚═╝╚═╝     ╚═╝╚═════╝  ╚═════╝ ╚══════╝
[/bold cyan][dim]  Personal AI Agent • v1.2.0 (Production Test)[/dim]
"""

# Custom Prompt Style
custom_style = Style.from_dict({
    'prompt': 'bold ansiwhite',
})

# ─── Skill Registration ────────────────────────────────────────────
def register_all_skills():
    """Register all built-in and generated skills."""
    from skills.python_exec import PythonExecutor
    from skills.bash_exec import BashExecutor
    from skills.web_search import WebSearch
    from skills.web_scraper import WebScraper
    from skills.file_manager import FileManager
    from skills.skill_creator import SkillCreator

    for skill_class in [PythonExecutor, BashExecutor, WebSearch, WebScraper, FileManager, SkillCreator]:
        register_skill(skill_class())

    # Load generated skills
    generated_dir = Path(__file__).parent / "generated_skills"
    if generated_dir.exists():
        for skill_file in generated_dir.glob("*.py"):
            if skill_file.name.startswith("_"):
                continue
            try:
                spec = importlib.util.spec_from_file_location(
                    f"generated_skills.{skill_file.stem}", str(skill_file)
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                from skills.base import BaseSkill
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if isinstance(attr, type) and issubclass(attr, BaseSkill) and attr is not BaseSkill:
                        register_skill(attr())
            except Exception:
                pass


# ─── Setup Wizard ───────────────────────────────────────────────────
def cmd_setup():
    """Interactive setup wizard using Questionary."""
    console.print(BANNER)
    console.print("[bold]Setup Wizard[/bold]\n")

    config = load_config()

    if config.get("provider"):
        console.print(f"[dim]Current default provider: {config['provider']}[/dim]")
        proceed = questionary.confirm("Configuration already exists. Do you want to re-configure?").ask()
        if not proceed:
            console.print("[dim]Setup cancelled. Exiting menu.[/dim]")
            return

    # Provider selection
    provider_ids = list(PROVIDERS.keys())
    provider_choices = []
    for pid in provider_ids:
        p = PROVIDERS[pid]
        status = "[Configured]" if get_api_key(pid) else "[Not Set]"
        provider_choices.append(questionary.Choice(f"{p['name']} {status}", value=pid))

    selected_provider = questionary.select(
        "Select default provider:",
        choices=provider_choices
    ).ask()
    
    if not selected_provider:
        return
        
    config["provider"] = selected_provider

    # API Key
    provider_config = PROVIDERS[selected_provider]
    current_key = get_api_key(selected_provider)
    
    if current_key:
        update_key = questionary.confirm(
            f"API key for {provider_config['name']} already set. Update it?"
        ).ask()
        if update_key:
            key = questionary.password(f"Enter {provider_config['name']} API key:").ask()
            if key: save_api_key(provider_config["api_key_env"], key)
    else:
        key = questionary.password(f"Enter {provider_config['name']} API key:").ask()
        if key: save_api_key(provider_config["api_key_env"], key)

    # Model selection
    models = provider_config["models"]
    model_choices = []

    if selected_provider == "openrouter":
        model_choices.append(questionary.Choice("Custom Model (Type your own)", value="__custom__"))

    for m in models:
        free_tag = " (FREE)" if m.get("free") else ""
        model_choices.append(questionary.Choice(f"{m['name']} {free_tag} - {m['id']}", value=m["id"]))

    while True:
        selected_model = questionary.select(
            "Select default model:",
            choices=model_choices
        ).ask()
        
        if not selected_model:
            return

        if selected_model == "__custom__":
            custom_model = questionary.text("Enter OpenRouter model ID (e.g. anthropic/claude-3-opus, openai/gpt-4o):").ask()
            if not custom_model:
                continue
            
            # Validate the custom model by sending a 10-token request
            console.print(f"[dim]Validating routing '{custom_model}' via OpenRouter API...[/dim]")
            try:
                test_prov = create_provider("openrouter", custom_model)
                test_prov.chat([{"role": "user", "content": "Say 'ok'"}], max_tokens=10)
                console.print(f"[green]Routing/Model '{custom_model}' is valid![/green]")
                config["model"] = custom_model
                break
            except Exception as e:
                console.print(f"[red]Validation failed: {str(e)}[/red]")
                console.print("[yellow]Please try entering a different model or routing ID.[/yellow]")
                continue
        else:
            config["model"] = selected_model
            break

    # OpenRouter Routing Selection
    if selected_provider == "openrouter":
        routing_choice = questionary.select(
            "Select OpenRouter Routing Preference:",
            choices=[
                questionary.Choice("Auto (OpenRouter decides)", value="auto"),
                questionary.Choice("Custom Providers (Type your own)", value="__custom__")
            ]
        ).ask()
        
        if routing_choice == "__custom__":
            while True:
                custom_route = questionary.text("Enter provider routing order (comma-separated, e.g. DeepInfra, together, fireworks):").ask()
                if not custom_route:
                    continue
                
                # Strict validation: use provider.only + allow_fallbacks=false
                console.print(f"[dim]Validating routing '{custom_route}' with model '{config['model']}'...[/dim]")
                api_key = get_api_key("openrouter")
                is_valid, err_msg = OpenRouterProvider.validate_routing(api_key, config["model"], custom_route)
                if is_valid:
                    console.print(f"[green][OK] Routing configuration is valid![/green]")
                    config["openrouter_routing"] = custom_route
                    break
                else:
                    console.print(f"[red][X] Routing validation failed: {err_msg}[/red]")
                    console.print("[yellow]Please check the provider names and try again.[/yellow]")
                    retry = questionary.confirm("Try again?", default=True).ask()
                    if not retry:
                        console.print("[dim]Using Auto routing as fallback.[/dim]")
                        config["openrouter_routing"] = ""
                        break
        else:
            config["openrouter_routing"] = ""

    # Tavily key
    console.print("\n[dim]- Tavily provides higher-quality web search results.[/dim]")
    console.print("[dim]- DuckDuckGo is used as a free fallback if no key is provided.[/dim]")
    set_tavily = questionary.confirm("Configure Tavily API key for web search?").ask()
    
    if set_tavily:
        t_key = questionary.password("Enter Tavily API key:").ask()
        if t_key:
            save_api_key("TAVILY_API_KEY", t_key)
            config["search_engine"] = "tavily"
    else:
        config["search_engine"] = "duckduckgo"

    save_config(config)
    console.print("\n[bold]Setup complete![/bold]")


# ─── Config Display ────────────────────────────────────────────────
def cmd_config():
    """Show current configuration."""
    config = load_config()

    table = Table(title="NimbusCLI Configuration", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")

    table.add_row("Provider", PROVIDERS.get(config.get("provider", ""), {}).get("name", config.get("provider", "N/A")))
    table.add_row("Model", config.get("model", "N/A"))
    table.add_row("Search Engine", config.get("search_engine", "duckduckgo"))
    table.add_row("Config Dir", str(CONFIG_DIR))

    console.print(table)

    # Show API key status
    console.print("\n[bold]API Key Status:[/bold]")
    for pid, p in PROVIDERS.items():
        status = "[Installed]" if get_api_key(pid) else "[Missing]"
        console.print(f"  {status} {p['name']}")

    tavily = "[Installed]" if os.environ.get("TAVILY_API_KEY") else "[Missing]"
    console.print(f"  {tavily} Tavily (Web Search)")


# ─── Skills List ────────────────────────────────────────────────────
def cmd_skills():
    """List all available skills."""
    register_all_skills()

    table = Table(title="Available Skills", show_header=True)
    table.add_column("#", style="dim", width=3)
    table.add_column("Tool Name", style="cyan bold")
    table.add_column("Description", style="white")

    for i, (name, skill) in enumerate(SKILL_REGISTRY.items(), 1):
        desc = skill.description[:80] + "..." if len(skill.description) > 80 else skill.description
        table.add_row(str(i), name, desc)

    console.print(table)


# ─── Memory Compaction ──────────────────────────────────────────────
def _compact_memory(session: Session):
    """Use Xiaomi MiMo-V2-Pro (or fallback) to summarize chat history."""
    if len(session.messages) < 4:
        console.print("[dim]Memory is already compact.[/dim]")
        return

    console.print("[dim]Compacting memory...[/dim]")
    
    # Extract transcript
    transcript = []
    for msg in session.messages:
        role = msg.get("role", "unknown")
        content = msg.get("content")
        if content:
            transcript.append(f"{role.upper()}: {content}")
        elif msg.get("tool_calls"):
            transcript.append(f"{role.upper()}: [Tool Call]")
            
    transcript_text = "\n".join(transcript)
    
    prompt = (
        "You are a memory optimization core. Please summarize the following conversation history "
        "into a concise, dense set of key facts, user preferences, and important context. "
        "Keep ALL critical details that would be needed for future tasks, but remove conversational filler. "
        "Respond ONLY with the summarized memory facts.\n\n"
        f"<conversation>\n{transcript_text}\n</conversation>"
    )

    # Setup agent for compaction (mimo-v2-pro if openrouter key exists)
    provider_id = "openrouter"
    model = "xiaomi/mimo-v2-pro"
    
    if not get_api_key("openrouter"):
        config = load_config()
        provider_id = config.get("provider", "openai")
        model = config.get("model", "gpt-3.5-turbo")
        
    try:
        ag = Agent(provider_id, model)
        ag.session.add_message("user", prompt)
        
        with console.status("[dim]Analyzing history...[/dim]", spinner="dots"):
            response = ag.provider.chat(ag._build_messages())
            summary = response.get("content", "")
            
        if summary:
            # Replace history with summary
            session.clear()
            session.add_message("system", f"Previous Context Summary:\n{summary}")
            console.print("[dim]Memory successfully compacted to core context.[/dim]")
        else:
            console.print("[dim]Failed to generate summary.[/dim]")
            
    except Exception as e:
        console.print(f"[dim]Memory compaction failed: {str(e)}[/dim]")


# ─── NimbusTeam Configuration ───────────────────────────────────────
MAX_TEAM_MEMBERS = 8  # Boss + Managers + Workers total cap
MAX_MANAGERS = 2

def _configure_team():
    """Interactive NimbusTeam setup wizard with Boss/Manager/Worker hierarchy."""
    console.print()
    console.print(Panel(
        "[bold]NimbusTeam Configuration Wizard[/bold]\n"
        "[dim]Build your AI team with a 3-tier hierarchy:[/dim]\n"
        "  [cyan]Boss[/cyan] (1) -> [yellow]Managers[/yellow] (0-2) -> [green]Workers[/green] (1-7)\n"
        f"  [dim]Maximum {MAX_TEAM_MEMBERS} total members (including Boss)[/dim]",
        title="[bold cyan]>> NimbusTeam Setup[/bold cyan]",
        border_style="cyan",
    ))

    tc = TeamConfig.load()
    if tc.enabled:
        console.print("[dim]NimbusTeam is already configured.[/dim]")
        proceed = questionary.confirm("Do you want to re-configure the team?").ask()
        if not proceed:
            console.print("[dim]Setup cancelled. Exiting menu.[/dim]")
            return

    # Gather all configured providers
    configured_providers = []
    for pid, p in PROVIDERS.items():
        if get_api_key(pid):
            configured_providers.append(pid)

    if not configured_providers:
        console.print("[red]No API keys configured. Run 'python main.py setup' first.[/red]")
        return

    # Helper to pick provider + model + optional routing with strict validation
    def pick_model_with_routing(label: str):
        """Returns (provider, model, routing) tuple."""
        prov = questionary.select(
            f"{label} -- Select provider:",
            choices=[questionary.Choice(PROVIDERS[p]["name"], value=p) for p in configured_providers]
        ).ask()
        if not prov:
            return None, None, ""
        
        models = PROVIDERS[prov]["models"]
        model_choices = []
        if prov == "openrouter":
            model_choices.append(questionary.Choice("Custom Model (Type your own)", value="__custom__"))
        for m in models:
            tag = " (FREE)" if m.get("free") else ""
            model_choices.append(questionary.Choice(f"{m['name']}{tag}", value=m["id"]))
        
        mod = questionary.select(f"{label} -- Select model:", choices=model_choices).ask()
        if not mod:
            return None, None, ""
        
        # Handle custom model input
        if mod == "__custom__":
            mod = questionary.text("Enter model ID (e.g. anthropic/claude-3-opus, openai/gpt-4o):").ask()
            if not mod:
                return None, None, ""
        
        # Routing selection for OpenRouter
        routing = ""
        if prov == "openrouter":
            routing_choice = questionary.select(
                f"{label} -- OpenRouter Routing:",
                choices=[
                    questionary.Choice("Auto (OpenRouter decides)", value="auto"),
                    questionary.Choice("Custom Providers (Type your own)", value="__custom__"),
                ]
            ).ask()
            if routing_choice == "__custom__":
                while True:
                    routing = questionary.text(
                        "Enter routing order (comma-separated, e.g. DeepInfra, Together):"
                    ).ask() or ""
                    if not routing:
                        break
                    
                    # Strict validation
                    console.print(f"[dim]Validating routing '{routing}' with model '{mod}'...[/dim]")
                    api_key = get_api_key("openrouter")
                    is_valid, err_msg = OpenRouterProvider.validate_routing(api_key, mod, routing)
                    if is_valid:
                        console.print(f"[green]>> Routing validated![/green]")
                        break
                    else:
                        console.print(f"[red]>> Routing validation failed: {err_msg}[/red]")
                        action = questionary.select(
                            "What would you like to do?",
                            choices=[
                                questionary.Choice("Try again with different routing", value="retry"),
                                questionary.Choice("Use Auto routing instead", value="auto"),
                            ]
                        ).ask()
                        if action == "auto":
                            routing = ""
                            console.print("[dim]Using Auto routing.[/dim]")
                            break
                        # else: loop continues
        
        return prov, mod, routing

    slots_remaining = MAX_TEAM_MEMBERS

    # ══════════════════════════════════════════════════════════════════
    # Step 1: BOSS (always 1)
    # ══════════════════════════════════════════════════════════════════
    console.print()
    console.print(Panel(
        "[bold]The Boss analyzes tasks, delegates to managers/workers, and synthesizes results.[/bold]",
        title="[bold cyan]Step 1/3: Boss (CEO)[/bold cyan]",
        border_style="cyan",
    ))
    
    boss_prov, boss_model, boss_routing = pick_model_with_routing("Boss")
    if not boss_prov:
        console.print("[dim]Cancelled.[/dim]")
        return
    tc.boss_provider = boss_prov
    tc.boss_model = boss_model
    tc.boss_routing = boss_routing
    slots_remaining -= 1  # Boss takes 1 slot

    use_custom_boss = questionary.confirm("Use custom system prompt for Boss? (No = use built-in smart prompt)").ask()
    if use_custom_boss:
        tc.boss_prompt = questionary.text("Enter Boss system prompt:").ask() or ""
    else:
        tc.boss_prompt = ""

    console.print(f"[dim]Slots remaining: {slots_remaining}/{MAX_TEAM_MEMBERS}[/dim]")

    # ══════════════════════════════════════════════════════════════════
    # Step 2: MANAGERS (optional, max 2)
    # ══════════════════════════════════════════════════════════════════
    console.print()
    console.print(Panel(
        "[bold]Managers coordinate complex subtasks between Boss and Workers.[/bold]\n"
        f"[dim]Max {MAX_MANAGERS} managers. You can skip this for a flat Boss->Worker structure.[/dim]",
        title="[bold yellow]Step 2/3: Managers (Optional)[/bold yellow]",
        border_style="yellow",
    ))

    add_managers = questionary.confirm("Add Managers to the team?", default=False).ask()
    managers = []
    
    if add_managers:
        max_mgr = min(MAX_MANAGERS, slots_remaining - 1)  # reserve at least 1 for workers
        if max_mgr < 1:
            console.print("[dim]Not enough slots for managers. Skipping.[/dim]")
        else:
            num_managers_input = questionary.text(
                f"How many managers? (1-{max_mgr}):", default="1"
            ).ask()
            try:
                num_managers = max(1, min(max_mgr, int(num_managers_input)))
            except ValueError:
                num_managers = 1

            for i in range(num_managers):
                console.print(f"\n[bold yellow]--- Manager #{i + 1} ---[/bold yellow]")
                
                name = questionary.text(f"Manager name:", default=f"Manager-{i+1}").ask() or f"Manager-{i+1}"
                m_prov, m_model, m_routing = pick_model_with_routing(f"Manager '{name}'")
                if not m_prov:
                    continue

                use_custom = questionary.confirm("Use custom system prompt? (No = use default)").ask()
                custom_prompt = ""
                if use_custom:
                    custom_prompt = questionary.text("Enter manager system prompt:").ask() or ""

                managers.append({
                    "id": i,
                    "name": name,
                    "role": "manager",
                    "provider": m_prov,
                    "model": m_model,
                    "prompt": custom_prompt,
                    "routing": m_routing,
                    "tier": "manager",
                })
                slots_remaining -= 1
                console.print(f"[dim]Slots remaining: {slots_remaining}/{MAX_TEAM_MEMBERS}[/dim]")

    tc.managers = managers

    # ══════════════════════════════════════════════════════════════════
    # Step 3: WORKERS
    # ══════════════════════════════════════════════════════════════════
    console.print()
    max_workers = slots_remaining
    console.print(Panel(
        "[bold]Workers execute the actual tasks (research, coding, analysis, etc.)[/bold]\n"
        f"[dim]Available slots: {max_workers}[/dim]",
        title="[bold green]Step 3/3: Workers (Execution)[/bold green]",
        border_style="green",
    ))

    if max_workers < 1:
        console.print("[red]No slots remaining for workers![/red]")
        return

    num_workers_input = questionary.text(
        f"How many workers? (1-{max_workers}):", default=str(min(2, max_workers))
    ).ask()
    try:
        num_workers = max(1, min(max_workers, int(num_workers_input)))
    except ValueError:
        num_workers = min(2, max_workers)

    workers = []
    for i in range(num_workers):
        console.print(f"\n[bold green]--- Worker #{i + 1} ---[/bold green]")

        # Role selection
        role = questionary.select(
            f"Worker #{i + 1} -- Select role:",
            choices=[
                questionary.Choice("Researcher  -- Web search, scraping, fact-checking", value="researcher"),
                questionary.Choice("Coder       -- Code, scripts, file operations", value="coder"),
                questionary.Choice("Analyst     -- Data analysis, reports, comparisons", value="analyst"),
                questionary.Choice("Creative    -- Writing, brainstorming, design", value="creative"),
                questionary.Choice("General     -- All-purpose agent", value="general"),
            ]
        ).ask()
        if not role:
            continue

        # Name
        default_name = f"{role.capitalize()}-{i + 1}"
        name = questionary.text(f"Worker name:", default=default_name).ask() or default_name

        # Model + Routing
        w_prov, w_model, w_routing = pick_model_with_routing(f"Worker '{name}'")
        if not w_prov:
            continue

        # Custom prompt?
        use_custom = questionary.confirm("Use custom system prompt? (No = use role default)").ask()
        custom_prompt = ""
        if use_custom:
            custom_prompt = questionary.text("Enter worker system prompt:").ask() or ""

        workers.append({
            "id": len(managers) + i,
            "name": name,
            "role": role,
            "provider": w_prov,
            "model": w_model,
            "prompt": custom_prompt,
            "routing": w_routing,
            "tier": "worker",
        })

    tc.workers = workers
    tc.enabled = True
    tc.save()

    console.print()
    console.print("[bold green]>> NimbusTeam configured successfully![/bold green]")
    _show_team_info(tc)


def _show_team_info(tc: TeamConfig = None):
    """Display current team configuration."""
    if tc is None:
        tc = TeamConfig.load()

    if not tc.enabled or (not tc.workers and not tc.managers):
        console.print("[dim]NimbusTeam is not configured. Use /configure nimbus-team[/dim]")
        return

    table = Table(title="[bold]NimbusTeam[/bold]", show_header=True, border_style="cyan",
                  title_style="bold cyan", header_style="bold")
    table.add_column("Tier", style="bold", min_width=10)
    table.add_column("Name", style="cyan", min_width=12)
    table.add_column("Role", style="magenta")
    table.add_column("Model", style="green")
    table.add_column("Provider", style="dim")
    table.add_column("Routing", style="dim")

    # Boss row
    boss_prov_name = PROVIDERS.get(tc.boss_provider, {}).get("name", tc.boss_provider)
    boss_routing_display = tc.boss_routing or "Auto"
    table.add_row("[cyan]BOSS[/cyan]", "Team Leader", "Orchestrator", tc.boss_model, boss_prov_name, boss_routing_display)

    # Managers
    for m in tc.managers:
        m_prov_name = PROVIDERS.get(m["provider"], {}).get("name", m["provider"])
        m_routing_display = m.get("routing", "") or "Auto"
        table.add_row("[yellow]MANAGER[/yellow]", m["name"], m.get("role", "manager").upper(), m["model"], m_prov_name, m_routing_display)

    # Workers
    for w in tc.workers:
        w_prov_name = PROVIDERS.get(w["provider"], {}).get("name", w["provider"])
        w_routing_display = w.get("routing", "") or "Auto"
        table.add_row("[green]WORKER[/green]", w["name"], w.get("role", "general").upper(), w["model"], w_prov_name, w_routing_display)

    console.print(table)
    total = 1 + len(tc.managers) + len(tc.workers)
    console.print(f"[dim]Total: {total}/{MAX_TEAM_MEMBERS} slots used (1 Boss + {len(tc.managers)} Manager(s) + {len(tc.workers)} Worker(s))[/dim]")


def _run_team(task: str, session=None):
    """Execute a task using NimbusTeam."""
    tc = TeamConfig.load()
    if not tc.enabled or (not tc.workers and not tc.managers):
        console.print("[dim]NimbusTeam is not configured. Use /configure nimbus-team[/dim]")
        return

    register_all_skills()
    team = NimbusTeam(tc)

    console.print()
    console.print(Panel(f"[bold cyan]Task:[/bold cyan] {task}", title="[bold cyan]NimbusTeam Activated[/bold cyan]", border_style="cyan"))
    console.print()

    try:
        def on_status(msg):
            console.print(f" [cyan]*[/cyan] [dim]{msg}[/dim]")

        def on_worker_start(name, task_desc):
            console.print()
            short = task_desc[:120] + "..." if len(task_desc) > 120 else task_desc
            console.print(Panel(f"[dim]{short}[/dim]", title=f"[bold yellow]>> {name} started[/bold yellow]", border_style="yellow", title_align="left"))

        def on_worker_done(name, preview):
            lines = preview.split('\n')
            short = lines[0][:150] + "..." if len(lines[0]) > 150 else lines[0]
            console.print(f" [green][OK][/green] [bold green]{name} completed task.[/bold green] [dim]{short}[/dim]")
            console.print()

        def on_boss_thinking():
            console.print(f" [magenta]*[/magenta] [dim]Boss is reviewing and synthesizing results...[/dim]")

        def on_worker_tool_call(worker_name, tool_name, args):
            args_preview = str(args)
            if len(args_preview) > 120:
                args_preview = args_preview[:120] + "..."
            console.print(f"    [yellow]>> [bold]{worker_name}[/bold] called Tool: {tool_name}[/yellow]")
            console.print(f"       [dim]{args_preview}[/dim]")

        def on_worker_tool_result(worker_name, tool_name, result):
            lines = result.strip().split("\n")
            preview_lines = lines[:5]
            preview = "\n".join(f"       [dim]{l[:100]}[/dim]" for l in preview_lines)
            if len(lines) > 5:
                preview += f"\n       [dim]... +{len(lines) - 5} more lines[/dim]"
            console.print(f"    [green]<< {tool_name}[/green] [dim]returned to {worker_name}[/dim]")
            console.print(preview)

        response = team.run(
            task,
            session=session,
            on_status=on_status,
            on_worker_start=on_worker_start,
            on_worker_done=on_worker_done,
            on_boss_thinking=on_boss_thinking,
            on_worker_tool_call=on_worker_tool_call,
            on_worker_tool_result=on_worker_tool_result,
        )

        console.print()
        console.print(Panel(Markdown(response), title="[bold green]NimbusTeam Result[/bold green]", border_style="green"))

    except KeyboardInterrupt:
        console.print("\n[dim]Team task interrupted.[/dim]")
    except Exception as e:
        console.print(f"[red]Team error: {str(e)}[/red]")


# ─── Interactive Chat ───────────────────────────────────────────────
def cmd_chat():
    """Main interactive chat loop."""
    console.print(BANNER)

    config = load_config()
    provider_id = config.get("provider", "openrouter")
    model = config.get("model", "google/gemma-4-31b-it:free")

    if not get_api_key(provider_id):
        console.print(f"[bold red]No API key set for {PROVIDERS[provider_id]['name']}.[/bold red]")
        console.print(f"Run 'python main.py setup' first.\n")
        return

    register_all_skills()

    # Load last session if possible
    session = Session()
    sessions = Session.list_sessions()
    if sessions:
        last_session_id = sessions[0]["id"]
        load_prev = questionary.confirm(f"Resume previous session ({last_session_id})?").ask()
        if load_prev:
            session = Session.load(last_session_id)
            model = session.model or model
            provider_id = session.provider or provider_id

    provider_name = PROVIDERS.get(provider_id, {}).get("name", provider_id)
    console.print(f"[dim]Provider: {provider_name} │ Model: {model}[/dim]")
    console.print(f"[dim]Type 'exit' to quit, '/help' for commands[/dim]\n")

    agent = Agent(provider_id, model, session)
    prompt_session = PromptSession(history=InMemoryHistory())

    while True:
        try:
            user_input = prompt_session.prompt("You > ", style=custom_style).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Disconnected.[/dim]")
            break

        if not user_input:
            continue

        # Handle slash commands
        cmd_lower = user_input.lower()
        cmd = cmd_lower.split(" ")[0]
        if cmd in ("exit", "quit", "/exit", "/quit"):
            agent.session.save()
            console.print("[dim]Session saved. Disconnected.[/dim]")
            break
        elif cmd == "/help":
            _show_help()
            continue
        elif cmd == "/compact-memory":
            _compact_memory(agent.session)
            continue
        elif cmd == "/skills":
            cmd_skills()
            continue
        elif cmd == "/token":
            in_t = agent.session.total_input_tokens
            out_t = agent.session.total_output_tokens
            tot_t = in_t + out_t
            console.print(f"\n[cyan]Session Token Usage:[/cyan]")
            console.print(f"  Input Tokens:  {in_t:,}")
            console.print(f"  Output Tokens: {out_t:,}")
            console.print(f"  Total Tokens:  [bold]{tot_t:,}[/bold]")
            continue
        elif cmd == "/config":
            cmd_config()
            continue
        elif cmd == "/clear":
            agent.session.clear()
            console.print("[dim]Context cleared.[/dim]")
            continue
        elif cmd == "/new":
            agent.session.save()
            agent.session = Session()
            agent.session.provider = provider_id
            agent.session.model = agent.model
            console.print("[dim]Started new session context.[/dim]")
            continue
        elif cmd == "/save":
            agent.session.save()
            console.print(f"[dim]Session saved: {agent.session.session_id}[/dim]")
            continue
        elif cmd == "/history":
            history_list = Session.list_sessions()
            tbl = Table(title="Saved Sessions", show_header=True)
            tbl.add_column("ID")
            tbl.add_column("Model")
            tbl.add_column("Messages")
            for h in history_list[:10]:
                tbl.add_row(h['id'], h['model'], str(h['message_count']))
            console.print(tbl)
            continue
        elif cmd == "/load":
            parts = user_input.split(" ", 1)
            if len(parts) > 1:
                try:
                    agent.session = Session.load(parts[1].strip())
                    console.print(f"[dim]Session {parts[1].strip()} loaded.[/dim]")
                except Exception as e:
                    console.print(f"[dim]Error loading: {str(e)}[/dim]")
            else:
                console.print("[dim]Usage: /load <session_id>[/dim]")
            continue
        elif cmd == "/model":
            parts = user_input.split(" ", 1)
            if len(parts) > 1:
                new_model = parts[1].strip()
                available_models = [m["id"] for m in PROVIDERS.get(provider_id, {}).get("models", [])]
                
                if new_model in available_models:
                    # Exact match -- switch immediately
                    try:
                        agent.provider = create_provider(provider_id, new_model)
                        agent.model = new_model
                        agent.session.model = new_model
                        console.print(f"[dim]Model switched to: {new_model}[/dim]")
                    except Exception as e:
                        console.print(f"[red]Error switching model: {str(e)}[/red]")
                else:
                    # Not found -- try fuzzy match
                    matches = difflib.get_close_matches(new_model, available_models, n=3, cutoff=0.3)
                    if matches:
                        console.print(f"[yellow]Model '{new_model}' not found. Did you mean:[/yellow]")
                        for i, m in enumerate(matches, 1):
                            console.print(f"  {i}. {m}")
                        pick = questionary.select(
                            "Select model:",
                            choices=[questionary.Choice(m, value=m) for m in matches] + [questionary.Choice("Cancel", value=None)]
                        ).ask()
                        if pick:
                            try:
                                agent.provider = create_provider(provider_id, pick)
                                agent.model = pick
                                agent.session.model = pick
                                console.print(f"[dim]Model switched to: {pick}[/dim]")
                            except Exception as e:
                                console.print(f"[red]Error switching model: {str(e)}[/red]")
                    else:
                        console.print(f"[red]Model '{new_model}' not found. No similar matches.[/red]")
                        console.print("[dim]Available models:[/dim]")
                        for m in available_models:
                            console.print(f"  - {m}")
            else:
                console.print("[dim]Usage: /model <model_id>[/dim]")
            continue
        elif cmd_lower.startswith("/configure nimbus-team") or cmd_lower == "/configure":
            _configure_team()
            continue
        elif cmd == "/team-info":
            _show_team_info()
            continue
        elif cmd == "/team":
            parts = user_input.split(" ", 1)
            if len(parts) > 1 and parts[1].strip():
                _run_team(parts[1].strip(), agent.session)
            else:
                console.print("[dim]Usage: /team <your task description>[/dim]")
            continue

        # Run agent
        try:
            console.print()
            iteration_count = [0]

            def on_thinking():
                iteration_count[0] += 1
                if iteration_count[0] == 1:
                    console.print("  [dim]Thinking...[/dim]")
                else:
                    console.print(f"  [dim]Thinking... (iteration {iteration_count[0]})[/dim]")

            def on_tool_call(name, args):
                args_preview = str(args)
                if len(args_preview) > 120:
                    args_preview = args_preview[:120] + "..."
                console.print(f"  [yellow]>> Tool: {name}[/yellow]")
                console.print(f"     [dim]{args_preview}[/dim]")

            def on_tool_result(name, result):
                lines = result.strip().split("\n")
                preview_lines = lines[:5]
                preview = "\n".join(f"     [dim]{l[:100]}[/dim]" for l in preview_lines)
                if len(lines) > 5:
                    preview += f"\n     [dim]... +{len(lines) - 5} more lines[/dim]"
                console.print(f"  [green]<< {name}[/green] [dim]returned[/dim]")
                console.print(preview)

            response = agent.run(
                user_input,
                on_thinking=on_thinking,
                on_tool_call=on_tool_call,
                on_tool_result=on_tool_result,
            )

            console.print()
            console.print("[bold cyan]Agent >[/bold cyan]")
            try:
                console.print(Markdown(response))
            except Exception:
                console.print(response)

        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted.[/dim]")
            continue
        except Exception as e:
            console.print(f"\n[bold red]Error: {type(e).__name__}: {str(e)}[/bold red]")
            continue


def _show_help():
    """Show available commands."""
    help_text = """
[bold]Commands:[/bold]
  /help                    Show this help
  /skills                  List all available tools
  /config                  Show current setup
  /model <name>            Switch active model
  /save                    Save current memory state
  /load <id>               Load past memory state
  /history                 List saved memory states
  /new                     Start fresh memory state
  /clear                   Wipe current memory
  /compact-memory          Summarize and compress memory
  /token                   Show session token usage

[bold]NimbusTeam:[/bold]
  /configure nimbus-team   Setup multi-agent team (Boss -> Managers -> Workers)
  /team <task>             Delegate a task to NimbusTeam
  /team-info               Show current team configuration

  exit                     Save and exit
"""
    console.print(help_text)


# ─── One-shot Command ──────────────────────────────────────────────
def cmd_do(task: str):
    """Execute a one-shot agent task."""
    config = load_config()
    provider_id = config.get("provider", "openrouter")
    model = config.get("model", "google/gemma-4-31b-it:free")

    if not get_api_key(provider_id):
        console.print(f"[bold red]No API key set. Run: python main.py setup[/bold red]")
        return

    register_all_skills()
    console.print(f"[dim]Task: {task}[/dim]")
    agent = Agent(provider_id, model)

    try:
        console.print()
        iteration_count = [0]

        def on_thinking():
            iteration_count[0] += 1
            if iteration_count[0] == 1:
                console.print("  [dim]Thinking...[/dim]")
            else:
                console.print(f"  [dim]Thinking... (iteration {iteration_count[0]})[/dim]")

        def on_tool_call(name, args):
            args_preview = str(args)
            if len(args_preview) > 120:
                args_preview = args_preview[:120] + "..."
            console.print(f"  [yellow]>> Tool: {name}[/yellow]")
            console.print(f"     [dim]{args_preview}[/dim]")

        def on_tool_result(name, result):
            lines = result.strip().split("\n")
            preview_lines = lines[:5]
            preview = "\n".join(f"     [dim]{l[:100]}[/dim]" for l in preview_lines)
            if len(lines) > 5:
                preview += f"\n     [dim]... +{len(lines) - 5} more lines[/dim]"
            console.print(f"  [green]<< {name}[/green] [dim]returned[/dim]")
            console.print(preview)

        response = agent.run(task, on_thinking=on_thinking, on_tool_call=on_tool_call, on_tool_result=on_tool_result)
        console.print()
        console.print(Markdown(response))
    except Exception as e:
        console.print(f"[bold red]Error: {str(e)}[/bold red]")


# ─── Main Entry Point ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="NimbusCLI -- Personal AI Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="chat",
        choices=["chat", "setup", "config", "skills", "do"],
        help="Command to run (default: chat)",
    )
    parser.add_argument(
        "task",
        nargs="*",
        help="Task description (for 'do' command)",
    )

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup()
    elif args.command == "config":
        cmd_config()
    elif args.command == "skills":
        cmd_skills()
    elif args.command == "do":
        task = " ".join(args.task) if args.task else ""
        if not task:
            console.print("[red]Please specify a task: python main.py do \"your task here\"[/red]")
            return
        cmd_do(task)
    else:
        cmd_chat()


if __name__ == "__main__":
    main()
