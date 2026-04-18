"""
NimbusCLI - Skill Creator Skill
AI can design and generate new skills at runtime, then register them immediately.
"""

import os
import re
import importlib
import importlib.util
from pathlib import Path
from skills.base import BaseSkill


GENERATED_SKILLS_DIR = Path(__file__).parent.parent / "generated_skills"


class SkillCreator(BaseSkill):
    name = "create_skill"
    description = (
        "Create a brand new custom skill/tool at runtime. Provide the skill name, "
        "a description, and the full Python source code. The code MUST define a class "
        "that inherits from BaseSkill with 'name', 'description' attributes and "
        "'get_parameters()' and 'execute()' methods. The new skill will be saved to "
        "the generated_skills directory and registered immediately for use. "
        "Example: creating a skill to compress images, convert formats, parse CSV, etc."
    )

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "skill_name": {
                    "type": "string",
                    "description": "Snake_case name for the skill file (e.g., 'image_compressor').",
                },
                "skill_description": {
                    "type": "string",
                    "description": "Brief description of what the skill does.",
                },
                "source_code": {
                    "type": "string",
                    "description": (
                        "Complete Python source code for the skill. Must define a class "
                        "inheriting from BaseSkill. Import BaseSkill from skills.base."
                    ),
                },
            },
            "required": ["skill_name", "skill_description", "source_code"],
        }

    def execute(self, skill_name: str, skill_description: str, source_code: str) -> str:
        # Sanitize skill name
        skill_name = re.sub(r"[^a-z0-9_]", "_", skill_name.lower().strip())
        if not skill_name:
            return "[ERROR] Invalid skill name."

        # Ensure generated_skills directory exists
        GENERATED_SKILLS_DIR.mkdir(parents=True, exist_ok=True)
        init_file = GENERATED_SKILLS_DIR / "__init__.py"
        if not init_file.exists():
            init_file.write_text("# Auto-generated skills\n")

        # Save the skill file
        skill_file = GENERATED_SKILLS_DIR / f"{skill_name}.py"
        try:
            skill_file.write_text(source_code, encoding="utf-8")
        except Exception as e:
            return f"[ERROR] Failed to write skill file: {str(e)}"

        # Try to load and register the skill
        try:
            spec = importlib.util.spec_from_file_location(
                f"generated_skills.{skill_name}", str(skill_file)
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find the BaseSkill subclass in the module
            skill_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (
                    isinstance(attr, type)
                    and issubclass(attr, BaseSkill)
                    and attr is not BaseSkill
                ):
                    skill_class = attr
                    break

            if not skill_class:
                return (
                    f"[ERROR] No BaseSkill subclass found in the code. "
                    f"File saved at: {skill_file}\n"
                    f"The code must define a class inheriting from BaseSkill."
                )

            # Instantiate and register
            from skills import register_skill
            skill_instance = skill_class()
            register_skill(skill_instance)

            return (
                f"[OK] Skill '{skill_instance.name}' created and registered!\n"
                f"  File: {skill_file}\n"
                f"  Description: {skill_instance.description}\n"
                f"  The skill is now available for use in this session."
            )

        except Exception as e:
            return (
                f"[ERROR] Skill file saved but failed to load: {type(e).__name__}: {str(e)}\n"
                f"  File: {skill_file}\n"
                f"  Please check the source code for errors."
            )
