"""
LLM providers behind one small interface.

The rest of the application only calls provider.complete(system, user) and gets text back, so
switching provider (OpenAI, Gemini, a local Ollama/LM Studio server, or the offline mock) does not
change any other code. Adding a provider means adding one entry to PROVIDERS.
"""

import json
import os
import time
from dataclasses import dataclass


class ProviderError(Exception):
    """The provider could not produce a response (bad key, quota, network, unknown model...)."""


@dataclass
class ProviderConfig:
    name: str
    base_url: str | None      # None = OpenAI's default endpoint
    key_env: str | None       # environment variable that holds the API key (None = no key needed)
    default_model: str
    json_mode: bool = True    # ask the server for a JSON object response


PROVIDERS = {
    "openai":   ProviderConfig("OpenAI", None, "OPENAI_API_KEY", "gpt-4o-mini"),
    "gemini":   ProviderConfig("Google Gemini", "https://generativelanguage.googleapis.com/v1beta/openai/",
                               "GEMINI_API_KEY", "gemini-3.5-flash-lite"),
    "ollama":   ProviderConfig("Ollama (local)", "http://localhost:11434/v1", None, "llama3.1"),
    "lmstudio": ProviderConfig("LM Studio (local)", "http://localhost:1234/v1", None, "local-model"),
    "mock":     ProviderConfig("Offline mock (testing)", None, None, "mock"),
}


class LLMProvider:
    """Common interface: every provider returns the model's raw text."""
    name = "base"
    model = ""

    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


class OpenAICompatibleProvider(LLMProvider):
    """Works with any server that speaks the OpenAI Chat Completions API."""

    def __init__(self, config: ProviderConfig, model: str | None = None, temperature: float = 0.2):
        try:
            from openai import OpenAI
        except ImportError:
            raise ProviderError("the 'openai' package is not installed (pip install openai)")
        api_key = "not-needed"
        if config.key_env:
            api_key = os.getenv(config.key_env)
            if not api_key:
                raise ProviderError(f"{config.key_env} is not set. In PowerShell: $env:{config.key_env}=\"your-key\"")
        self.name = config.name
        self.model = model or config.default_model
        self.temperature = temperature
        self.json_mode = config.json_mode
        self.client = OpenAI(api_key=api_key, base_url=config.base_url, timeout=60, max_retries=2)

    def complete(self, system: str, user: str) -> str:
        from openai import (APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError,
                            BadRequestError, NotFoundError, RateLimitError)
        params = {"model": self.model, "temperature": self.temperature,
                  "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if self.json_mode:
            params["response_format"] = {"type": "json_object"}
        try:
            try:
                response = self.client.chat.completions.create(**params)
            except BadRequestError:
                if not self.json_mode:
                    raise
                # Some servers or models do not support JSON mode: retry once without it.
                self.json_mode = False
                params.pop("response_format")
                response = self.client.chat.completions.create(**params)
        except AuthenticationError:
            raise ProviderError("authentication failed: check the API key")
        except NotFoundError:
            raise ProviderError(f"model '{self.model}' was not found (use --model)")
        except RateLimitError as e:
            raise ProviderError(f"rate limit or quota exceeded: {_message(e)}")
        except APITimeoutError:
            raise ProviderError("the request timed out")
        except APIConnectionError:
            raise ProviderError("could not connect to the provider (is the server running / are you online?)")
        except BadRequestError as e:
            raise ProviderError(f"the provider rejected the request: {_message(e)}")
        except APIStatusError as e:
            raise ProviderError(f"provider error {e.status_code}: {_message(e)}")
        return response.choices[0].message.content or ""


class MockProvider(LLMProvider):
    """
    Offline provider for testing without an API key.
    'kallis' returns the example entry; 'tyhjä' returns an entry with an empty definition list
    (to demonstrate validation); 'rikki' returns broken JSON; any other word returns a generic entry.
    """
    name = "Offline mock (testing)"
    model = "mock"

    def complete(self, system: str, user: str) -> str:
        time.sleep(0.2)
        word = user.split("WORD:", 1)[-1].strip().splitlines()[0].strip()
        if word.casefold() == "kallis":
            return json.dumps({
                "word": "kallis",
                "definitions": ["expensive", "dear", "costly"],
                "synonyms": ["hintava", "arvokas", "tyyris"],
                "antonyms": ["halpa", "edullinen"],
                "examples": ["Tämä auto on liian kallis.", "Hän on minulle hyvin kallis ystävä."],
            }, ensure_ascii=False)
        if word.casefold() == "tyhjä":
            return json.dumps({"word": word, "definitions": [], "synonyms": [], "antonyms": [], "examples": []})
        if word.casefold() == "rikki":
            return '{"word": "rikki", "definitions": ["broken"'
        return json.dumps({"word": word, "definitions": [f"(mock definition of {word})"],
                           "synonyms": [], "antonyms": [], "examples": [f"(mock example using {word})"]})


def create_provider(key: str, model: str | None = None, temperature: float = 0.2) -> LLMProvider:
    if key not in PROVIDERS:
        raise ProviderError(f"unknown provider '{key}'. Choose one of: {', '.join(PROVIDERS)}")
    if key == "mock":
        return MockProvider()
    return OpenAICompatibleProvider(PROVIDERS[key], model, temperature)


def _message(e: Exception) -> str:
    body = getattr(e, "body", None)
    if isinstance(body, dict):
        msg = body.get("message") or (body.get("error") or {}).get("message")
        if msg:
            return msg
    if isinstance(body, list) and body and isinstance(body[0], dict):
        return str(body[0].get("error", {}).get("message", body))
    return str(e)
