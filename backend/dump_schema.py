from google.genai import types
from agents.tool_registry import SENORITA_TOOLS
from google.genai._api_client import ApiClient

# The _api_client has some model conversion logic. 
# But wait, in version 1.0.0, types.Tool(function_declarations=...) takes python callables directly!
tool = types.Tool(function_declarations=SENORITA_TOOLS)
print(tool.model_dump(exclude_unset=True))
