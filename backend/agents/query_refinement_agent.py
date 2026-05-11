async def refine_query(user_query: str, history: list[dict]) -> str:
    """Append recent conversation context to improve retrieval for follow-up questions."""
    if not history:
        return user_query
    # Include last 4 turns (both user and assistant) for context
    recent = history[-4:]
    contextual_parts = []
    for item in recent:
        role = item.get("role", "")
        content = item.get("content", "").strip()
        if content and role in ("user", "assistant"):
            prefix = "User" if role == "user" else "Assistant"
            contextual_parts.append(f"{prefix}: {content}")
    if not contextual_parts:
        return user_query
    context_str = " | ".join(contextual_parts)
    refined = f"{user_query}\n[Conversation context: {context_str}]"
    # Guard: don't exceed 1500 chars to avoid inflating embedding
    return refined[:1500]
