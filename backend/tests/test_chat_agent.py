from unittest.mock import AsyncMock, patch

import pytest
from google.genai import types
from httpx import AsyncClient


@pytest.fixture
def mock_gemini_client():
    with patch("app.agents.llm_provider.get_client") as mock_get_client1, patch("app.agents.orchestrator.get_client") as mock_get_client2:
        mock_client = AsyncMock()
        mock_response_intent = AsyncMock()
        mock_response_intent.text = '{"intent": "generic_chat", "confidence": 1.0, "entities": {}, "constraints": [], "required_capabilities": [], "ambiguities": [], "routing_decision": "DIRECT_EXECUTION"}'
        mock_response_intent.function_calls = None
        mock_response_intent.candidates = []

        mock_response_text = AsyncMock()
        mock_response_text.text = "I have created the task."
        mock_response_text.function_calls = None
        mock_response_text.candidates = []

        mock_client.aio.models.generate_content.side_effect = [mock_response_intent, mock_response_text]
        mock_get_client1.return_value = mock_client
        mock_get_client2.return_value = mock_client

        yield mock_client

@pytest.mark.asyncio
async def test_chat_basic_response(client: AsyncClient, mock_gemini_client):
    # Setup user
    import uuid
    username = f"test_chat_user_{uuid.uuid4().hex[:8]}"
    setup_res = await client.post("/api/v1/auth/login", json={"name": username})
    assert setup_res.status_code == 200, setup_res.text
    token = setup_res.json()["token"]
    
    with patch("app.agents.orchestrator.embed_text") as mock_embed:
        mock_embed.return_value = [0.1] * 3072
        
        # Send a basic chat message
        res = await client.post(
            "/api/v1/chat",
            json={"message": "create a task to buy groceries"},
            headers={"Authorization": f"Bearer {token}"}
        ) # Mocking memory vector search so we don't try to connect to missing services
    
    chat_res = res
    assert chat_res.status_code == 200
    assert "response" in chat_res.json()
    assert "I've started" in chat_res.json()["response"]
