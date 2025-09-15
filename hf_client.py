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
            # For image inputs we send binary data, for text we send JSON.
            if is_image:
                # data expected to be a path to a file or binary bytes
                if isinstance(data, (bytes, bytearray)):
                    resp = requests.post(url, headers=headers, data=data, timeout=120)
                else:
                    with open(data, "rb") as f:
                        resp = requests.post(url, headers=headers, data=f.read(), timeout=120)
            else:
                # allow passing dict for model-specific params
                if isinstance(data, dict):
                    payload = data
                else:
                    payload = {"inputs": data}
                resp = requests.post(url, headers=headers, json=payload, timeout=120)
            resp.raise_for_status()
            # Some HF models return binary (for image-generation) or json
            content_type = resp.headers.get("Content-Type", "")
            if "application/json" in content_type:
                return resp.json()
            # for image bytes return raw content
            return resp.content
        except Exception as e:
            raise RuntimeError(f"HF inference API call failed: {e}")

    def generate_image(self, prompt: str, out_path: str, model: str = "stabilityai/stable-diffusion-2", params: dict = None) -> str:
        """Generate image using Hugging Face Inference API and save to out_path.

        params can include model-specific options; function falls back to returning a placeholder
        if the API is not available.
        """
        # try local diffusers/transformers first if available
        try:
            # local generation via diffusers if installed
            from diffusers import StableDiffusionPipeline
            import torch

            pipe = StableDiffusionPipeline.from_pretrained(model, torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32)
            if torch.cuda.is_available():
                pipe = pipe.to("cuda")
            guidance = params.get("guidance_scale", 7.5) if params else 7.5
            steps = params.get("num_inference_steps", 50) if params else 50
            img = pipe(prompt, guidance_scale=guidance, num_inference_steps=steps).images[0]
            img.save(out_path)
            return out_path
        except Exception:
            # fallback to HF Inference API
            if not self.token:
                raise RuntimeError("Hugging Face API token not configured for image generation")
            payload = {
                "inputs": prompt,
            }
            if params:
                payload.update(params)
            # The image endpoint can return binary image bytes directly
            result = self._call_inference_api(model, payload, is_image=False)
            # If API returns bytes it will be raw content
            if isinstance(result, (bytes, bytearray)):
                with open(out_path, "wb") as f:
                    f.write(result)
                return out_path
            # If JSON with base64
            if isinstance(result, dict):
                # common key: 'image' or 'images' or data[0]['b64_json']
                if "image" in result and isinstance(result["image"], str):
                    import base64

                    b = base64.b64decode(result["image"])
                    with open(out_path, "wb") as f:
                        f.write(b)
                    return out_path
                if "images" in result and isinstance(result["images"], list) and len(result["images"]):
                    import base64

                    b = base64.b64decode(result["images"][0])
                    with open(out_path, "wb") as f:
                        f.write(b)
                    return out_path
            # try list shape
            if isinstance(result, list) and len(result) and isinstance(result[0], dict):
                first = result[0]
                if "b64_json" in first:
                    import base64

                    b = base64.b64decode(first["b64_json"])
                    with open(out_path, "wb") as f:
                        f.write(b)
                    return out_path
                if "generated_image" in first and isinstance(first["generated_image"], str):
                    import base64

                    b = base64.b64decode(first["generated_image"])
                    with open(out_path, "wb") as f:
                        f.write(b)
                    return out_path

            # If we reach here we couldn't decode the response
            raise RuntimeError("Unexpected response from HF image generation API")

    def caption_image(self, path: str, model: str = "Salesforce/blip-image-captioning-large") -> str:
        # simple cache by file md5 to reduce repeated calls
        try:
            import hashlib, json

            cache_dir = os.path.join(os.getcwd(), ".cache")
            os.makedirs(cache_dir, exist_ok=True)
            cache_file = os.path.join(cache_dir, "hf_captions.json")
            # compute md5
            h = hashlib.md5()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
            key = h.hexdigest()
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as cf:
                        cache = json.load(cf)
                except Exception:
                    cache = {}
            else:
                cache = {}
            if key in cache:
                return cache[key]

        except Exception:
            cache = None

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
        finally:
            # write to cache if we have a caption and cache path
            try:
                if cache is not None and key and caption:
                    cache[key] = caption
                    with open(cache_file, "w", encoding="utf-8") as cf:
                        json.dump(cache, cf, ensure_ascii=False, indent=2)
            except Exception:
                pass

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
