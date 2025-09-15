import os
import openai
from typing import Optional, Dict, Any


class AIClient:
    """Minimal wrapper for OpenAI Chat and Image (DALL·E or image generation) usage.

    This class expects the OpenAI API key to be available via the environment variable
    OPENAI_API_KEY or via storage.get_setting("OPENAI_API_KEY") if provided.
    """

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or os.getenv("OPENAI_API_KEY")
        if not key:
            # try local storage (avoids importing storage at module import)
            try:
                from storage import get_setting

                key = get_setting("OPENAI_API_KEY")
            except Exception:
                key = None

        if not key:
            raise RuntimeError("OpenAI API key not found. Set OPENAI_API_KEY or store in settings.")

        openai.api_key = key

    def generate_text(self, prompt: str, max_tokens: int = 150, temperature: float = 0.8) -> str:
        resp = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            import os
            from openai import OpenAI
            from typing import Optional
            import requests


            class AIClient:
                """Wrapper for the OpenAI modern client (OpenAI()).

                Reads API key from env OPENAI_API_KEY or from storage setting OPENAI_API_KEY.
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

                    self.client = OpenAI(api_key=key)

                def generate_text(self, prompt: str, max_tokens: int = 150, temperature: float = 0.8) -> str:
                    # Prefer chat completions; fall back to Responses if needed
                    try:
                        resp = self.client.chat.completions.create(
                            model="gpt-4o-mini",
                            messages=[{"role": "user", "content": prompt}],
                            max_tokens=max_tokens,
                            temperature=temperature,
                        )
                        # modern response shape: resp.choices[0].message.content
                        choices = getattr(resp, "choices", None)
                        if choices and len(choices) > 0:
                            msg = choices[0].message
                            if msg and getattr(msg, "content", None):
                                # msg.content may be a dict/list depending on client version
                                content = getattr(msg, "content")
                                if isinstance(content, str):
                                    return content.strip()
                                # if content is a list/dict, attempt to extract text
                                try:
                                    return str(content).strip()
                                except Exception:
                                    return ""
                    except Exception:
                        # try Responses API
                        try:
                            resp = self.client.responses.create(model="gpt-4o-mini", input=prompt, max_tokens=max_tokens)
                            if hasattr(resp, "output_text") and resp.output_text:
                                return resp.output_text.strip()
                            # otherwise try to parse outputs
                            out = []
                            for item in getattr(resp, "output", []) or []:
                                if isinstance(item, dict) and "content" in item:
                                    for c in item["content"]:
                                        if c.get("type") == "output_text":
                                            out.append(c.get("text", ""))
                            return "\n".join(out).strip()
                        except Exception as e:
                            raise
                    return ""

                def generate_image(self, prompt: str, out_path: str, size: str = "1024x1024") -> str:
                    # Use the modern Images API (model=gpt-image-1). Response may contain url or b64_json.
                    resp = self.client.images.generate(model="gpt-image-1", prompt=prompt, size=size)
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
