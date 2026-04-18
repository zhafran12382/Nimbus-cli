"""
NimbusCLI - Python Executor Skill
Executes Python code in a sandboxed subprocess.
"""

import subprocess
import sys
import tempfile
import os
from skills.base import BaseSkill


class PythonExecutor(BaseSkill):
    name = "execute_python"
    description = (
        "Execute Python code. Use this to run calculations, data processing, "
        "test code snippets, or any Python script. The code runs in a subprocess. "
        "Returns stdout and stderr output."
    )

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "The Python code to execute.",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Maximum execution time in seconds. Default: 30.",
                },
            },
            "required": ["code"],
        }

    def execute(self, code: str, timeout: int = 30) -> str:
        # Write code to a temp file
        tmp_dir = tempfile.mkdtemp()
        script_path = os.path.join(tmp_dir, "nimbus_exec.py")

        try:
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(code)

            result = subprocess.run(
                [sys.executable, script_path],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=os.getcwd(),
            )

            output_parts = []
            if result.stdout.strip():
                output_parts.append(f"[STDOUT]\n{result.stdout.strip()}")
            if result.stderr.strip():
                output_parts.append(f"[STDERR]\n{result.stderr.strip()}")
            if result.returncode != 0:
                output_parts.append(f"[EXIT CODE] {result.returncode}")

            if not output_parts:
                return "[OK] Code executed successfully (no output)."

            return "\n".join(output_parts)

        except subprocess.TimeoutExpired:
            return f"[ERROR] Execution timed out after {timeout} seconds."
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {str(e)}"
        finally:
            try:
                os.unlink(script_path)
                os.rmdir(tmp_dir)
            except OSError:
                pass
