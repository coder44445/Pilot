"""
Unified LLM client supporting OpenAI and Ollama.

Fixes vs v1:
- Ollama uses streaming so the connection stays alive (no read timeout)
- Separate connect_timeout (5s) vs read_timeout (never)
- Retry with exponential backoff on transient failures
- Progress dots printed during long Ollama generations
- OpenAI uses stream=True as well for consistency
"""

import os
import json
import time
import sys
from typing import Optional
from src.display import console


MAX_RETRIES = 3
RETRY_DELAYS = [3, 8, 20]  # seconds between retries


class LLMClient:
    def __init__(
        self,
        provider: str,
        model: Optional[str] = None,
        ollama_url: str = "http://localhost:11434",
    ):
        self.provider = provider
        self.ollama_url = ollama_url.rstrip("/")

        if provider == "openai":
            self.model = model or "gpt-4o"
        elif provider == "ollama":
            self.model = model or "llama3.1"
        else:
            raise ValueError(f"Unknown provider: {provider}")

    def validate(self):
        """Validate that the LLM is reachable / configured."""
        if self.provider == "openai":
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                console.print("\n[bold yellow]⚠  OPENAI_API_KEY not found in environment.[/bold yellow]")
                api_key = input("Paste your OpenAI API key: ").strip()
                if not api_key:
                    raise ValueError("OpenAI API key is required.")
                os.environ["OPENAI_API_KEY"] = api_key

            try:
                from openai import OpenAI
                self._openai_client = OpenAI(
                    api_key=api_key,
                    timeout=600,  # 10 min hard cap — OpenAI handles keepalive internally
                )
                console.print(f"[green]✓ OpenAI ready (model: {self.model})[/green]")
            except ImportError:
                raise ImportError("OpenAI package not installed. Run: pip install openai")

        elif self.provider == "ollama":
            import urllib.request
            try:
                urllib.request.urlopen(f"{self.ollama_url}/api/tags", timeout=5)
                console.print(f"[green]✓ Ollama connected at {self.ollama_url} (model: {self.model})[/green]")
            except Exception:
                raise ConnectionError(
                    f"Cannot reach Ollama at {self.ollama_url}\n"
                    "  → Make sure Ollama is running:   ollama serve\n"
                    f"  → And the model is pulled:      ollama pull {self.model}"
                )

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def chat(self, system_prompt: str, user_prompt: str, json_mode: bool = False) -> str:
        """Send a chat request and return the full response text. Retries on failure."""
        for attempt in range(MAX_RETRIES):
            try:
                if self.provider == "openai":
                    return self._openai_chat(system_prompt, user_prompt, json_mode)
                elif self.provider == "ollama":
                    return self._ollama_chat_streaming(system_prompt, user_prompt, json_mode)
            except Exception as e:
                is_last = attempt == MAX_RETRIES - 1
                if is_last:
                    raise
                delay = RETRY_DELAYS[attempt]
                console.print(
                    f"\n[yellow]  ⚠ LLM error (attempt {attempt + 1}/{MAX_RETRIES}): {e}[/yellow]"
                    f"\n[dim]  Retrying in {delay}s...[/dim]"
                )
                time.sleep(delay)

    # ------------------------------------------------------------------ #
    #  OpenAI
    # ------------------------------------------------------------------ #

    def _openai_chat(self, system_prompt: str, user_prompt: str, json_mode: bool) -> str:
        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.3,
            "stream": True,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        chunks = []
        with self._openai_client.chat.completions.create(**kwargs) as stream:
            for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    chunks.append(delta)
                    if len(chunks) % 50 == 0:
                        sys.stdout.write(".")
                        sys.stdout.flush()

        if chunks:
            sys.stdout.write("\n")
            sys.stdout.flush()

        return "".join(chunks)

    # ------------------------------------------------------------------ #
    #  Ollama — streaming via raw HTTP to avoid any read timeout
    # ------------------------------------------------------------------ #

    def _ollama_chat_streaming(self, system_prompt: str, user_prompt: str, json_mode: bool) -> str:
        """
        Uses Ollama's streaming API (stream=true).
        Each line is a JSON object with a 'message.content' delta.
        The connection stays alive throughout generation — no timeout issue.
        """
        import http.client

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": True,  # KEY FIX: streaming keeps connection alive
            "options": {
                "temperature": 0.3,
                "num_predict": 4096,
            },
        }
        if json_mode:
            payload["format"] = "json"

        data = json.dumps(payload).encode("utf-8")

        # Parse host/port from ollama_url
        url_clean = self.ollama_url.replace("http://", "").replace("https://", "")
        host, _, port_str = url_clean.partition(":")
        port = int(port_str) if port_str else 80

        chunks = []
        dot_counter = 0

        # Connect with 5s timeout, then remove timeout so reads never expire
        conn = http.client.HTTPConnection(host, port, timeout=5)
        try:
            conn.connect()
            conn.sock.settimeout(None)  # Unlimited read time after connect
            conn.request(
                "POST",
                "/api/chat",
                body=data,
                headers={"Content-Type": "application/json"},
            )

            resp = conn.getresponse()

            if resp.status != 200:
                body = resp.read().decode("utf-8")
                raise RuntimeError(f"Ollama returned HTTP {resp.status}: {body[:300]}")

            # Read streaming NDJSON line by line
            buffer = b""
            while True:
                byte = resp.read(1)
                if not byte:
                    break
                buffer += byte
                if byte == b"\n":
                    line = buffer.decode("utf-8").strip()
                    buffer = b""
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    content = obj.get("message", {}).get("content", "")
                    if content:
                        chunks.append(content)
                        dot_counter += len(content)
                        if dot_counter >= 100:
                            sys.stdout.write(".")
                            sys.stdout.flush()
                            dot_counter = 0

                    if obj.get("done", False):
                        break

        finally:
            conn.close()

        if chunks:
            sys.stdout.write("\n")
            sys.stdout.flush()

        return "".join(chunks)
