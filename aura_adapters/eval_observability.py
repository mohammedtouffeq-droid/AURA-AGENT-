"""
===================================================================================
AURA ADAPTER: EVALUATION & OBSERVABILITY LAYER
===================================================================================
Curated capabilities extracted from:
- SWE-bench/SWE-bench (Reproducible Task Evaluation & Verification)
- Arize-ai/phoenix (OpenTelemetry Traces & Spans)
- promptfoo/promptfoo (Assertion Tests & Red-Teaming)
- confident-ai/deepeval (G-Eval Metric Rubric Evaluators)
- explodinggradients/ragas (RAG Faithfulness & Relevance)
===================================================================================
"""
import time
import re
from typing import Dict, Any, List, Optional, Tuple


class PhoenixSpanTracer:
    """Arize-ai/phoenix-inspired OpenTelemetry span tracer and latency profiler."""
    def __init__(self):
        self.spans: List[Dict[str, Any]] = []

    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None) -> str:
        span_id = f"span_{len(self.spans) + 1}"
        span = {
            "span_id": span_id,
            "name": name,
            "start_time": time.time(),
            "attributes": attributes or {},
            "status": "RECORDING"
        }
        self.spans.append(span)
        return span_id

    def end_span(self, span_id: str, status: str = "OK"):
        for span in self.spans:
            if span["span_id"] == span_id:
                span["end_time"] = time.time()
                span["duration_ms"] = round((span["end_time"] - span["start_time"]) * 1000, 2)
                span["status"] = status
                return span
        return None


class PromptfooAssertionEngine:
    """promptfoo-inspired LLM output assertion validator."""
    @staticmethod
    def assert_contains(text: str, expected_substring: str) -> Tuple[bool, str]:
        passed = expected_substring in text
        return passed, f"Assertion 'contains {expected_substring}' {'passed' if passed else 'failed'}."

    @staticmethod
    def assert_regex(text: str, pattern: str) -> Tuple[bool, str]:
        compiled = re.compile(pattern)
        passed = bool(compiled.search(text))
        return passed, f"Assertion 'regex {pattern}' {'passed' if passed else 'failed'}."

    @staticmethod
    def assert_not_contains(text: str, forbidden_substring: str) -> Tuple[bool, str]:
        passed = forbidden_substring not in text
        return passed, f"Assertion 'not-contains {forbidden_substring}' {'passed' if passed else 'failed'}."


class DeepEvalMetricScorer:
    """confident-ai/deepeval-inspired G-Eval metric scoring algorithm."""
    @staticmethod
    def score_completeness(expected_elements: List[str], actual_output: str) -> Dict[str, Any]:
        found = [elem for elem in expected_elements if elem.lower() in actual_output.lower()]
        score = len(found) / max(1, len(expected_elements))
        return {
            "metric": "completeness",
            "score": round(score, 2),
            "passed": score >= 0.8,
            "elements_matched": found,
            "missing_elements": [e for e in expected_elements if e not in found]
        }
