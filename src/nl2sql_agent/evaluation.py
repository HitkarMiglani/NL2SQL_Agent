"""LLM-as-judge scoring for NL2SQL agent responses.

Runs a lightweight second LLM pass that scores the generated SQL/summary
against the original question. Traced as its own LangSmith run via
`tracing.traceable` so scores show up alongside the agent trace.
"""
from __future__ import annotations

import json
import re
from typing import Any, TypedDict

import pandas as pd

from .logging_utils import get_logger
from .tracing import traceable

logger = get_logger("EVALUATION")

_JSON_BLOCK_PATTERN = re.compile(r"\{.*\}", re.DOTALL)


class JudgeScore(TypedDict):
    overall_score: int
    correctness: int
    relevance: int
    clarity: int
    rationale: str


def _build_judge_prompt(question: str, sql_query: str, result_preview: str, summary: str) -> str:
    return (
        "You are an impartial judge evaluating the quality of an AI-generated SQL answer.\n"
        "Score the response on three dimensions from 1 (poor) to 5 (excellent):\n"
        "- correctness: does the SQL plausibly answer the question given the result preview?\n"
        "- relevance: does the summary address the user's question?\n"
        "- clarity: is the summary clear and business-friendly?\n\n"
        f"User question: {question}\n\n"
        f"Generated SQL:\n{sql_query}\n\n"
        f"Result preview:\n{result_preview}\n\n"
        f"Generated summary:\n{summary}\n\n"
        "Respond with strict JSON only, no markdown fences, in this exact shape:\n"
        '{"correctness": <1-5>, "relevance": <1-5>, "clarity": <1-5>, "rationale": "<one sentence>"}'
    )


def _parse_judge_response(raw_text: str) -> JudgeScore | None:
    match = _JSON_BLOCK_PATTERN.search(raw_text)
    if not match:
        return None
    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None

    try:
        correctness = int(payload["correctness"])
        relevance = int(payload["relevance"])
        clarity = int(payload["clarity"])
    except (KeyError, TypeError, ValueError):
        return None

    correctness = min(5, max(1, correctness))
    relevance = min(5, max(1, relevance))
    clarity = min(5, max(1, clarity))

    return {
        "overall_score": round((correctness + relevance + clarity) / 3),
        "correctness": correctness,
        "relevance": relevance,
        "clarity": clarity,
        "rationale": str(payload.get("rationale", "")).strip(),
    }


@traceable(name="judge_response", run_type="llm")
def judge_response(
    question: str,
    sql_query: str,
    db_result: pd.DataFrame | None,
    summary: str,
    llm_client: Any,
) -> JudgeScore | None:
    """Ask the LLM to score its own generated SQL/summary as an independent judge pass."""
    if db_result is None or not isinstance(db_result, pd.DataFrame) or db_result.empty:
        preview = "No rows."
    else:
        preview = db_result.head(5).to_string(index=False)

    prompt = _build_judge_prompt(question, sql_query, preview, summary)

    try:
        raw_response = llm_client.generate_text(prompt)
    except Exception as exc:  # noqa: BLE001 - judge failures must never break the main flow
        logger.warning("LLM judge call failed: %s", exc)
        return None

    score = _parse_judge_response(raw_response)
    if score is None:
        logger.warning("LLM judge returned an unparsable response: %s", raw_response[:200])
    return score
