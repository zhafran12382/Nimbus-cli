"""
NimbusCLI - File Manager Skill
Handles file and directory operations (read, write, list, delete, move).
"""

import os
import shutil
from pathlib import Path
from skills.base import BaseSkill


class FileManager(BaseSkill):
    name = "file_manager"
    description = (
        "Manage files and directories. Supported operations: "
        "'read' (read file content), 'write' (create/overwrite file), "
        "'append' (add to end of file), 'delete' (remove file/dir), "
        "'list' (list directory contents), 'move' (move/rename file), "
        "'copy' (copy file/dir), 'mkdir' (create directory), "
        "'exists' (check if path exists), 'info' (get file size/type info)."
    )

    def get_parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "operation": {
                    "type": "string",
                    "enum": ["read", "write", "append", "delete", "list", "move", "copy", "mkdir", "exists", "info"],
                    "description": "The file operation to perform.",
                },
                "path": {
                    "type": "string",
                    "description": "The target file or directory path.",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write (for 'write' and 'append' operations).",
                },
                "destination": {
                    "type": "string",
                    "description": "Destination path (for 'move' and 'copy' operations).",
                },
            },
            "required": ["operation", "path"],
        }

    def execute(self, operation: str, path: str, content: str = None, destination: str = None) -> str:
        path = os.path.expanduser(path)

        try:
            if operation == "read":
                return self._read(path)
            elif operation == "write":
                return self._write(path, content or "")
            elif operation == "append":
                return self._append(path, content or "")
            elif operation == "delete":
                return self._delete(path)
            elif operation == "list":
                return self._list(path)
            elif operation == "move":
                return self._move(path, destination)
            elif operation == "copy":
                return self._copy(path, destination)
            elif operation == "mkdir":
                return self._mkdir(path)
            elif operation == "exists":
                return self._exists(path)
            elif operation == "info":
                return self._info(path)
            else:
                return f"[ERROR] Unknown operation: {operation}"
        except PermissionError:
            return f"[ERROR] Permission denied: {path}"
        except Exception as e:
            return f"[ERROR] {type(e).__name__}: {str(e)}"

    def _read(self, path: str) -> str:
        if not os.path.isfile(path):
            return f"[ERROR] File not found: {path}"
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        if len(content) > 10000:
            content = content[:10000] + "\n\n[... truncated, file too large]"
        return f"[Content of {path}]\n{content}"

    def _write(self, path: str, content: str) -> str:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"[OK] Written {len(content)} chars to {path}"

    def _append(self, path: str, content: str) -> str:
        with open(path, "a", encoding="utf-8") as f:
            f.write(content)
        return f"[OK] Appended {len(content)} chars to {path}"

    def _delete(self, path: str) -> str:
        if os.path.isfile(path):
            os.unlink(path)
            return f"[OK] Deleted file: {path}"
        elif os.path.isdir(path):
            shutil.rmtree(path)
            return f"[OK] Deleted directory: {path}"
        else:
            return f"[ERROR] Path not found: {path}"

    def _list(self, path: str) -> str:
        if not os.path.isdir(path):
            return f"[ERROR] Not a directory: {path}"
        entries = sorted(os.listdir(path))
        items = []
        for entry in entries[:100]:
            full = os.path.join(path, entry)
            marker = "📁" if os.path.isdir(full) else "📄"
            try:
                size = os.path.getsize(full) if os.path.isfile(full) else ""
                size_str = f" ({self._human_size(size)})" if size else ""
            except OSError:
                size_str = ""
            items.append(f"  {marker} {entry}{size_str}")

        header = f"[Directory: {path}] ({len(entries)} items)\n"
        if len(entries) > 100:
            items.append(f"  ... and {len(entries) - 100} more")
        return header + "\n".join(items)

    def _move(self, path: str, destination: str) -> str:
        if not destination:
            return "[ERROR] Destination path required for move."
        shutil.move(path, destination)
        return f"[OK] Moved {path} -> {destination}"

    def _copy(self, path: str, destination: str) -> str:
        if not destination:
            return "[ERROR] Destination path required for copy."
        if os.path.isdir(path):
            shutil.copytree(path, destination)
        else:
            os.makedirs(os.path.dirname(destination) or ".", exist_ok=True)
            shutil.copy2(path, destination)
        return f"[OK] Copied {path} -> {destination}"

    def _mkdir(self, path: str) -> str:
        os.makedirs(path, exist_ok=True)
        return f"[OK] Created directory: {path}"

    def _exists(self, path: str) -> str:
        if os.path.exists(path):
            kind = "directory" if os.path.isdir(path) else "file"
            return f"[YES] Path exists ({kind}): {path}"
        return f"[NO] Path does not exist: {path}"

    def _info(self, path: str) -> str:
        if not os.path.exists(path):
            return f"[ERROR] Path not found: {path}"
        p = Path(path)
        stat = p.stat()
        info = [
            f"Path: {path}",
            f"Type: {'directory' if p.is_dir() else 'file'}",
            f"Size: {self._human_size(stat.st_size)}",
            f"Extension: {p.suffix or 'none'}",
        ]
        return "[File Info]\n" + "\n".join(info)

    def _human_size(self, size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
