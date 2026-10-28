"""Settings this module declares (resolved category > project > system > default)."""

from typing import Literal

from mindgrid.core.settings_registry import Scope, define

ANSWER_LLM = define(
    "answer.llm",
    Literal["none", "gemini", "local"],
    "none",
    {Scope.SYSTEM, Scope.PROJECT},
    "Who writes server-side answers: none (return the Context Pack only), gemini (needs the "
    "Gemini key) or local (an Ollama server).",
)
