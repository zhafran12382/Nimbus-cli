# NimbusCLI Skills Module
from skills.base import BaseSkill

# Registry of all available skills
SKILL_REGISTRY: dict[str, BaseSkill] = {}


def register_skill(skill: BaseSkill):
    """Register a skill instance into the global registry."""
    SKILL_REGISTRY[skill.name] = skill


def get_all_tools_schema() -> list[dict]:
    """Get OpenAI-compatible tool schemas for all registered skills."""
    tools = []
    for skill in SKILL_REGISTRY.values():
        tools.append({
            "type": "function",
            "function": skill.get_schema(),
        })
    return tools


def execute_skill(name: str, arguments: dict) -> str:
    """Execute a skill by name with given arguments."""
    if name not in SKILL_REGISTRY:
        return f"Error: Unknown skill '{name}'. Available: {', '.join(SKILL_REGISTRY.keys())}"
    
    try:
        return SKILL_REGISTRY[name].execute(**arguments)
    except Exception as e:
        return f"Error executing {name}: {type(e).__name__}: {str(e)}"
