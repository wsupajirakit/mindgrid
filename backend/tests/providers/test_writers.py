"""Answer writers: the Ollama client against a local HTTP server speaking Ollama's chat
API, and the Gemini request shape through a stand-in client (no network, no key)."""

import asyncio
import json
import sys
import types
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest

from mindgrid.providers.llm.base import Prompt, WriterError
from mindgrid.providers.llm.gemini import GeminiWriter
from mindgrid.providers.llm.ollama import OllamaWriter

pytestmark = pytest.mark.anyio
SEEN: list[dict[str, Any]] = []


async def _serve(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    head = await reader.readuntil(b"\r\n\r\n")
    length = int(
        next(
            line.split(b":")[1]
            for line in head.split(b"\r\n")
            if line.lower().startswith(b"content-length")
        )
    )
    body = json.loads(await reader.readexactly(length))
    SEEN.append(body)
    content = "" if body["messages"][1]["content"] == "empty" else "Yields rose [P1]."
    reply = json.dumps({"message": {"role": "assistant", "content": content}}).encode()
    writer.write(
        b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
        + f"Content-Length: {len(reply)}\r\nConnection: close\r\n\r\n".encode()
        + reply
    )
    await writer.drain()
    writer.close()


@pytest.fixture
async def ollama() -> AsyncIterator[str]:
    server = await asyncio.start_server(_serve, "127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    yield f"http://127.0.0.1:{port}"
    server.close()
    await server.wait_closed()


async def test_ollama_sends_rules_as_system_and_reads_reply(ollama: str) -> None:
    SEEN.clear()
    writer = OllamaWriter(ollama, "qwen3:8b")
    assert await writer.write(Prompt("rules", "Passages ... Question: q")) == "Yields rose [P1]."
    sent = SEEN[0]
    assert (sent["model"], sent["stream"], sent["think"]) == ("qwen3:8b", False, False)
    assert [m["role"] for m in sent["messages"]] == ["system", "user"]
    assert sent["options"]["temperature"] == 0.1
    assert sent["options"]["num_ctx"] == 16384  # never Ollama's silent 4096 default
    with pytest.raises(WriterError, match="no text"):
        await writer.write(Prompt("rules", "empty"))


def test_ollama_prompt_room_follows_the_context_window(env: Callable[..., None]) -> None:
    env(MINDGRID_LLM_LOCAL_CONTEXT_TOKENS="8192", MINDGRID_LLM_MAX_OUTPUT_TOKENS="2048")
    assert OllamaWriter("http://127.0.0.1:9", "m").max_prompt_chars == 9216  # 6144 x 1.5


async def test_ollama_unreachable_is_a_writer_error() -> None:
    with pytest.raises(WriterError, match="unavailable"):
        await OllamaWriter("http://127.0.0.1:9", "m").write(Prompt("s", "u"))


async def test_gemini_request_shape(
    monkeypatch: pytest.MonkeyPatch, env: Callable[..., None]
) -> None:
    env(MINDGRID_LLM_MAX_OUTPUT_TOKENS="512")
    calls: list[dict[str, Any]] = []

    class Models:
        async def generate_content(self, **kw: Any) -> Any:
            calls.append(kw)
            return types.SimpleNamespace(text="ok [P1]")

    class Client:
        def __init__(self, api_key: str) -> None:
            assert api_key == "k"
            self.aio = types.SimpleNamespace(models=Models())

    from google import genai  # noqa: PLC0415 — patched for this test only

    monkeypatch.setattr(genai, "Client", Client)
    assert "google.genai" in sys.modules
    out = await GeminiWriter("k", "gemini-flash-latest").write(Prompt("rules", "question"))
    assert out == "ok [P1]"
    config = calls[0]["config"]
    assert (calls[0]["model"], calls[0]["contents"]) == ("gemini-flash-latest", "question")
    assert (config.system_instruction, config.max_output_tokens) == ("rules", 512)
