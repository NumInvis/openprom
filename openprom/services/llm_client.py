"""Unified LLM client for OpenPROM.

Exposes a single OpenAI-compatible client configured from environment/config.
Supports plain chat, function-calling tool loops, and progress streaming.
"""

import json
import logging
import time
import threading
from typing import Any, Dict, Iterable, List, Optional, Callable
from dataclasses import dataclass

from openai import OpenAI
from openai.types.chat import ChatCompletion

from openprom.infrastructure.config.settings import get_settings
from openprom.tools.schemas import Tool
from openprom.utils.json_parser import parse_llm_json_response

logger = logging.getLogger(__name__)


@dataclass
class LLMResponse:
    """Normalized LLM response."""
    content: str
    tool_calls: List[Dict[str, Any]]
    model: str
    usage: Optional[Dict[str, int]] = None


class LLMClient:
    """Thread-safe singleton-ish LLM client.

    Uses the credentials passed in at construction; if none provided, reads
    from the standard env/config chain.
    """

    _lock: threading.Lock = threading.Lock()

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
    ):
        from openprom.utils.env_config import get_api_key, get_base_url, get_model

        self.api_key = api_key or get_api_key()
        self.base_url = base_url or get_base_url()
        self.model = model or get_model()
        self._client: Optional[OpenAI] = None
        self._settings = get_settings()

    def _ensure_client(self) -> OpenAI:
        if self._client is not None:
            return self._client
        with self._lock:
            if self._client is None:
                if not self.api_key:
                    raise RuntimeError("LLM API key is not configured")
                self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def _call(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        timeout: float,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[str] = None,
        stream: bool = False,
    ) -> ChatCompletion:
        client = self._ensure_client()
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "timeout": timeout,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        max_retries = self._settings.api.max_retries
        retry_delay = self._settings.api.retry_delay

        last_error: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                return client.chat.completions.create(**kwargs)
            except Exception as e:
                last_error = e
                logger.warning(f"LLM call failed (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
        raise RuntimeError(f"LLM call failed after {max_retries} attempts: {last_error}")

    def chat(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        json_mode: bool = False,
    ) -> Dict[str, Any]:
        """Simple chat completion.

        If json_mode is True, attempts to parse content as JSON.
        """
        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        temp = temperature if temperature is not None else self._settings.api.temperature_generation
        response = self._call(
            messages=messages,
            temperature=temp,
            timeout=self._settings.api.model_timeout,
        )
        content = response.choices[0].message.content or ""
        if json_mode:
            return parse_llm_json_response(content)
        return {"content": content, "raw": response}

    def chat_with_tools(
        self,
        prompt: str,
        tools: List[Tool],
        system_prompt: Optional[str] = None,
        max_rounds: int = 5,
        temperature: Optional[float] = None,
        progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
    ) -> Dict[str, Any]:
        """Run a tool-calling loop.

        The LLM may call tools; each tool result is appended to the conversation.
        Returns the final assistant message content and the full message history.
        """
        messages: List[Dict[str, Any]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        tool_schemas = [t.to_openai_schema() for t in tools]
        registry = {t.name: t.func for t in tools}
        temp = temperature if temperature is not None else self._settings.api.temperature_generation

        for round_idx in range(max_rounds):
            if progress_callback:
                progress_callback("thinking", {"round": round_idx + 1, "max_rounds": max_rounds})

            response = self._call(
                messages=messages,
                temperature=temp,
                timeout=self._settings.api.model_timeout,
                tools=tool_schemas,
            )
            message = response.choices[0].message
            assistant_msg = {
                "role": "assistant",
                "content": message.content or "",
            }
            if message.tool_calls:
                assistant_msg["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]
            messages.append(assistant_msg)

            if not message.tool_calls:
                if progress_callback:
                    progress_callback("done", {"content": message.content or ""})
                return {"content": message.content or "", "messages": messages}

            # Execute tools
            for tc in message.tool_calls:
                name = tc.function.name
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                if name not in registry:
                    result = {"error": f"Unknown tool: {name}"}
                else:
                    if progress_callback:
                        progress_callback("tool_call", {"tool": name, "arguments": args})
                    try:
                        result = registry[name](**args)
                    except Exception as e:
                        logger.exception(f"Tool {name} execution failed")
                        result = {"error": str(e)}
                if progress_callback:
                    progress_callback("tool_result", {"tool": name, "result": result})
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        # If we exhaust rounds without a final answer, return the last assistant message.
        last = messages[-1]
        return {"content": last.get("content", ""), "messages": messages}

    def stream_progress(
        self,
        prompt: str,
        tools: List[Tool],
        system_prompt: Optional[str] = None,
        max_rounds: int = 5,
        temperature: Optional[float] = None,
    ) -> Iterable[str]:
        """Yield SSE-style data lines for a tool-calling generation process.

        Each yielded string is a JSON object prefixed with "data: " and ends with two newlines,
        suitable for StreamingResponse with media_type="text/event-stream".
        """

        def emit(event: str, payload: Dict[str, Any]) -> None:
            line = json.dumps({"event": event, **payload}, ensure_ascii=False)
            yield f"data: {line}\n\n"

        buffer: List[str] = []

        def progress_callback(event: str, payload: Dict[str, Any]) -> None:
            line = json.dumps({"event": event, **payload}, ensure_ascii=False)
            buffer.append(line)

        result = self.chat_with_tools(
            prompt=prompt,
            tools=tools,
            system_prompt=system_prompt,
            max_rounds=max_rounds,
            temperature=temperature,
            progress_callback=progress_callback,
        )

        for line in buffer:
            yield f"data: {line}\n\n"

        final = {"event": "final", "content": result.get("content", "")}
        yield f"data: {json.dumps(final, ensure_ascii=False)}\n\n"


_client_instance: Optional[LLMClient] = None
_client_lock = threading.Lock()


def get_llm_client(
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> LLMClient:
    """Get the global LLM client instance."""
    global _client_instance
    if _client_instance is None:
        with _client_lock:
            if _client_instance is None:
                _client_instance = LLMClient(api_key=api_key, base_url=base_url, model=model)
    return _client_instance
