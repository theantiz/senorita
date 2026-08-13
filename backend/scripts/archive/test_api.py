import asyncio
import json

from google.genai import types

from app.agents.tool_registry import SENORITA_TOOLS

config = types.GenerateContentConfig(tools=SENORITA_TOOLS)
print("Before mutation:")
print(json.dumps(config.model_dump(exclude_unset=True), indent=2)[:500])

if config.tools:
    for tool in config.tools:
        if tool.function_declarations:
            for fd in tool.function_declarations:
                fd.name = f"default_api:{fd.name}"

print("\nAfter mutation:")
print(json.dumps(config.model_dump(exclude_unset=True), indent=2)[:500])
