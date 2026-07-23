from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from db.models import User, Contact, Conversation, ActionLog
from memory.embeddings import embed_text
from memory.retrieval import search_similar_memory
from agents.prompts import build_system_instruction
from agents.gemini_client import start_chat
from google.genai import types
from agents.tool_registry import SENORITA_TOOLS, execute_tool
from db.session import async_session_factory
from core.state import get_pause_state
import asyncio
import json

async def _implicit_capture_routine(user_id: UUID, message_text: str, final_text: str, sensitivity: str):
    if sensitivity == 'off' or get_pause_state():
        return
        
    prompt = f"""Analyze the following exchange. Did the user mention a durable fact about their life worth remembering that wasn't already explicitly stored? 
If yes, extract it as a single sentence. Return ONLY a JSON object with:
'has_fact': boolean,
'fact': string (the sentence),
'category': string (one of: person, preference, date, promise, context),
'confidence': float (0.0 to 1.0)

User: {message_text}
Assistant: {final_text}
"""
    try:
        chat = start_chat()
        response = await chat.send_message(prompt)
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:-3]
        elif text.startswith("```"):
            text = text[3:-3]
        data = json.loads(text)
        
        has_fact = data.get("has_fact")
        confidence = float(data.get("confidence", 0.0))
        fact = data.get("fact")
        category = data.get("category", "context")
        
        if not has_fact or not fact:
            return
            
        if sensitivity == 'conservative' and confidence < 0.8:
            return
            
        # Store it implicitly
        async with async_session_factory() as session:
            # We need to import MemoryEntry locally to avoid circular import if needed, but it's not imported here yet. Wait, we imported it in tool_registry, but we need it here.
            from db.models import MemoryEntry
            embedding = await embed_text(fact, task_type="RETRIEVAL_DOCUMENT")
            mem = MemoryEntry(
                user_id=user_id,
                content=fact,
                category=category,
                source_ref='implicit_capture',
                embedding=embedding
            )
            session.add(mem)
            await session.commit()
    except Exception as e:
        print(f"Implicit capture failed: {e}")

async def handle_message(session: AsyncSession, user: User, message_text: str) -> str:
    # a. Embed message_text
    query_embedding = await embed_text(message_text, task_type="RETRIEVAL_QUERY")
    
    # b. search_similar_memory for top-5 context
    memories = await search_similar_memory(session, user.id, query_embedding, top_k=5)
    
    # c. Fetch the user's contacts
    stmt_contacts = select(Contact).where(Contact.user_id == user.id)
    res_contacts = await session.execute(stmt_contacts)
    contacts = list(res_contacts.scalars().all())
    
    # d. Fetch the last 10 conversation rows, and most recent gemini_interaction_id
    stmt_conv = select(Conversation).where(Conversation.user_id == user.id).order_by(Conversation.created_at.desc()).limit(10)
    res_conv = await session.execute(stmt_conv)
    conv_history = list(res_conv.scalars().all())
    
    previous_interaction_id = None
    for c in conv_history:
        if c.gemini_interaction_id:
            previous_interaction_id = c.gemini_interaction_id
            break
            
    # e. Build system instruction
    sys_inst = build_system_instruction(user, memories, contacts)
    
    # Add system instruction to the text, since the new SDK interactions doesn't accept system instructions easily in create().
    # Actually, we passed it to start_chat.
    # Re-construct chat history to resume state if needed, or just let it run.
    chat = start_chat(tools=SENORITA_TOOLS, system_instruction=sys_inst)
    
    # Track the new interaction id
    new_interaction_id = previous_interaction_id
    
    # For now, pass conversation history
    history = []
    # reverse conv_history to chronological order
    conv_history.reverse()
    for c in conv_history:
        if c.role == "user":
            history.append(types.Content(role="user", parts=[types.Part.from_text(text=c.content)]))
        else:
            history.append(types.Content(role="model", parts=[types.Part.from_text(text=c.content)]))
            
    # set chat history
    chat._history = history
    
    response = await chat.send_message(message_text)
    
    # g. Loop up to 5 times
    for _ in range(5):
        function_calls = response.function_calls
        if not function_calls:
            break
            
        function_responses = []
        for fc in function_calls:
            fn_name = fc.name
            args = fc.args
            
            # Write action_log 'pending'
            action = ActionLog(
                user_id=user.id,
                action_type=fn_name,
                payload=args,
                result="pending"
            )
            session.add(action)
            await session.flush()
            
            # Execute tool
            tool_res = await execute_tool(session, user.id, fn_name, args)
            
            if "error" in tool_res:
                action.result = "failed"
            else:
                action.result = "success"
                
            await session.commit()
            
            function_responses.append(
                types.Part.from_function_response(name=fn_name, response=tool_res)
            )
            
        # Send function results back
        response = await chat.send_message(function_responses)
        
    # h. Persist to conversations table
    final_text = response.text or ""
    
    # Save user message
    user_conv = Conversation(
        user_id=user.id,
        gemini_interaction_id=new_interaction_id,
        role="user",
        content=message_text
    )
    session.add(user_conv)
    
    # Save assistant message
    asst_conv = Conversation(
        user_id=user.id,
        gemini_interaction_id=new_interaction_id,
        role="assistant",
        content=final_text
    )
    session.add(asst_conv)
    
    await session.commit()
    
    # Implicit capture trigger (Module 4)
    asyncio.create_task(
        _implicit_capture_routine(
            user_id=user.id, 
            message_text=message_text, 
            final_text=final_text, 
            sensitivity=user.memory_capture_sensitivity
        )
    )
    
    return final_text
