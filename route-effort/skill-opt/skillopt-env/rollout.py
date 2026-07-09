"""route-effort rollout — effort level routing classification.

The skill receives a task description and must output the appropriate
effort level (low/medium/high/xhigh/max) in <effort>...</effort> tags.

Public API
----------
- :func:`process_one`  — run + evaluate one routing task
- :func:`run_batch`    — parallel execution of a list of items
"""
from __future__ import annotations

import json
import os
import re
import time
from collections import Counter
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from pathlib import Path

from skillopt.model import chat_target
from skillopt.prompts import load_prompt


# ── Prompt templates ────────────────────────────────────────────────────────

SYSTEM_PROMPT_TEMPLATE = load_prompt("system", env="route_effort")
USER_PROMPT_TEMPLATE = load_prompt("user", env="route_effort")


# ── Scoring ─────────────────────────────────────────────────────────────────

EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max"]
EFFORT_SCORE = {"low": 0, "medium": 1, "high": 2, "xhigh": 3, "max": 4}


def _extract_effort(text: str) -> str | None:
    """Extract effort level from <effort>...</effort> tags."""
    match = re.search(r"<effort>\s*(\w+)\s*</effort>", text, re.IGNORECASE)
    if match:
        effort = match.group(1).lower()
        if effort in EFFORT_LEVELS:
            return effort
    return None


def _score_effort(predicted: str | None, expected: str) -> tuple[int, float]:
    """Score predicted effort level.

    Returns:
        hard: 1 if exact match, 0 otherwise
        soft: distance-based score (1.0 for exact, decreases with distance)
    """
    if predicted is None or expected not in EFFORT_SCORE:
        return 0, 0.0

    if predicted not in EFFORT_SCORE:
        return 0, 0.0

    if predicted == expected:
        return 1, 1.0

    # Distance-based soft score: max distance is 4 (low vs max)
    distance = abs(EFFORT_SCORE[predicted] - EFFORT_SCORE[expected])
    soft_score = max(0.0, 1.0 - (distance / 4.0))

    return 0, soft_score


# ── Single-item execution ───────────────────────────────────────────────────

def process_one(
    item: dict,
    skill_content: str,
    exec_timeout: int = 120,
    max_completion_tokens: int = 4096,
) -> dict:
    """Process one route-effort task.

    Args:
        item: Task dict with "id", "query", and optional "expected_effort"
        skill_content: The skill prompt/instructions
        exec_timeout: Timeout in seconds
        max_completion_tokens: Max tokens for model response

    Returns:
        Result dict with id, query, predicted_effort, expected_effort,
        correct (0/1), soft_score, raw_output
    """
    task_id = item.get("id", "unknown")
    query = item.get("query", "")
    expected = item.get("expected_effort")

    # Build prompt
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(skill=skill_content)
    user_prompt = USER_PROMPT_TEMPLATE.format(task_description=query)

    # Call model
    start = time.time()
    try:
        response, _ = chat_target(
            system=system_prompt,
            user=user_prompt,
            max_completion_tokens=max_completion_tokens,
            timeout=exec_timeout,
        )
        raw_output = response
        elapsed = time.time() - start
        timed_out = False
    except Exception as e:
        raw_output = f"ERROR: {e}"
        elapsed = time.time() - start
        timed_out = True

    # Extract and score
    predicted = _extract_effort(raw_output)
    hard_score, soft_score = _score_effort(predicted, expected) if expected else (0, 0.0)

    return {
        "id": task_id,
        "query": query,
        "expected_effort": expected,
        "predicted_effort": predicted,
        "hard": hard_score,
        "soft": soft_score,
        "raw_output": raw_output,
        "elapsed": elapsed,
        "timed_out": timed_out,
    }


# ── Batch execution with parallelism ────────────────────────────────────────

def run_batch(
    items: list[dict],
    out_root: str,
    skill_content: str,
    exec_timeout: int = 120,
    workers: int = 8,
    max_completion_tokens: int = 4096,
    diagnostic_mode: bool = False,
    diagnostic_instruction: str = "",
    diagnostic_trace_context_by_id: dict | None = None,
    task_timeout: int = 120,
) -> list[dict]:
    """Run route-effort classification on a batch of items in parallel.

    Args:
        items: List of task dicts
        out_root: Output directory for results
        skill_content: The skill prompt
        exec_timeout: Timeout per item
        workers: Parallel workers
        max_completion_tokens: Max tokens per response
        diagnostic_mode: Unused (for API compatibility)
        diagnostic_instruction: Unused
        diagnostic_trace_context_by_id: Unused
        task_timeout: Unused (same as exec_timeout)

    Returns:
        List of result dicts
    """
    out_dir = Path(out_root)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "rollout.jsonl"

    # Resume: load existing results
    completed_ids = set()
    existing_results = []
    if out_file.exists():
        with open(out_file, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    res = json.loads(line)
                    existing_results.append(res)
                    completed_ids.add(res["id"])
        print(f"[rollout] 恢复: {len(completed_ids)} 条已完成", flush=True)

    # Filter pending items
    pending = [item for item in items if item.get("id") not in completed_ids]
    if not pending:
        print("[rollout] 所有任务已完成", flush=True)
        return existing_results

    print(f"[rollout] 处理 {len(pending)}/{len(items)} 任务 (workers={workers})", flush=True)

    results = existing_results.copy()
    correct_count = sum(r.get("correct", 0) for r in existing_results)
    completed = len(existing_results)
    total = len(items)

    # Parallel execution
    with open(out_file, "a", encoding="utf-8") as outf:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {
                ex.submit(
                    process_one,
                    item,
                    skill_content,
                    exec_timeout,
                    max_completion_tokens,
                ): item
                for item in pending
            }

            try:
                while futs:
                    done, _ = wait(futs, timeout=exec_timeout + 5, return_when=FIRST_COMPLETED)

                    for fut in done:
                        item = futs.pop(fut)
                        try:
                            res = fut.result(timeout=1)
                        except Exception as e:
                            res = {
                                "id": item.get("id", "unknown"),
                                "query": item.get("query", ""),
                                "expected_effort": item.get("expected_effort"),
                                "predicted_effort": None,
                                "correct": 0,
                                "soft_score": 0.0,
                                "raw_output": f"EXCEPTION: {e}",
                                "elapsed": 0,
                                "timed_out": True,
                            }

                        results.append(res)
                        correct_count += res.get("correct", 0)
                        completed += 1
                        acc = correct_count / completed if completed else 0

                        status = "✓" if res.get("correct") else "✗"
                        print(
                            f"    [rollout] {completed}/{total} "
                            f"(acc={acc:.3f}) id={res['id']} {status} "
                            f"predicted={res['predicted_effort']} expected={res['expected_effort']}",
                            flush=True,
                        )

                        outf.write(json.dumps(res, ensure_ascii=False) + "\n")
                        outf.flush()
            finally:
                ex.shutdown(wait=False, cancel_futures=True)

    print(f"[rollout] 完成! 准确率={correct_count}/{total}={correct_count/total:.3f}", flush=True)
    return results
