"""
NimbusCLI - Base Skill
Abstract base class for all skills/tools.
"""

from abc import ABC, abstractmethod


class BaseSkill(ABC):
    """Abstract base class for agent skills."""

    name: str = ""
    description: str = ""

    def get_schema(self) -> dict:
        """
        Return the OpenAI function-calling schema for this skill.
        Must define: name, description, parameters.
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.get_parameters(),
        }

    @abstractmethod
    def get_parameters(self) -> dict:
        """Return JSON Schema for the skill's parameters."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> str:
        """Execute the skill and return a string result."""
        pass
