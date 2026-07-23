from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from uuid import UUID

from db.models import User, Contact, Conversation, ActionLog
from memory.embeddings import embed_text
from memory.retrieval import search_similar_memory
from agents.prompts import build_system_instruction
from agents.gemini_client import call_model
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
        interaction = call_model(input_content=prompt)
        text = interaction.text.strip()
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
    # Or actually, we can prepend it to the user message for context in this turn if needed, or pass it via config if supported.
    # We will pass it as the first message or prepend to input.
    input_content = f"[SYSTEM INSTRUCTION]\\n{sys_inst}\\n\\n[USER MESSAGE]\\n{message_text}"
    
    # f. Call gemini_client
    interaction = call_model(
        input_content=input_content,
        tools=SENORITA_TOOLS,
        previous_interaction_id=previous_interaction_id
    )
    
    # Track the new interaction id
    new_interaction_id = getattr(interaction, "interaction_id", None) or previous_interaction_id
    
    # g. Loop up to 5 times
    for _ in range(5):
        # We need to process the latest response in the interaction
        # The SDK interactions automatically handles state. We just check if it wants to call a function.
        # Wait, the `interactions.create()` returns a response.
        # Let's check `interaction.function_calls`.
        function_calls = interaction.function_calls
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
            
            # HARD NON-NEGOTIABLE CONSTRAINT:
            # Never write result='success' before the DB write is confirmed!
            # Since the tool modifies DB and returns dict without exception (or returns {"error": ...} on fail),
            # we check for "error" key.
            if "error" in tool_res:
                action.result = "failed"
            else:
                action.result = "success"
                
            await session.commit()
            
            function_responses.append({
                "name": fn_name,
                "response": tool_res
            })
            
        # Send function results back
        # SDK supports interaction.reply(function_responses=...)
        interaction = interaction.reply(function_responses=function_responses)
        
    # h. Persist to conversations table
    final_text = interaction.text or ""
    
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
