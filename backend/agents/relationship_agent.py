from typing import Any
from backend.llm.ollama_client import ollama_client
from backend.config.settings import get_settings
from backend.models.entities import Relationship, UploadedDocument
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

settings = get_settings()

async def extract_relationships(document_id: int, text: str, db: AsyncSession):
    """Analyze document content to find relationships with existing knowledge assets."""
    # 1. Fetch other documents in the system
    other_docs = (await db.execute(select(UploadedDocument).where(UploadedDocument.id != document_id))).scalars().all()
    if not other_docs:
        return

    # 2. Extract potential links using LLM
    # We provide a list of existing doc names to help the LLM identify links
    doc_names = [d.filename for d in other_docs]
    prompt = f"""Analyze this text and identify how it relates to these other knowledge assets: {doc_names}.
Text Segment: {text[:3000]}

For each relationship found, output a JSON list:
[
  {{"target_name": "filename", "type": "relates_to|supports|contradicts|explains", "description": "short reason"}}
]
If no clear relationships, return empty list []."""

    try:
        response = await ollama_client.generate(prompt, model=settings.ollama_model)
        # Extract JSON from response
        import re
        match = re.search(r"\[.*\]", response, re.DOTALL)
        if match:
            links = json.loads(match.group(0))
            for link in links:
                target_doc = next((d for d in other_docs if d.filename == link["target_name"]), None)
                if target_doc:
                    rel = Relationship(
                        source_id=document_id,
                        target_id=target_doc.id,
                        type=link["type"],
                        description=link["description"],
                        weight=0.8
                    )
                    db.add(rel)
            await db.commit()
    except Exception as e:
        print(f"GraphRAG-lite extraction failed: {e}")
