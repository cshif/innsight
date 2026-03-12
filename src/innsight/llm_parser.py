"""LLM-backed query parser utilities.

This module contains a helper that sends the original user query to a hosted
LLM (e.g., Claude or OpenAI) and normalizes the structured JSON response into
the format expected by ``innsight.parser``.
"""

from __future__ import annotations

import json
import os
from typing import Any, Callable, Dict, List, Optional

import requests

from .exceptions import ParseError
from .logging_config import get_logger

logger = get_logger(__name__)

_ALLOWED_FILTERS = ("parking", "wheelchair", "kids", "pet")


def _env_flag(name: str, default: bool = False) -> bool:
    """Return boolean flag derived from environment variables."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


class LLMQueryParser:
    """Convert natural language queries to structured JSON via LLM."""

    DEFAULT_SYSTEM_PROMPT = (
        "You are InnSight's travel query parser. Parse Chinese travel requests and "
        "respond with valid JSON describing the trip. The JSON must include the "
        "fields: days (1-14 or null), filters (array containing any of: parking, "
        "wheelchair, kids, pet), poi (main attraction or activity), and place "
        "(destination or region). If a value is missing, return null (for days) "
        "or an empty string/list. Do not output natural language explanations."
    )

    def __init__(
        self,
        *,
        enabled: Optional[bool] = None,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
        api_version: Optional[str] = None,
        timeout: Optional[int] = None,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
        auth_header: Optional[str] = None,
        auth_prefix: Optional[str] = None,
        http_client: Optional[Callable[..., Any]] = None,
    ) -> None:
        self.enabled = enabled if enabled is not None else _env_flag("LLM_PARSER_ENABLED", False)
        self.api_key = api_key or os.getenv("LLM_PARSER_API_KEY")
        self.api_url = api_url or os.getenv("LLM_PARSER_API_URL", "https://api.anthropic.com/v1/messages")
        self.model = model or os.getenv("LLM_PARSER_MODEL", "claude-3-5-sonnet-20241022")
        self.api_version = api_version or os.getenv("LLM_PARSER_API_VERSION", "2023-06-01")
        self.timeout = timeout or int(os.getenv("LLM_PARSER_TIMEOUT", "30"))
        self.max_tokens = max_tokens or int(os.getenv("LLM_PARSER_MAX_TOKENS", "512"))
        self.temperature = temperature if temperature is not None else float(os.getenv("LLM_PARSER_TEMPERATURE", "0"))
        self.system_prompt = system_prompt or os.getenv("LLM_PARSER_SYSTEM_PROMPT", self.DEFAULT_SYSTEM_PROMPT)
        self.auth_header = auth_header or os.getenv("LLM_PARSER_AUTH_HEADER", "x-api-key")
        self.auth_prefix = auth_prefix if auth_prefix is not None else os.getenv("LLM_PARSER_AUTH_PREFIX", "")
        self.max_days = int(os.getenv("LLM_PARSER_MAX_DAYS", "14"))
        self._http_client = http_client or requests.post

    @property
    def is_enabled(self) -> bool:
        """Return True when the parser has enough configuration to run."""
        return self.enabled and bool(self.api_key and self.api_url and self.model)

    def parse(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse query with LLM and normalize to parser schema."""
        if not self.is_enabled or not isinstance(text, str) or not text.strip():
            return None

        try:
            response_payload = self._invoke_llm(text)
            response_text = self._extract_text_content(response_payload)
            structured_payload = self._load_json(response_text)
            return self._normalize_payload(structured_payload)
        except requests.RequestException as exc:
            logger.warning(
                "LLM query parsing failed due to network error",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        except (json.JSONDecodeError, ParseError) as exc:
            logger.warning(
                "LLM query parsing failed",
                error_type=type(exc).__name__,
                error_message=str(exc),
            )
        return None

    def _invoke_llm(self, text: str) -> Dict[str, Any]:
        """Send the query to the configured LLM endpoint."""
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": self._build_messages(text),
        }

        response = self._http_client(
            self.api_url,
            json=payload,
            headers=self._build_headers(),
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def _build_messages(self, text: str) -> List[Dict[str, str]]:
        """Build chat messages for Anthropic/OpenAI compatible APIs."""
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self._build_user_prompt(text)},
        ]

    def _build_user_prompt(self, text: str) -> str:
        """Create user prompt instructing the LLM to return JSON only."""
        return (
            "請閱讀以下旅遊需求並輸出 JSON。欄位為:\n"
            "- days: 1~14 的整數或 null\n"
            "- filters: 由 parking/wheelchair/kids/pet 組成的陣列\n"
            "- poi: 主行程或景點名稱 (字串)\n"
            "- place: 地點/城市/區域 (字串)\n"
            "若無資訊請回傳 null、空字串或空陣列。只輸出純 JSON，不要多餘說明。\n\n"
            f"Query: {text.strip()}"
        )

    def _build_headers(self) -> Dict[str, str]:
        """Build HTTP headers with auth metadata."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            value = f"{self.auth_prefix}{self.api_key}" if self.auth_prefix else self.api_key
            headers[self.auth_header] = value
        if self.api_version:
            headers["anthropic-version"] = self.api_version
        return headers

    def _extract_text_content(self, response: Dict[str, Any]) -> str:
        """Extract first textual segment from an Anthropic/OpenAI style response."""
        content = response.get("content")
        if isinstance(content, list):
            texts = [segment.get("text", "") for segment in content if isinstance(segment, dict)]
            merged = "\n".join(text.strip() for text in texts if text)
            if merged:
                return merged
        if isinstance(content, str) and content.strip():
            return content.strip()

        for key in ("output", "result"):
            maybe_text = response.get(key)
            if isinstance(maybe_text, str) and maybe_text.strip():
                return maybe_text.strip()

        raise ParseError("LLM response did not include textual content")

    def _load_json(self, text: str) -> Dict[str, Any]:
        """Load JSON text returned from the LLM response."""
        cleaned = self._strip_code_fence(text)
        payload = json.loads(cleaned)
        if not isinstance(payload, dict):
            raise ParseError("LLM JSON payload must be an object")
        return payload

    def _strip_code_fence(self, text: str) -> str:
        """Remove Markdown code fences from the response text, if present."""
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped[3:]
            if stripped.startswith("json"):
                stripped = stripped[4:]
            if stripped.endswith("```"):
                stripped = stripped[:-3]
        return stripped.strip()

    def _normalize_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Convert raw LLM JSON payload into parser-compatible shape."""
        days = self._normalize_days(payload.get("days"))
        filters = self._normalize_filters(payload.get("filters"))
        poi = self._normalize_poi(payload.get("poi"))
        place = self._normalize_place(payload.get("place"))
        return {
            "days": days,
            "filters": filters,
            "poi": poi,
            "place": place or None,
        }

    def _normalize_days(self, value: Any) -> Optional[int]:
        """Ensure days is an integer within the accepted range."""
        if value in (None, ""):
            return None
        try:
            days_value = int(float(value))
        except (TypeError, ValueError):
            return None
        if days_value <= 0 or days_value > self.max_days:
            return None
        return days_value

    def _normalize_filters(self, value: Any) -> List[str]:
        """Normalize filter array and drop duplicates."""
        if value is None:
            return []
        if isinstance(value, str):
            values = [value]
        elif isinstance(value, list):
            values = value
        else:
            return []

        normalized: List[str] = []
        seen = set()
        for item in values:
            if not isinstance(item, str):
                continue
            key = item.strip().lower()
            if key in _ALLOWED_FILTERS and key not in seen:
                seen.add(key)
                normalized.append(key)
        return normalized

    def _normalize_poi(self, value: Any) -> List[str]:
        """Ensure POI is always returned as a list."""
        if value is None:
            return []
        values = value if isinstance(value, list) else [value]
        pois: List[str] = []
        for item in values:
            if item is None:
                continue
            text = str(item).strip()
            if text:
                pois.append(text)
        return pois

    def _normalize_place(self, value: Any) -> str:
        """Return cleaned place string from multiple potential shapes."""
        if value is None:
            return ""
        if isinstance(value, dict):
            value = value.get("name") or value.get("text") or value.get("value") or ""
        return str(value).strip()
