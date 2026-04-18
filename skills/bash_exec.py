"""
NimbusCLI - Bash Executor Skill
Executes shell/bash commands.
"""

import subprocess
import os
import platform
from skills.base import BaseSkill


class BashExecutor(BaseSkill):
    name = "execute_bash"
    description = (
        "Execute a shell/bash command on the system. Use this for system operations, "
        "file manipulation via commands, installing packages, git operations, etc. "
        "Returns stdout and stderr output."
    )

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
                "working_directory": {
                    "type": "string",
                    "description": "Working directory for the command. Defaults to current directory.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds. Default: 30.",
                },
            },
            "required": ["command"],
        }

    def execute(self, command: str, working_directory: str = None, timeout: int = 30) -> str:
        cwd = working_directory or os.getcwd()

        # Determine shell based on platform
        is_windows = platform.system() == "Windows"
        shell_executable = None if is_windows else "/bin/bash"

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=cwd,
                executable=shell_executable,
            )

            output_parts = []
            if result.stdout.strip():
                output_parts.append(f"[STDOUT]\n{result.stdout.strip()}")
            if result.stderr.strip():
                output_parts.append(f"[STDERR]\n{result.stderr.strip()}")
            if result.returncode != 0:
                output_parts.append(f"[EXIT CODE] {result.returncode}")

            if not output_parts:
                return "[OK] Command executed successfully (no output)."

            return "\n".join(output_parts)

        except subprocess.TimeoutExpired:
            return f"[ERROR] Command timed out after {timeout} seconds."
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {str(e)}"
