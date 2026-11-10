"""
Lightweight tracing for agent runs.

Pipeline code calls record(...) at the points worth measuring (LLM calls,
tool calls, SQL execution). Outside an active trace, record() does nothing,
so the app behaves exactly as before. The evaluation harness opens a trace
per question with start_trace() and saves its events.
"""
import time
import contextvars
from contextlib import contextmanager

_current_trace = contextvars.ContextVar("current_trace", default=None)


class Trace:
    def __init__(self, item_id: str, question: str):
        self.item_id = item_id
        self.question = question
        self.events = []
        self.final_answer = None
        self.stop_reason = None  # answered | step_limit | error
        self.error = None
        self.started = time.time()
        self.latency_s = None

    def add(self, kind: str, **data):
        data["kind"] = kind
        data["t"] = round(time.time() - self.started, 3)
        self.events.append(data)

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "question": self.question,
            "final_answer": self.final_answer,
            "stop_reason": self.stop_reason,
            "error": self.error,
            "latency_s": self.latency_s,
            "events": self.events,
        }


def record(kind: str, **data):
    """
    Adds an event to the active trace, if any.
    """
    trace = _current_trace.get()
    if trace is not None:
        trace.add(kind, **data)


@contextmanager
def start_trace(item_id: str, question: str):
    trace = Trace(item_id, question)
    token = _current_trace.set(trace)
    try:
        yield trace
    finally:
        trace.latency_s = round(time.time() - trace.started, 3)
        _current_trace.reset(token)
