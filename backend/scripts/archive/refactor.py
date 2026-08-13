import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

MODULES = [
    "api",
    "core",
    "db",
    "schemas",
    "services",
    "workers",
    "agents",
    "integrations",
    "memory"
]

def refactor_imports(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    
    original = content
    
    for mod in MODULES:
        # Regex to match `from <mod>` or `from <mod>.something`
        content = re.sub(rf"^from {mod}(\.|\s)", rf"from app.{mod}\1", content, flags=re.MULTILINE)
        # Regex to match `import <mod>` or `import <mod>.something`
        content = re.sub(rf"^import {mod}(\.|\s)", rf"import app.{mod}\1", content, flags=re.MULTILINE)

    if content != original:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Refactored: {file_path}")

def main():
    for root, dirs, files in os.walk(ROOT):
        if ".venv" in root or "__pycache__" in root or ".pytest_cache" in root or ".git" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                refactor_imports(os.path.join(root, file))

if __name__ == "__main__":
    main()
