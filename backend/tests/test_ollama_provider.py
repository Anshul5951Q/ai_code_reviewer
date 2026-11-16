"""
Unit tests for Phase 7.1: OllamaProvider, OllamaInferenceQueue, and error handling.

All tests use a mocked HTTP layer (httpx.MockTransport) so they execute deterministically
without requiring Ollama to be installed or running on the development machine.
"""
from __future__ import annotations

import asyncio
import json
import pytest
import httpx
from pydantic import BaseModel, Field

from app.llm.provider import (
    InferenceTimeoutError,
    LLMProviderError,
    ModelNotFoundError,
    OllamaHealthStatus,
    OllamaInferenceQueue,
    OllamaProvider,
    ProviderUnavailableError,
    StructuredOutputError,
    extract_json_from_text,
)


class SampleOutput(BaseModel):
    summary: str
    score: int = Field(ge=0, le=100)


# 1. Successful generation
@pytest.mark.anyio
async def test_successful_generation():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["model"] == "qwen2.5-coder:7b"
        return httpx.Response(200, json={"message": {"content": "Generation succeeded."}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(base_url="http://mock-ollama:11434", client=client)
    res = await provider.complete("Test prompt")
    assert res == "Generation succeeded."


# 2. Successful structured generation
@pytest.mark.anyio
async def test_successful_structured_generation():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/chat"
        body = json.loads(request.content)
        assert body["format"] == "json"
        return httpx.Response(
            200,
            json={"message": {"content": json.dumps({"summary": "Architecture verified", "score": 92})}},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(base_url="http://mock-ollama:11434", client=client)
    res: SampleOutput = await provider.structured_output("Test prompt", SampleOutput)
    assert isinstance(res, SampleOutput)
    assert res.summary == "Architecture verified"
    assert res.score == 92


# 3. Ollama unavailable
@pytest.mark.anyio
async def test_ollama_unavailable():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Failed to establish a new connection: [Errno 111] Connection refused")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(base_url="http://mock-ollama:11434", client=client, max_retries=1)
    with pytest.raises(ProviderUnavailableError, match="Ollama server is unavailable"):
        await provider.complete("Test prompt")


# 4. Connection refused on structured output
@pytest.mark.anyio
async def test_connection_refused():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(base_url="http://mock-ollama:11434", client=client, max_retries=0)
    with pytest.raises(ProviderUnavailableError):
        await provider.structured_output("Test", SampleOutput)


# 5. Timeout handling
@pytest.mark.anyio
async def test_timeout():
    async def slow_handler(request: httpx.Request) -> httpx.Response:
        await asyncio.sleep(0.5)
        return httpx.Response(200, json={"message": {"content": "Too late"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(slow_handler))
    # Configure tiny timeout (0.05s) to trigger timeout
    provider = OllamaProvider(base_url="http://mock-ollama:11434", timeout=0.05, client=client)
    with pytest.raises(InferenceTimeoutError, match="timed out"):
        await provider.complete("Test")


# 6. Model not found (HTTP 404)
@pytest.mark.anyio
async def test_model_not_found():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'non-existent:7b' not found"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(
        base_url="http://mock-ollama:11434",
        model="non-existent:7b",
        client=client,
    )
    with pytest.raises(ModelNotFoundError, match="is not installed in Ollama"):
        await provider.complete("Test")


# 7. HTTP error (HTTP 400 Bad Request)
@pytest.mark.anyio
async def test_http_error():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="Bad Request: invalid parameter")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(base_url="http://mock-ollama:11434", client=client)
    with pytest.raises(LLMProviderError, match="Ollama client error 400"):
        await provider.complete("Test")


# 8. Malformed JSON handling
@pytest.mark.anyio
async def test_malformed_json():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "This is plain text, not JSON at all."}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(base_url="http://mock-ollama:11434", client=client, max_retries=1)
    with pytest.raises(StructuredOutputError, match="Failed to obtain valid structured output"):
        await provider.structured_output("Test", SampleOutput)


# 9. Invalid Pydantic schema (missing required fields or invalid types)
@pytest.mark.anyio
async def test_invalid_pydantic_schema():
    def handler(request: httpx.Request) -> httpx.Response:
        # Score exceeds Field(le=100) constraint
        return httpx.Response(200, json={"message": {"content": json.dumps({"summary": "Bad", "score": 9999})}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(base_url="http://mock-ollama:11434", client=client, max_retries=1)
    with pytest.raises(StructuredOutputError):
        await provider.structured_output("Test", SampleOutput)


# 10. Retry on transient failure (succeeds after transient 500 error)
@pytest.mark.anyio
async def test_retry_on_transient_failure():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(500, text="Temporary GPU internal error")
        return httpx.Response(200, json={"message": {"content": "Recovered successfully"}})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(base_url="http://mock-ollama:11434", client=client, max_retries=2)
    res = await provider.complete("Test")
    assert res == "Recovered successfully"
    assert calls == 2


# 11. No retry on permanent failure (404 Model Not Found called only once)
@pytest.mark.anyio
async def test_no_retry_on_permanent_failure():
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(404, json={"error": "model missing"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(base_url="http://mock-ollama:11434", client=client, max_retries=3)
    with pytest.raises(ModelNotFoundError):
        await provider.complete("Test")
    assert calls == 1  # Did NOT retry!


# 12. Queue concurrency limit
@pytest.mark.anyio
async def test_queue_concurrency_limit():
    queue = OllamaInferenceQueue(max_concurrent=1, timeout=5.0)
    concurrency_history = []
    current_concurrent = 0

    async def task(idx: int):
        nonlocal current_concurrent
        async def _job():
            nonlocal current_concurrent
            current_concurrent += 1
            concurrency_history.append(current_concurrent)
            await asyncio.sleep(0.04)
            current_concurrent -= 1
            return idx

        return await queue.execute(_job)

    results = await asyncio.gather(task(1), task(2), task(3))
    assert set(results) == {1, 2, 3}
    # Max concurrency never exceeded 1
    assert max(concurrency_history) == 1


# 13. Semaphore released after failure
@pytest.mark.anyio
async def test_semaphore_released_after_failure():
    queue = OllamaInferenceQueue(max_concurrent=1, timeout=5.0)

    async def failing_job():
        raise ValueError("Simulated job failure")

    with pytest.raises(ValueError, match="Simulated job failure"):
        await queue.execute(failing_job)

    assert queue.active_count == 0
    assert queue.queued_count == 0

    # Next job must acquire cleanly without being blocked
    async def next_job():
        return "Clean execution"

    result = await queue.execute(next_job)
    assert result == "Clean execution"


# 14. Timeout releases queue slot
@pytest.mark.anyio
async def test_timeout_releases_queue_slot():
    queue = OllamaInferenceQueue(max_concurrent=1, timeout=0.05)

    async def slow_job():
        await asyncio.sleep(0.5)

    with pytest.raises(InferenceTimeoutError):
        await queue.execute(slow_job)

    assert queue.active_count == 0

    # Subsequent task runs without hang
    async def quick_job():
        return 42

    res = await queue.execute(quick_job)
    assert res == 42


# 15. Health check: Ollama available vs unavailable
@pytest.mark.anyio
async def test_health_check_available_and_unavailable():
    # 15a. Available
    def ok_handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/tags"
        return httpx.Response(200, json={"models": [{"name": "qwen2.5-coder:7b"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(ok_handler))
    provider = OllamaProvider(base_url="http://mock-ollama:11434", model="qwen2.5-coder:7b", client=client)
    health = await provider.health_check()
    assert health["status"] == OllamaHealthStatus.MODEL_AVAILABLE
    assert health["healthy"] is True
    assert health["model_installed"] is True

    # 15b. Unavailable
    def down_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    down_client = httpx.AsyncClient(transport=httpx.MockTransport(down_handler))
    down_provider = OllamaProvider(base_url="http://mock-ollama:11434", client=down_client)
    down_health = await down_provider.health_check()
    assert down_health["status"] == OllamaHealthStatus.OLLAMA_UNAVAILABLE
    assert down_health["healthy"] is False


# 16. Model availability detection (Ollama running, but model not pulled)
@pytest.mark.anyio
async def test_model_availability_detection():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"models": [{"name": "llama3:8b"}, {"name": "mistral:7b"}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = OllamaProvider(
        base_url="http://mock-ollama:11434",
        model="qwen2.5-coder:7b",  # Configured, but not in installed models!
        client=client,
    )

    health = await provider.health_check()
    assert health["status"] == OllamaHealthStatus.MODEL_NOT_FOUND
    assert health["healthy"] is False
    assert health["model_installed"] is False
    assert "llama3:8b" in health["available_models"]
