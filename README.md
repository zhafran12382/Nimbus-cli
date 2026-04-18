# NimbusCLI

A lightweight but highly capable AI assistant built entirely for the terminal. No clunky web interfaces, no locked-in subscriptions. Bring your own API keys and let your models interact directly with your local system.

NimbusCLI runs on a ReAct (Reasoning + Acting) loop. It doesn't just chat—it *thinks, searches the web, writes code, and executes files* right on your machine.

## Why use this?
Nimbus was built to solve the frustration of having to copy-paste code back and forth between a browser and a code editor. It supports **OpenRouter**, **Google Gemini**, and local models, giving you the freedom to switch backends mid-conversation. 

It's entirely text-based, lightning fast, and optimized to run anywhere—from your main workstation down to Termux on an Android phone.

## Features that matter
- **Local Tool Execution:** The AI can read your directory tree, modify files, run bash/powershell commands, and search the web (via Tavily or DuckDuckGo).
- **NimbusTeam (Multi-Agent):** Break down monolithic tasks. Create a 3-tier hierarchy (Boss -> Managers -> Workers) to divide and conquer massive codebase refactors or heavy research.
- **Strict Custom Routing:** Save money on OpenRouter by manually specifying your primary and fallback providers. Nimbus strictly validates your custom routing so you don't accidentally burn credits.
- **Session Memory:** Don't lose your context. Save, load, and compact your AI's memory states directly to disk.
- **Token Tracking:** Type `/token` anytime to see exactly how much context you've used in the current session.

## Setup
You just need Python 3 and some API keys. 

1. Clone the repo and install dependencies:
```bash
git clone https://github.com/zhafran12382/NimbusCLI.git
cd NimbusCLI

pip install -r requirements.txt
```

2. Run the interactive setup wizard:
```bash
python main.py setup
```
The wizard will guide you through setting up your default provider (e.g., OpenRouter) and storing your API key securely into a local `.env` file.

3. Start your session:
```bash
python main.py chat
```

## The "NimbusTeam" Feature
The highlight of v1.2.0 is multi-agent orchestration. Instead of giving one model a giant task and hoping it doesn't get overwhelmed, use `/configure nimbus-team` to build a mini-company inside your terminal.

- **The Boss (1)**: Takes your request, figures out the core architecture, and assigns subtasks.
- **The Managers (0-2)**: Coordinates complex pipelines and reviews the workers' output.
- **The Workers (1-7)**: The specialists. Choose between Coders, Researchers, Analysts, and Creative agents that actually execute the tools.

*Pro tip: You can assign fast, cheap models (like Llama 3 8B) for Workers and powerful models (like DeepSeek V3 or Claude 3.5 Sonnet) for the Boss to optimize API costs.*

## Daily Commands
Running `python main.py chat` drops you into a REPL. From there, you can type normally or use these commands:

- `/help` : View all commands.
- `/team <task>` : Delegate a giant task to your configured NimbusTeam.
- `/model <model_name>` : Switch the active model instantly.
- `/config` : Show current model and routing info.
- `/save <id>` / `/load <id>` : Context management. 

## Custom Skills
NimbusCLI is modular. If you want the AI to learn a new trick (e.g., querying your local database), simply write a python class in the `skills/` directory.

---
*Built for hackers, by hackers.*
