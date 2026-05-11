import asyncio
import numpy as np
from typing import List, Dict
from backend.llm.ollama_client import ollama_client
from backend.config.settings import get_settings

settings = get_settings()

class RAPTORService:
    def __init__(self):
        self.summary_model = settings.ollama_model
        self.cluster_size = 5 # Chunks per summary

    async def summarize_chunks(self, chunks: List[str]) -> str:
        combined_text = "\n\n".join(chunks)
        prompt = f"Summarize the following text concisely, capturing all key facts and entities. This will be used for hierarchical indexing. \n\nTEXT:\n{combined_text}"
        summary = await ollama_client.generate(prompt, model=self.summary_model)
        return summary

    async def build_hierarchy(self, chunks: List[Dict]) -> List[Dict]:
        """
        Builds a one-level hierarchy of summaries for the given chunks.
        In a full RAPTOR implementation, this would be recursive.
        """
        if len(chunks) <= self.cluster_size:
            return [] # No need to summarize if few chunks

        # Simple clustering: group by sequential order (assuming they are from the same doc)
        # In better implementation, use K-Means on embeddings.
        summaries = []
        for i in range(0, len(chunks), self.cluster_size):
            batch = chunks[i:i + self.cluster_size]
            batch_texts = [c["text"] for c in batch]
            summary_text = await self.summarize_chunks(batch_texts)
            
            # Create a 'summary chunk'
            summary_chunk = {
                "chunk_id": f"summary_{i}_{batch[0]['chunk_id']}",
                "text": f"[SUMMARY] {summary_text}",
                "document": batch[0].get("document", "Summary"),
                "metadata": {
                    "is_summary": True,
                    "source_chunks": [c["chunk_id"] for c in batch],
                    "session_id": batch[0].get("metadata", {}).get("session_id")
                }
            }
            summaries.append(summary_chunk)
            
        return summaries

raptor_service = RAPTORService()
