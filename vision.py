"""Optional vision helpers: local image captioning using transformers/BLIP.

This module is optional. It will try to import required heavy dependencies only when
caption_image() is called. If dependencies are missing it raises an informative error.
"""
from typing import Optional


def caption_image_local(path: str) -> str:
    """Attempt to produce an image caption using a local model (transformers + torchvision).

    Raises RuntimeError with a message if dependencies are unavailable.
    """
    try:
        from transformers import BlipProcessor, BlipForConditionalGeneration
        from PIL import Image
    except Exception as e:
        raise RuntimeError("Local captioner dependencies missing. Install 'transformers' and 'torch' to enable this feature.")

    try:
        processor = BlipProcessor.from_pretrained("Salesforce/blip-image-captioning-base")
        model = BlipForConditionalGeneration.from_pretrained("Salesforce/blip-image-captioning-base")
        img = Image.open(path).convert("RGB")
        inputs = processor(images=img, return_tensors="pt")
        out = model.generate(**inputs)
        caption = processor.decode(out[0], skip_special_tokens=True)
        return caption
    except Exception as e:
        raise RuntimeError(f"Captioning failed: {e}")


def caption_image(path: str) -> str:
    """Higher-level wrapper: try local captioner, otherwise return empty string."""
    try:
        return caption_image_local(path)
    except RuntimeError:
        return ""