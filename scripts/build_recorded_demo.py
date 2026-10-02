"""Build public numerical demo fixtures offline. No provider or corpus downloads.

Only released API-shaped outputs are retained, not provider requests/responses,
cost logs, session history or private documentary passages. This is a recorded
demonstration, never a live AI answer or a replacement for backend verification.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.api.metadata import product_metadata
from src.api.service import GraphService
from src.api.sessions import SessionStore
from src.api.settings import AppSettings

QUESTIONS = (
    "What were Henkel H1 2026 sales?",
    "What was Siemens revenue in Q2 2026?",
    "Calculate the difference between Henkel H1 2025 sales and H1 2026 sales.",
    "How did Mercedes-Benz Group revenue change from Q2 2025 to Q2 2026?",
    "What drove Mercedes-Benz Cars adjusted EBIT in Q2 2026?",
    "What drove Henkel organic sales growth in H1 2026?",
    "How does Henkel define organic sales growth?",
    "How does Siemens define Industrial Business profit?",
    "What did management say about Mercedes-Benz Cars adjusted EBIT in Q2 2026?",
    "What did management say about Henkel organic sales growth in H1 2026?",
    "Where does the Henkel sales figure for H1 2026 come from?",
    "Show the source for Henkel sales in H1 2026",
    "How much Mercedes-Benz Cars EBIT was due to price alone in Q2 2026?",
    "What were Henkel sales?",
    "What will Henkel sales be next year?",
)

async def build():
    settings = AppSettings(app_mode="demo", public_demo=True, checkpoint_backend="memory", session_db_path="")
    service = GraphService(settings, session_store=SessionStore(None))
    responses = {}
    for i, question in enumerate(QUESTIONS):
        response = await service.query(question, f"recorded_{i}", None)
        payload = response.model_dump(mode="json")
        payload.update(request_id="recorded", session_id="recorded", provider="sample", model="recorded-numerical-demo", latency_ms=0)
        payload["execution"].update(provider_calls=0, input_tokens=0, output_tokens=0, cost_usd="0", stages=[])
        if payload["status"] != "COMPLETED":
            payload["verification"] = None
        responses[question] = payload
    metadata = product_metadata(settings).model_dump(mode="json")
    metadata["provider_mode"] = "test"
    destination = ROOT / "frontend/src/lib/recorded.json"
    destination.write_text(json.dumps({"metadata": metadata, "responses": responses}, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"fixtures": len(responses), "outcomes": {q: r["status"] for q, r in responses.items()}}, indent=2))

if __name__ == "__main__":
    asyncio.run(build())
