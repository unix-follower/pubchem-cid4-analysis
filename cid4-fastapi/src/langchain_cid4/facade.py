from typing import Any

from sqlalchemy.ext.asyncio import AsyncEngine

from src.langchain_cid4.workflows import run_question_workflow


class LangchainApiFacade:
    def __init__(self, engine: AsyncEngine):
        self._engine = engine

    async def ask_literature_question(self) -> dict[str, Any]:
        question = (
            "What does the literature say about isopropanolamine fungicide activity?"
        )
        return await run_question_workflow(
            question,
            domains=["literature"],
            workflow="literature-rag",
            engine=self._engine,
        )
