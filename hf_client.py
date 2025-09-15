import os
import requests
from typing import Optional


class HFClient:
    """Thin wrapper to use Hugging Face Inference API (preferred) or local transformers when available.

    Reads token from arg, env HF_API_TOKEN, or storage.get_setting("HF_API_TOKEN").
    """

    def __init__(self, token: Optional[str] = None):
        token = token or os.getenv("HF_API_TOKEN")
        if not token:
            try:
                from storage import get_setting

                token = get_setting("HF_API_TOKEN")
            except Exception:
                token = None
        self.token = token

    def _call_inference_api(self, model: str, data, is_image: bool = False):
        if not self.token:
            raise RuntimeError("Hugging Face API token not configured")
        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            if is_image:
                with open(data, "rb") as f:
                    resp = requests.post(url, headers=headers, data=f, timeout=60)
            else:
                resp = requests.post(url, headers=headers, json={"inputs": data}, timeout=60)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            raise RuntimeError(f"HF inference API call failed: {e}")

    def caption_image(self, path: str, model: str = "Salesforce/blip-image-captioning-large") -> str:
        # Try local transformers first
        try:
            from transformers import BlipProcessor, BlipForConditionalGeneration
            from PIL import Image
            processor = BlipProcessor.from_pretrained(model)
            model_local = BlipForConditionalGeneration.from_pretrained(model)
            img = Image.open(path).convert("RGB")
            inputs = processor(images=img, return_tensors="pt")
            out = model_local.generate(**inputs)
            caption = processor.decode(out[0], skip_special_tokens=True)
            return caption
        except Exception:
            # fallback to Inference API
            if not self.token:
                raise RuntimeError("No local captioner available and HF_API_TOKEN not set")
            j = self._call_inference_api(model, path, is_image=True)
            # response may be a list or dict
            if isinstance(j, dict) and "generated_text" in j:
                return j["generated_text"]
            if isinstance(j, list) and len(j) and isinstance(j[0], dict):
                # common shape: [{"generated_text": "..."}]
                return j[0].get("generated_text") or ""
            # try string
            if isinstance(j, str):
                return j
            return ""

    def generate_text(self, prompt: str, model: str = "gpt2", max_length: int = 150) -> str:
        # Try local pipeline
        try:
            from transformers import pipeline
            gen = pipeline("text-generation", model=model)
            out = gen(prompt, max_length=max_length, do_sample=True, top_p=0.95)
            if isinstance(out, list) and len(out):
                return out[0].get("generated_text", "").strip()
            return str(out)
        except Exception:
            # fallback to HF inference API
            if not self.token:
                raise RuntimeError("No local text-generation model and HF_API_TOKEN not set")
            j = self._call_inference_api(model, prompt, is_image=False)
            # Many HF text models return [{'generated_text': '...'}]
            if isinstance(j, list) and len(j) and isinstance(j[0], dict):
                return j[0].get("generated_text", "").strip()
            if isinstance(j, dict) and "generated_text" in j:
                return j["generated_text"].strip()
            if isinstance(j, str):
                return j.strip()
            return ""
