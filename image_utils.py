import os
from PIL import Image, ImageDraw, ImageFont
import requests


def generate_placeholder_image(text: str, out_path: str, size=(800, 450)):
    # Create a simple image with the brand text
    img = Image.new("RGB", size, color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("arial.ttf", 40)
    except Exception:
        font = ImageFont.load_default()
    w, h = draw.textsize(text, font=font)
    draw.text(((size[0]-w)/2, (size[1]-h)/2), text, fill=(0, 0, 0), font=font)
    img.save(out_path)
    return out_path


def download_image(url: str, out_path: str):
    r = requests.get(url, stream=True, timeout=10)
    r.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in r.iter_content(1024):
            f.write(chunk)
    return out_path


def is_valid_image_path(path: str) -> bool:
    if not path:
        return False
    if not os.path.exists(path):
        return False
    try:
        Image.open(path).verify()
        return True
    except Exception:
        return False


def compute_image_metadata(path: str) -> dict:
    """Return simple metadata: width, height, average_color (r,g,b)."""
    try:
        with Image.open(path) as im:
            im = im.convert("RGB")
            w, h = im.size
            # compute average color by resizing to 1x1
            small = im.resize((1, 1))
            avg = small.getpixel((0, 0))
            meta = {"width": w, "height": h, "avg_color": avg}
            # try to compute phash if imagehash is available
            try:
                import imagehash

                ph = imagehash.phash(im)
                meta["phash"] = str(ph)
            except Exception:
                meta["phash"] = None
            return meta
    except Exception:
        return {"width": None, "height": None, "avg_color": None}


def hamming_distance_hex(a: str, b: str) -> int:
    """Compute Hamming distance between two hex phash strings. Returns large int if invalid."""
    if not a or not b:
        return 999
    try:
        # imagehash phash can be represented like 'ff00a0...'
        ha = int(str(a), 16)
        hb = int(str(b), 16)
        x = ha ^ hb
        # count bits
        return bin(x).count("1")
    except Exception:
        return 999
