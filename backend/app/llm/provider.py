"""
LLM Provider abstraction.

Defines a uniform interface for language model providers.
Includes a robust MockLLMProvider for deterministic, zero-cost offline testing
and an OpenAICompatibleProvider for live API execution.
"""
import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger("ai_code_reviewer.llm")

T = TypeVar("T", bound=BaseModel)


class LLMProviderError(Exception):
    """Base exception for all LLM provider errors."""
    pass


class ProviderUnavailableError(LLMProviderError):
    """Raised when the LLM server is offline or unreachable."""
    pass


class ModelNotFoundError(LLMProviderError):
    """Raised when the configured model is not installed."""
    pass


class StructuredOutputError(LLMProviderError):
    """Raised when the model response fails schema validation or JSON parsing."""
    pass


class ModelRefusalError(StructuredOutputError):
    """Raised when the model returns a natural-language apology, safety refusal, or refusal JSON."""

    def __init__(self, message: str, raw_response: Optional[str] = None) -> None:
        super().__init__(message)
        self.raw_response = raw_response


REFUSAL_PHRASES = [
    "i cannot assist",
    "i can't assist",
    "i cannot fulfill",
    "i can't fulfill",
    "i am unable to",
    "i'm unable to",
    "as an ai",
    "as a language model",
    "i apologize",
    "i'm sorry",
    "i am sorry",
    "safety policy",
    "safety guidelines",
    "against my safety",
    "violates our policy",
    "offensive or harmful",
    "cannot analyze this repository",
    "cannot review this code",
    "cannot execute this request",
]


def is_model_refusal(text: str) -> bool:
    """Detect whether a model response is an apology or refusal."""
    if not text:
        return False
    lower = text.strip().lower()
    for phrase in REFUSAL_PHRASES:
        if phrase in lower:
            return True
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            for key in ("error", "message", "detail", "apology", "refusal", "reason"):
                val = str(parsed.get(key, "")).lower()
                for phrase in REFUSAL_PHRASES:
                    if phrase in val:
                        return True
    except Exception:
        pass
    return False


class InferenceTimeoutError(LLMProviderError):
    """Raised when inference exceeds the timeout."""
    pass


class OllamaHealthStatus:
    """Standard health check status identifiers."""
    OLLAMA_AVAILABLE = "OLLAMA_AVAILABLE"
    OLLAMA_UNAVAILABLE = "OLLAMA_UNAVAILABLE"
    MODEL_AVAILABLE = "MODEL_AVAILABLE"
    MODEL_NOT_FOUND = "MODEL_NOT_FOUND"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


def extract_json_from_text(text: str) -> str:
    """Extract raw JSON substring from potentially markdown-wrapped or reasoning-tagged model output."""
    text = text.strip()
    # Strip <think>...</think> reasoning tags if present
    text = re.sub(r"<think>[\s\S]*?</think>", "", text).strip()
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
    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate raw completion text."""
        pass

    @abstractmethod
    async def structured_output(
        self,
        prompt: str,
        schema_class: Type[T],
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> T:
        """Generate and validate a structured response against a Pydantic schema."""
        pass

    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """Perform a provider connectivity check."""
        pass

    @abstractmethod
    async def model_info(self) -> Dict[str, Any]:
        """Return metadata regarding the active model."""
        pass


class MockLLMProvider(LLMProvider):
    """
    Deterministic mock provider for unit/integration testing and offline operation.
    Synthesizes realistic outputs anchored to the provided context.
    """

    def __init__(self, override_responses: Optional[Dict[str, Any]] = None) -> None:
        self.override_responses = override_responses or {}
        self.call_history: List[Dict[str, Any]] = []

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        self.call_history.append({"prompt": prompt, "system": system, "options": options})
        return "Mock completion response."

    async def structured_output(
        self,
        prompt: str,
        schema_class: Type[T],
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> T:
        self.call_history.append({"prompt": prompt, "system": system, "schema": schema_class.__name__, "options": options})

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
            frameworks = ["FastAPI", "Next.js", "React"] if "react" in prompt.lower() else ["FastAPI"]
            found_files = [
                m for m in re.findall(r'(?:path=["\']|`|\b)([a-zA-Z0-9_\-./]+\.(?:py|ts|tsx|js|jsx|json|go|java|rs|html))\b', prompt)
                if not m.startswith("http") and ("/" in m or "." in m)
            ]
            default_ep = "app/main.py" if "main.py" in prompt else (found_files[0] if found_files else "src/index.ts")
            entry_points = [default_ep]
            default_mod_dir = "/".join(default_ep.split("/")[:-1]) if "/" in default_ep else "api"
            data = {
                "architecture_summary": "Modular web service with layered API, service, and data persistence boundaries.",
                "languages": ["Python", "TypeScript"] if "react" in prompt.lower() else ["Python"],
                "frameworks": frameworks,
                "entry_points": entry_points,
                "modules": [
                    {
                        "name": "api",
                        "path": "app/api" if "app/api" in prompt else default_mod_dir,
                        "responsibility": "API endpoint routers and HTTP handling",
                        "key_symbols": ["router"],
                        "evidence": default_ep,
                        "confidence": 0.90,
                    },
                    {
                        "name": "services",
                        "path": "src/service.py" if "src/service.py" in prompt else default_mod_dir,
                        "responsibility": "Business logic and domain operations",
                        "key_symbols": ["process_data"],
                        "evidence": default_ep,
                        "confidence": 0.85,
                    },
                ],
                "important_modules": [default_mod_dir],
                "important_files": entry_points,
                "dependencies": ["fastapi", "pydantic", "sqlalchemy"],
                "external_integrations": ["PostgreSQL", "GitHub API"],
                "security_boundaries": ["app/api/auth", "JWT Bearer Token Validation"],
                "data_flows": ["Client -> FastAPI Router -> Domain Service -> Database Layer"],
                "confidence": 0.90,
                "architecture_risks": ["Potential tight coupling between controllers and direct data queries"],
                "observations": ["Well-structured configuration and typed data contracts"],
            }
            return schema_class.model_validate(data)


        elif "review" in schema_name or "quality" in schema_name:
            # Code review and Code Quality output
            findings = []
            line_match = re.search(r"File:\s*([^\s\n()]+)", prompt)
            file_path = line_match.group(1) if line_match else "src/service.py"
            lines_match = re.search(r"Lines\s*(\d+)-(\d+)", prompt)
            start_l = int(lines_match.group(1)) if lines_match else 2
            end_l = int(lines_match.group(2)) if lines_match else (start_l + 3)

            if "def " in prompt or "function" in prompt or "class" in prompt or "code" in prompt.lower():
                findings.append({
                    "finding_id": "qual-mock-1",
                    "category": "maintainability",
                    "type": "complexity",
                    "severity": "medium",
                    "title": "High Cognitive Complexity in Function Logic",
                    "description": "Function contains multiple nested conditional branches that should be decomposed.",
                    "file_path": file_path,
                    "start_line": start_l,
                    "end_line": end_l,
                    "confidence": 0.88,
                    "evidence": "def process_request(data):\n    if condition:\n        ...",
                    "why_problematic": "Excessive nesting increases bug density and maintenance difficulty.",
                    "recommended_improvement": "Extract conditional logic into dedicated helper functions.",
                    "detection_provenance": "hybrid",
                })
            return schema_class.model_validate({"findings": findings})

        elif "security" in schema_name:
            # Security agent output
            findings = []
            file_match = re.search(r"File:\s*([^\s\n()]+)", prompt)
            file_path = file_match.group(1) if file_match else "src/api/users.py"
            lines_match = re.search(r"Lines\s*(\d+)-(\d+)", prompt)
            start_l = int(lines_match.group(1)) if lines_match else 2
            end_l = int(lines_match.group(2)) if lines_match else (start_l + 3)

            if "sql" in prompt.lower() or "cwe-89" in prompt.lower():
                findings.append({
                    "finding_id": "sec-mock-1",
                    "category": "security",
                    "type": "sql_injection",
                    "severity": "high",
                    "title": "Verified SQL Injection in Query Construction",
                    "description": "User input is directly concatenated into SQL query string executed against the database.",
                    "file_path": file_path,
                    "start_line": start_l,
                    "end_line": end_l,
                    "confidence": 0.95,
                    "evidence": 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")',
                    "cwe": "CWE-89",
                    "source_input": "user_id from query params",
                    "transformation": "Direct f-string string interpolation",
                    "sink": "cursor.execute()",
                    "exploitability_explanation": "Untrusted user_id enters query unmodified, allowing arbitrary SQL execution.",
                    "impact": "Full database read/write compromise.",
                    "recommended_mitigation": "Use parameterized query placeholders (%s or :user_id).",
                    "detection_provenance": "hybrid",
                })
            return schema_class.model_validate({"findings": findings})

        elif "correlation" in schema_name:
            # Semantic finding correlation output
            finding_ids = re.findall(r'\[([a-zA-Z0-9_\-]+)\]', prompt) or re.findall(r'"id":\s*"([a-zA-Z0-9_\-]+)"', prompt)
            relationships = []
            if len(finding_ids) >= 2:
                prompt_lower = prompt.lower()
                is_related = (
                    ("validation" in prompt_lower and "sql" in prompt_lower) or
                    ("path" in prompt_lower and "traversal" in prompt_lower) or
                    ("error" in prompt_lower and "leak" in prompt_lower) or
                    ("insecure helper" in prompt_lower or "shared helper" in prompt_lower) or
                    ("same function" in prompt_lower)
                )
                if is_related:
                    rel_type = "shared_root_cause" if ("validation" in prompt_lower and "sql" in prompt_lower) else "overlapping"
                    relationships.append({
                        "finding_id_1": finding_ids[0],
                        "finding_id_2": finding_ids[1],
                        "relationship_type": rel_type,
                        "shared_root_cause": "Unsanitized user input parameter reaching multiple execution layers",
                        "rationale": "Findings in the same function affect the same data flow parameter without validation.",
                        "confidence": 0.90,
                    })
            return schema_class.model_validate({"relationships": relationships})

        elif "remediation" in schema_name:
            # Remediation agent output
            file_path = "src/api/users.py"
            # Extract file path from prompt if available
            path_match = re.search(r"File(?:\s*path)?:\s*([^\n\r]+)", prompt, re.IGNORECASE)
            if path_match:
                candidate = path_match.group(1).strip()
                if candidate and not candidate.startswith("None"):
                    file_path = candidate

            # Extract finding details specifically to avoid false matches on guidelines
            details_section = prompt
            if "FINDING DETAILS:" in prompt:
                end_idx = prompt.find("REMEDIATION STRATEGY REQUIREMENTS:")
                if end_idx != -1:
                    details_section = prompt[prompt.find("FINDING DETAILS:"):end_idx]
                else:
                    details_section = prompt[prompt.find("FINDING DETAILS:"):]

            prompt_lower = details_section.lower()
            if "xss" in prompt_lower or "cwe-79" in prompt_lower or "cross-site" in prompt_lower:
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
            elif "secret" in prompt_lower or "cwe-798" in prompt_lower or "credential" in prompt_lower or "api_key" in prompt_lower:
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
            if "simulate_regression" in prompt_lower or "simulate_syntax_error" in prompt_lower:
                return schema_class.model_validate({
                    "outcome": "REGRESSION_DETECTED",
                    "status": "verification_failed",
                    "confidence": 0.95,
                    "reason": "The applied patch introduces a syntax error, broken interface, or new defect.",
                    "source_transformation_sink": {
                        "source_input": "Untrusted input",
                        "transformation": "Flawed substitution",
                        "sink": "Runtime execution",
                        "is_exploitable_path_severed": False,
                        "remaining_attack_surface": "Code fails at runtime or introduces secondary vulnerability.",
                        "rationale": "Patch introduces regression.",
                    },
                    "remaining_risk": "Code fails to parse or execute.",
                    "new_findings": [{
                        "category": "quality",
                        "severity": "high",
                        "title": "Syntax error introduced by patch",
                    }],
                    "evidence": ["Invalid syntax in patch lines"],
                })
            elif "simulate_partially_fixed" in prompt_lower:
                return schema_class.model_validate({
                    "outcome": "PARTIALLY_FIXED",
                    "status": "partially_resolved",
                    "confidence": 0.88,
                    "reason": "The patch addresses the primary call site but leaves secondary unparameterized branches reachable.",
                    "source_transformation_sink": {
                        "source_input": "user parameter",
                        "transformation": "Partial query parameterization",
                        "sink": "Secondary database query",
                        "is_exploitable_path_severed": False,
                        "remaining_attack_surface": "Secondary query execution path remains vulnerable.",
                        "rationale": "Primary vector mitigated but alternative path remains reachable.",
                    },
                    "remaining_risk": "Alternative execution path allows injection under specific conditions.",
                    "new_findings": [],
                    "evidence": ["Secondary query branch retains string formatting."],
                })
            elif "simulate_still_vulnerable" in prompt_lower or "simulate_unfixed" in prompt_lower or "simulate_not_fixed" in prompt_lower:
                return schema_class.model_validate({
                    "outcome": "NOT_FIXED",
                    "status": "still_vulnerable",
                    "confidence": 0.92,
                    "reason": "The modified code still includes dynamic string construction without full parameter binding.",
                    "source_transformation_sink": {
                        "source_input": "user input",
                        "transformation": "Superficial string quoting",
                        "sink": "Database execution",
                        "is_exploitable_path_severed": False,
                        "remaining_attack_surface": "Quotes can still be escaped or bypassed.",
                        "rationale": "Untrusted input still alters query structure.",
                    },
                    "remaining_risk": "Attackers can still manipulate query structure via unsanitized input.",
                    "new_findings": [],
                    "evidence": ["Unescaped string interpolation remains reachable."],
                })
            elif "simulate_unable_to_verify" in prompt_lower:
                return schema_class.model_validate({
                    "outcome": "UNABLE_TO_VERIFY",
                    "status": "verification_failed",
                    "confidence": 0.50,
                    "reason": "Available code snippets and test fixtures are insufficient to establish whether vulnerability is eradicated.",
                    "source_transformation_sink": None,
                    "remaining_risk": "Uncertainty cannot be accepted as resolution.",
                    "new_findings": [],
                    "evidence": [],
                })
            else:
                return schema_class.model_validate({
                    "outcome": "FIXED",
                    "status": "resolved",
                    "confidence": 0.96,
                    "reason": "The dynamic vulnerability construct has been replaced with safe parameterization. Static re-analysis confirms zero matching vulnerability signals and no regressions.",
                    "source_transformation_sink": {
                        "source_input": "User input from HTTP request parameter",
                        "transformation": "Database driver parameter binding (%s)",
                        "sink": "cursor.execute()",
                        "is_exploitable_path_severed": True,
                        "remaining_attack_surface": None,
                        "rationale": "Direct string interpolation was completely replaced with driver-level parameterized query binding.",
                    },
                    "remaining_risk": None,
                    "new_findings": [],
                    "evidence": ["Verified secure parameter binding in modified code."],
                })

        # Generic default
        return schema_class.model_validate({})

    async def health_check(self) -> Dict[str, Any]:
        return {
            "healthy": True,
            "provider": "mock",
            "model": "mock-model",
            "model_installed": True,
            "available_models": ["mock-model"],
        }

    async def model_info(self) -> Dict[str, Any]:
        return {"model": "mock-model", "parameter_size": "7B", "family": "mock"}


class OllamaInferenceQueue:
    """
    Asynchronous queue with bounded concurrency for local Ollama execution.
    Protects local GPU VRAM / CPU from thrashing and manages inference load.
    """

    def __init__(self, max_concurrent: int = 1, timeout: float = 120.0) -> None:
        self._max_concurrent = max(1, max_concurrent)
        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._timeout = timeout
        self._active_count = 0
        self._queued_count = 0

    @property
    def max_concurrent(self) -> int:
        return self._max_concurrent

    @property
    def active_count(self) -> int:
        return self._active_count

    @property
    def queued_count(self) -> int:
        return self._queued_count

    async def execute(self, func, *args, **kwargs):
        self._queued_count += 1
        acquired = False
        try:
            async with self._semaphore:
                acquired = True
                self._queued_count -= 1
                self._active_count += 1
                try:
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=self._timeout)
                except asyncio.TimeoutError as te:
                    raise InferenceTimeoutError(f"Ollama inference timed out after {self._timeout}s") from te
                finally:
                    self._active_count -= 1
        finally:
            if not acquired:
                self._queued_count -= 1


class OllamaProvider(LLMProvider):
    """
    Ollama Local LLM Provider.
    Implements structured JSON validation, hardware-aware concurrency queuing,
    connection retries, health checking, and model discovery.
    """

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "qwen2.5-coder:7b",
        timeout: float = 120.0,
        max_concurrent: int = 1,
        context_size: int = 8192,
        temperature: float = 0.1,
        keep_alive: str = "15m",
        max_retries: int = 2,
        client: Optional[httpx.AsyncClient] = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.context_size = context_size
        self.temperature = temperature
        self.keep_alive = keep_alive
        self.max_retries = max_retries
        self._external_client = client
        self.queue = OllamaInferenceQueue(max_concurrent=max_concurrent, timeout=timeout)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._external_client:
            return self._external_client
        return httpx.AsyncClient(timeout=self.timeout)

    async def complete(
        self,
        prompt: str,
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> str:
        async def _do_call():
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            payload: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "keep_alive": self.keep_alive,
                "options": {
                    "temperature": self.temperature,
                    "num_ctx": self.context_size,
                    **(options or {}),
                },
            }

            url = f"{self.base_url}/api/chat"
            client = await self._get_client()
            last_error = None
            try:
                for attempt in range(self.max_retries + 1):
                    try:
                        resp = await client.post(url, json=payload)
                        if resp.status_code == 404:
                            raise ModelNotFoundError(f"Configured model '{self.model}' is not installed in Ollama.")
                        if 400 <= resp.status_code < 500:
                            raise LLMProviderError(f"Ollama client error {resp.status_code}: {resp.text}")
                        resp.raise_for_status()
                        data = resp.json()
                        msg = data.get("message", {}).get("content", "")
                        return re.sub(r"<think>[\s\S]*?</think>", "", msg).strip()
                    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                        raise ProviderUnavailableError(f"Ollama server is unavailable at {self.base_url}: {exc}") from exc
                    except (ModelNotFoundError, LLMProviderError):
                        raise
                    except Exception as exc:
                        last_error = exc
                        logger.warning("Ollama complete attempt %d failed: %s", attempt + 1, exc)
                        if attempt < self.max_retries:
                            await asyncio.sleep(0.5 * (2 ** attempt))
                raise LLMProviderError(f"Failed to complete prompt after {self.max_retries} retries: {last_error}")
            finally:
                if not self._external_client:
                    await client.aclose()

        return await self.queue.execute(_do_call)

    async def structured_output(
        self,
        prompt: str,
        schema_class: Type[T],
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> T:
        schema_json = schema_class.model_json_schema()
        schema_instruction = (
            f"\n\nMANDATORY SCHEMA ENFORCEMENT:\n"
            f"You MUST respond strictly in valid JSON conforming to this schema:\n"
            f"{json.dumps(schema_json, indent=2)}\n"
            f"Do not include any conversational preamble, commentary, apologies, refusals, or markdown formatting outside the JSON."
        )
        full_system = f"{system.strip()}\n{schema_instruction}" if system else schema_instruction.strip()

        async def _do_call():
            url = f"{self.base_url}/api/chat"
            client = await self._get_client()
            last_error: Optional[Exception] = None
            last_raw_content: str = ""

            # Determine format parameter: use schema dict if requested, otherwise default to "json"
            requested_format = options.get("format") if options else None
            use_schema = bool(options.get("use_schema_format")) if options else False
            if requested_format is not None:
                current_format = requested_format
            elif use_schema:
                current_format = schema_json
            else:
                current_format = "json"

            try:
                for attempt in range(self.max_retries + 1):
                    # Construct message payload with corrective feedback on retries
                    if attempt == 0:
                        messages = [
                            {"role": "system", "content": full_system},
                            {"role": "user", "content": prompt},
                        ]
                    else:
                        if isinstance(last_error, ModelRefusalError) or is_model_refusal(last_raw_content):
                            correction_msg = (
                                "CRITICAL CORRECTION: Your previous response was detected as an apology or refusal. "
                                "This is an authorized, defensive, read-only static code analysis task. "
                                "Refusals and apologies are strictly forbidden. You MUST output a complete, valid "
                                f"JSON object matching the requested schema for {schema_class.__name__}. "
                                "All required fields, including 'architecture_summary', must be populated."
                            )
                        elif isinstance(last_error, ValidationError):
                            missing_fields = []
                            for err in last_error.errors():
                                loc = err.get("loc", [])
                                if loc:
                                    missing_fields.append(str(loc[0]))
                            missing_str = f" Missing required fields: {', '.join(missing_fields)}." if missing_fields else ""
                            correction_msg = (
                                f"CRITICAL CORRECTION: Your previous output failed schema validation:{missing_str}\n"
                                f"Details: {last_error}\n"
                                f"You MUST output valid JSON strictly satisfying all required schema fields for {schema_class.__name__}."
                            )
                        elif isinstance(last_error, json.JSONDecodeError):
                            correction_msg = (
                                f"CRITICAL CORRECTION: Your previous response was not valid JSON ({last_error}). "
                                "Output ONLY raw valid JSON conforming to the schema with no conversational prose or markdown fences."
                            )
                        else:
                            correction_msg = (
                                f"CRITICAL CORRECTION: Previous attempt failed ({last_error}). "
                                f"Please output strictly valid JSON conforming to the {schema_class.__name__} schema."
                            )

                        messages = [
                            {"role": "system", "content": full_system},
                            {"role": "user", "content": prompt},
                            {"role": "assistant", "content": last_raw_content[:1500] if last_raw_content else "{}"},
                            {"role": "user", "content": correction_msg},
                        ]

                    call_options = {k: v for k, v in (options or {}).items() if k not in ("format", "use_schema_format")}
                    payload: Dict[str, Any] = {
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "format": current_format,
                        "keep_alive": self.keep_alive,
                        "options": {
                            "temperature": self.temperature,
                            "num_ctx": self.context_size,
                            **call_options,
                        },
                    }

                    try:
                        resp = await client.post(url, json=payload)
                        if resp.status_code == 404:
                            raise ModelNotFoundError(f"Configured model '{self.model}' is not installed in Ollama.")
                        if resp.status_code == 400 and current_format != "json":
                            # Fallback if older Ollama does not support schema dict in format
                            logger.info("Ollama rejected schema format with 400; falling back to format='json'")
                            current_format = "json"
                            payload["format"] = "json"
                            resp = await client.post(url, json=payload)

                        if 400 <= resp.status_code < 500:
                            raise LLMProviderError(f"Ollama client error {resp.status_code}: {resp.text}")
                        resp.raise_for_status()

                        data = resp.json()
                        raw_content = data.get("message", {}).get("content", "")
                        last_raw_content = raw_content

                        # Check if raw response is refusal / apology
                        if is_model_refusal(raw_content):
                            logger.warning(
                                "Ollama structured_output attempt %d returned a refusal/apology for schema %s",
                                attempt + 1,
                                schema_class.__name__,
                            )
                            raise ModelRefusalError(
                                f"Model returned a refusal or apology instead of structured output for {schema_class.__name__}",
                                raw_response=raw_content,
                            )

                        clean_json = extract_json_from_text(raw_content)

                        # Check if extracted JSON is itself a refusal
                        if is_model_refusal(clean_json):
                            raise ModelRefusalError(
                                f"Model returned a refusal or apology JSON for {schema_class.__name__}",
                                raw_response=clean_json,
                            )

                        return schema_class.model_validate_json(clean_json)

                    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                        raise ProviderUnavailableError(f"Ollama server is unavailable at {self.base_url}: {exc}") from exc
                    except (ModelNotFoundError, ProviderUnavailableError):
                        raise
                    except (httpx.HTTPError, json.JSONDecodeError, ValidationError, ModelRefusalError) as exc:
                        last_error = exc
                        logger.warning(
                            "Ollama structured_output attempt %d failed for schema %s: %s",
                            attempt + 1,
                            schema_class.__name__,
                            type(exc).__name__,
                        )
                        if attempt < self.max_retries:
                            await asyncio.sleep(0.5 * (2 ** attempt))

                if isinstance(last_error, ModelRefusalError):
                    raise ModelRefusalError(
                        f"Failed to obtain valid structured output for {schema_class.__name__} after {self.max_retries} retries: Model refused analysis ({last_error})",
                        raw_response=last_raw_content,
                    )
                raise StructuredOutputError(
                    f"Failed to obtain valid structured output for {schema_class.__name__} after {self.max_retries} retries: {last_error}"
                )
            finally:
                if not self._external_client:
                    await client.aclose()

        return await self.queue.execute(_do_call)

    async def health_check(self) -> Dict[str, Any]:
        """Verify that local Ollama instance is reachable and model is available."""
        url = f"{self.base_url}/api/tags"
        client = await self._get_client()
        try:
            resp = await client.get(url, timeout=5.0)
            if resp.status_code == 200:
                data = resp.json()
                available_models = [m.get("name") for m in data.get("models", [])]
                model_installed = any(
                    self.model == m or self.model.split(":")[0] == m.split(":")[0]
                    for m in available_models
                )
                status = (
                    OllamaHealthStatus.MODEL_AVAILABLE
                    if model_installed
                    else OllamaHealthStatus.MODEL_NOT_FOUND
                )
                return {
                    "status": status,
                    "healthy": model_installed,
                    "provider": "ollama",
                    "base_url": self.base_url,
                    "model": self.model,
                    "model_installed": model_installed,
                    "available_models": available_models,
                }
            return {
                "status": OllamaHealthStatus.UNKNOWN_ERROR,
                "healthy": False,
                "provider": "ollama",
                "base_url": self.base_url,
                "model": self.model,
                "model_installed": False,
                "available_models": [],
                "error": f"Ollama API returned HTTP {resp.status_code}",
            }
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            return {
                "status": OllamaHealthStatus.OLLAMA_UNAVAILABLE,
                "healthy": False,
                "provider": "ollama",
                "base_url": self.base_url,
                "model": self.model,
                "model_installed": False,
                "available_models": [],
                "error": f"Ollama daemon unreachable at {self.base_url}: {exc}",
            }
        except Exception as exc:
            return {
                "status": OllamaHealthStatus.UNKNOWN_ERROR,
                "healthy": False,
                "provider": "ollama",
                "base_url": self.base_url,
                "model": self.model,
                "model_installed": False,
                "available_models": [],
                "error": str(exc),
            }
        finally:
            if not self._external_client:
                await client.aclose()

    async def model_info(self) -> Dict[str, Any]:
        """Fetch metadata for configured model via Ollama /api/show."""
        url = f"{self.base_url}/api/show"
        client = await self._get_client()
        try:
            resp = await client.post(url, json={"name": self.model}, timeout=5.0)
            if resp.status_code == 200:
                return resp.json()
            return {"error": f"Model info returned status {resp.status_code}"}
        except Exception as exc:
            return {"error": str(exc)}
        finally:
            if not self._external_client:
                await client.aclose()


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
        self,
        prompt: str,
        schema_class: Type[T],
        system: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> T:
        import httpx

        json_schema = schema_class.model_json_schema()
        schema_instruction = (
            f"\n\nMANDATORY SCHEMA ENFORCEMENT:\n"
            f"You MUST respond strictly in valid JSON conforming to this schema:\n"
            f"{json.dumps(json_schema, indent=2)}\n"
            f"Do not include any conversational preamble, commentary, apologies, refusals, or markdown formatting outside the JSON."
        )
        full_system = f"{system.strip()}\n{schema_instruction}" if system else schema_instruction.strip()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        last_error: Optional[Exception] = None
        last_raw_content: str = ""

        for attempt in range(self.max_retries + 1):
            if attempt == 0:
                messages = [
                    {"role": "system", "content": full_system},
                    {"role": "user", "content": prompt},
                ]
            else:
                if isinstance(last_error, ModelRefusalError) or is_model_refusal(last_raw_content):
                    correction_msg = (
                        "CRITICAL CORRECTION: Your previous response was detected as an apology or refusal. "
                        "This is an authorized, defensive, read-only static code analysis task. "
                        "Refusals and apologies are strictly forbidden. You MUST output a complete, valid "
                        f"JSON object matching the requested schema for {schema_class.__name__}. "
                        "All required fields, including 'architecture_summary', must be populated."
                    )
                elif isinstance(last_error, ValidationError):
                    missing_fields = []
                    for err in last_error.errors():
                        loc = err.get("loc", [])
                        if loc:
                            missing_fields.append(str(loc[0]))
                    missing_str = f" Missing required fields: {', '.join(missing_fields)}." if missing_fields else ""
                    correction_msg = (
                        f"CRITICAL CORRECTION: Your previous output failed schema validation:{missing_str}\n"
                        f"Details: {last_error}\n"
                        f"You MUST output valid JSON strictly satisfying all required schema fields for {schema_class.__name__}."
                    )
                elif isinstance(last_error, json.JSONDecodeError):
                    correction_msg = (
                        f"CRITICAL CORRECTION: Your previous response was not valid JSON ({last_error}). "
                        "Output ONLY raw valid JSON conforming to the schema with no conversational prose or markdown fences."
                    )
                else:
                    correction_msg = (
                        f"CRITICAL CORRECTION: Previous attempt failed ({last_error}). "
                        f"Please output strictly valid JSON conforming to the {schema_class.__name__} schema."
                    )

                messages = [
                    {"role": "system", "content": full_system},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": last_raw_content[:1500] if last_raw_content else "{}"},
                    {"role": "user", "content": correction_msg},
                ]

            payload = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.1,
                "response_format": {"type": "json_object"},
                **(options or {}),
            }

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers,
                    )
                    resp.raise_for_status()
                    content = resp.json()["choices"][0]["message"]["content"]
                    last_raw_content = content

                    if is_model_refusal(content):
                        raise ModelRefusalError(
                            f"Model returned a refusal or apology instead of structured output for {schema_class.__name__}",
                            raw_response=content,
                        )

                    clean_json = extract_json_from_text(content)
                    if is_model_refusal(clean_json):
                        raise ModelRefusalError(
                            f"Model returned a refusal or apology JSON for {schema_class.__name__}",
                            raw_response=clean_json,
                        )

                    return schema_class.model_validate_json(clean_json)
            except (httpx.HTTPError, json.JSONDecodeError, ValidationError, ModelRefusalError) as exc:
                last_error = exc
                logger.warning(f"OpenAI structured_output attempt {attempt + 1} failed: {exc}")
                if attempt < self.max_retries:
                    await asyncio.sleep(0.5 * (2 ** attempt))

        if isinstance(last_error, ModelRefusalError):
            raise ModelRefusalError(
                f"Failed to obtain valid structured output for {schema_class.__name__} after {self.max_retries} retries: Model refused analysis ({last_error})",
                raw_response=last_raw_content,
            )
        raise StructuredOutputError(
            f"Failed to obtain valid structured output for {schema_class.__name__} after {self.max_retries} retries: {last_error}"
        )
