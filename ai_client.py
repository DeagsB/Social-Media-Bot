import os
import requests
from typing import Optional


class AIClient:
    """Wrapper that supports modern and legacy OpenAI clients.

    It reads the API key from the provided api_key argument, the OPENAI_API_KEY
    environment variable, or from storage.get_setting("OPENAI_API_KEY") if available.
    """

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            try:
                from storage import get_setting

                key = get_setting("OPENAI_API_KEY")
            except Exception:
                key = None

        if not key:
            raise RuntimeError("OpenAI API key not found. Set OPENAI_API_KEY or store in settings.")

        # Try the modern OpenAI client first (if installed)
        try:
            from openai import OpenAI

            self._client_type = "modern"
            self._client = OpenAI(api_key=key)
            return
        except Exception:
            pass

        # Fall back to legacy openai package
        try:
            import openai

            openai.api_key = key
            self._client_type = "legacy"
            self._client = openai
            return
        except Exception:
            raise RuntimeError("Could not initialize OpenAI client. Ensure 'openai' package is installed.")

    def generate_text(self, prompt: str, max_tokens: int = 150, temperature: float = 0.8) -> str:
        """Generate text from a prompt. Returns the generated string or raises on error."""
        if self._client_type == "modern":
            # modern client: try chat completion API then Responses as a fallback
            try:
                resp = self._client.chat.completions.create(
                    model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], max_tokens=max_tokens, temperature=temperature
                )
                choices = getattr(resp, "choices", None)
                if choices and len(choices) > 0:
                    msg = choices[0].message
                    content = getattr(msg, "content", None)
                    if isinstance(content, str):
                        return content.strip()
                    return str(content).strip()
            except Exception:
                # try Responses API
                try:
                    resp = self._client.responses.create(model="gpt-4o-mini", input=prompt, max_tokens=max_tokens)
                    out_text = getattr(resp, "output_text", None)
                    if out_text:
                        return out_text.strip()
                    parts = []
                    for item in getattr(resp, "output", []) or []:
                        if isinstance(item, dict) and "content" in item:
                            for c in item["content"]:
                                if c.get("type") == "output_text":
                                    parts.append(c.get("text", ""))
                    return "\n".join(parts).strip()
                except Exception:
                    raise
            return ""
        else:
            # legacy openai package
            try:
                resp = self._client.ChatCompletion.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
                choices = resp.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
            except Exception:
                raise
            return ""

    def generate_image(self, prompt: str, out_path: str, size: str = "1024x1024") -> str:
        """Generate an image for the prompt and save it to out_path. Returns out_path."""
        if self._client_type == "modern":
            try:
                resp = self._client.images.generate(model="gpt-image-1", prompt=prompt, size=size)
                data = getattr(resp, "data", None)
                if not data or len(data) == 0:
                    raise RuntimeError("No image returned from API")
                item = data[0]
                url = item.get("url") if isinstance(item, dict) else None
                b64 = item.get("b64_json") if isinstance(item, dict) else None
                if url:
                    r = requests.get(url, stream=True, timeout=15)
                    r.raise_for_status()
                    with open(out_path, "wb") as f:
                        for chunk in r.iter_content(1024):
                            f.write(chunk)
                    return out_path
                if b64:
                    import base64

                    with open(out_path, "wb") as f:
                        f.write(base64.b64decode(b64))
                    return out_path
                raise RuntimeError("Image response did not contain url or b64 data")
            except Exception:
                raise
        else:
            try:
                resp = self._client.Image.create(prompt=prompt, size=size)
                data = resp.get("data")
                if not data:
                    raise RuntimeError("No image returned from API")
                url = data[0].get("url")
                if not url:
                    raise RuntimeError("No URL returned for generated image")
                r = requests.get(url, stream=True)
                r.raise_for_status()
                with open(out_path, "wb") as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
                return out_path
            except Exception:
                raise
