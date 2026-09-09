"""
LLM Provider abstraction.

Defines a uniform interface for language model providers.
Includes a robust MockLLMProvider for deterministic, zero-cost offline testing
and an OpenAICompatibleProvider for live API execution.
"""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar

from pydantic import BaseModel, ValidationError

logger = logging.getLogger("ai_code_reviewer.llm")

T = TypeVar("T", bound=BaseModel)


def extract_json_from_text(text: str) -> str:
    """Extract raw JSON substring from potentially markdown-wrapped model output."""
    text = text.strip()
    # Match ```json ... ``` blocks
    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if code_block:
        return code_block.group(1).strip()
    # Or find first '{' and last '}'
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace : last_brace + 1].strip()
    return text


class LLMProvider(ABC):
    """Abstract interface for LLM operations."""

    @abstractmethod
    async def complete(self, prompt: str, system: Optional[str] = None) -> str:
        """Generate raw completion text."""
        pass

    @abstractmethod
    async def structured_output(
        self, prompt: str, schema_class: Type[T], system: Optional[str] = None
    ) -> T:
        """Generate and validate a structured response against a Pydantic schema."""
        pass


class MockLLMProvider(LLMProvider):
    """
    Deterministic mock provider for unit/integration testing and offline operation.
    Synthesizes realistic outputs anchored to the provided context.
    """

    def __init__(self, override_responses: Optional[Dict[str, Any]] = None) -> None:
        self.override_responses = override_responses or {}
        self.call_history: List[Dict[str, Any]] = []

    async def complete(self, prompt: str, system: Optional[str] = None) -> str:
        self.call_history.append({"prompt": prompt, "system": system})
        return "Mock completion response."

    async def structured_output(
        self, prompt: str, schema_class: Type[T], system: Optional[str] = None
    ) -> T:
        self.call_history.append({"prompt": prompt, "system": system, "schema": schema_class.__name__})

        # Check for explicitly configured mock override
        if schema_class.__name__ in self.override_responses:
            override_val = self.override_responses[schema_class.__name__]
            if isinstance(override_val, schema_class):
                return override_val
            return schema_class.model_validate(override_val)

        # Generate realistic schema-compliant responses based on prompt inspection
        schema_name = schema_class.__name__.lower()

        if "understanding" in schema_name:
            # Code understanding output
            frameworks = ["FastAPI", "Next.js", "React"] if "react" in prompt.lower() else ["Python", "FastAPI"]
            entry_points = ["app/main.py"] if "main.py" in prompt else ["src/index.ts"]
            data = {
                "architecture_summary": "Modular web service with layered API, service, and data persistence boundaries.",
                "frameworks": frameworks,
                "important_modules": ["api", "core", "models", "services"],
                "entry_points": entry_points,
                "architecture_risks": ["Potential tight coupling between controllers and direct data queries"],
                "observations": ["Well-structured configuration and typed data contracts"],
            }
            return schema_class.model_validate(data)

        elif "review" in schema_name:
            # Code review output
            findings = []
            # Check if there are lines in the prompt we can reference
            line_match = re.search(r"File:\s*([^\s\n]+)", prompt)
            file_path = line_match.group(1) if line_match else "src/service.py"

            if "def " in prompt or "function" in prompt or "class" in prompt:
                findings.append({
                    "category": "maintainability",
                    "type": "complexity",
                    "severity": "medium",
                    "title": "High Cognitive Complexity in Function Logic",
                    "description": "Function contains multiple nested conditional branches that should be decomposed.",
                    "file_path": file_path,
                    "start_line": 15,
                    "end_line": 35,
                    "confidence": 0.88,
                    "evidence": "def process_request(data):\n    if condition:\n        ...",
                })
            return schema_class.model_validate({"findings": findings})

        elif "security" in schema_name:
            # Security agent output
            findings = []
            if "sql" in prompt.lower() or "cwe-89" in prompt.lower():
                findings.append({
                    "category": "security",
                    "type": "sql_injection",
                    "severity": "high",
                    "title": "Verified SQL Injection in Query Construction",
                    "description": "User input is directly concatenated into SQL query string executed against the database.",
                    "file_path": "src/api/users.py",
                    "start_line": 25,
                    "end_line": 28,
                    "confidence": 0.95,
                    "evidence": 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
                    "cwe": "CWE-89",
                })
            return schema_class.model_validate({"findings": findings})

        elif "remediation" in schema_name:
            # Remediation agent output
            file_path = "src/api/users.py"
            # Extract file path from prompt if available
            path_match = re.search(r"File(?:\s*path)?:\s*([^\n\r]+)", prompt, re.IGNORECASE)
            if path_match:
                candidate = path_match.group(1).strip()
                if candidate and not candidate.startswith("None"):
                    file_path = candidate

            prompt_lower = prompt.lower()
            if "xss" in prompt_lower or "cwe-79" in prompt_lower:
                return schema_class.model_validate({
                    "strategy": "Sanitize and safely encode untrusted input prior to rendering.",
                    "explanation": "Replaces dangerous innerHTML/raw rendering with framework-safe text rendering.",
                    "files_changed": [file_path],
                    "changes": [{
                        "file_path": file_path,
                        "start_line": 10,
                        "end_line": 12,
                        "original_code": 'element.innerHTML = userInput;',
                        "replacement_code": 'element.textContent = userInput;',
                    }],
                    "confidence": 0.95,
                })
            elif "secret" in prompt_lower or "cwe-798" in prompt_lower:
                return schema_class.model_validate({
                    "strategy": "Replace hardcoded secret with environment variable lookup.",
                    "explanation": "Loads the credential securely from environment configuration at runtime, removing raw secrets from source.",
                    "files_changed": [file_path],
                    "changes": [{
                        "file_path": file_path,
                        "start_line": 5,
                        "end_line": 5,
                        "original_code": 'API_KEY = "AKIA1234567890ABCDEF"',
                        "replacement_code": 'import os\nAPI_KEY = os.environ.get("API_KEY")',
                    }],
                    "confidence": 0.96,
                })
            elif "command" in prompt_lower or "cwe-78" in prompt_lower:
                return schema_class.model_validate({
                    "strategy": "Avoid shell interpretation and use argument lists with shell=False.",
                    "explanation": "Separates executable binary from parameters, preventing shell metacharacter injection.",
                    "files_changed": [file_path],
                    "changes": [{
                        "file_path": file_path,
                        "start_line": 15,
                        "end_line": 15,
                        "original_code": 'os.system(f"ping {host}")',
                        "replacement_code": 'import subprocess\nsubprocess.run(["ping", "-c", "1", host], check=True)',
                    }],
                    "confidence": 0.94,
                })
            else:
                # Default: SQL Injection or general parameterized query
                return schema_class.model_validate({
                    "strategy": "Use parameterized queries with database query parameters.",
                    "explanation": "Replaces string interpolation with parameterized SQL query arguments, ensuring input is treated purely as data.",
                    "files_changed": [file_path],
                    "changes": [{
                        "file_path": file_path,
                        "start_line": 25,
                        "end_line": 28,
                        "original_code": 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
                        "replacement_code": 'cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))',
                    }],
                    "confidence": 0.95,
                })

        elif "verification" in schema_name:
            # Verification agent output
            prompt_lower = prompt.lower()
            if "simulate_still_vulnerable" in prompt_lower or "simulate_unfixed" in prompt_lower:
                return schema_class.model_validate({
                    "status": "still_vulnerable",
                    "confidence": 0.92,
                    "reason": "The modified code still includes dynamic string construction without full parameter binding.",
                    "remaining_risk": "Attackers can still manipulate query structure via unsanitized input.",
                    "new_findings": [],
                    "evidence": ["Unescaped string interpolation remains reachable."],
                })
            elif "syntax_error" in prompt_lower or "broken" in prompt_lower:
                return schema_class.model_validate({
                    "status": "verification_failed",
                    "confidence": 0.95,
                    "reason": "The applied patch introduces a syntax error or missing variable definition.",
                    "remaining_risk": "Code fails to parse or execute.",
                    "new_findings": [{
                        "category": "quality",
                        "severity": "high",
                        "title": "Syntax error introduced by patch",
                    }],
                    "evidence": ["Invalid syntax in patch lines"],
                })
            else:
                return schema_class.model_validate({
                    "status": "resolved",
                    "confidence": 0.96,
                    "reason": "The dynamic vulnerability construct has been replaced with safe parameterization. Static re-analysis confirms zero matching vulnerability signals and no regressions.",
                    "remaining_risk": None,
                    "new_findings": [],
                    "evidence": ["Verified secure parameter binding in modified code."],
                })

        # Generic default
        return schema_class.model_validate({})


class OpenAICompatibleProvider(LLMProvider):
    """Provider connecting to standard OpenAI-compatible API endpoints via httpx."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 60.0,
        max_retries: int = 2,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries

    async def complete(self, prompt: str, system: Optional[str] = None) -> str:
        import httpx

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def structured_output(
        self, prompt: str, schema_class: Type[T], system: Optional[str] = None
    ) -> T:
        import httpx

        json_schema = schema_class.model_json_schema()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    content = resp.json()["choices"][0]["message"]["content"]
                    clean_json = extract_json_from_text(content)
                    return schema_class.model_validate_json(clean_json)
            except (httpx.HTTPError, json.JSONDecodeError, ValidationError) as exc:
                last_error = exc
                logger.warning(f"LLM structured_output attempt {attempt + 1} failed: {exc}")

        raise RuntimeError(f"Failed to obtain valid structured output after {self.max_retries} retries: {last_error}")
