import os
from PIL import Image, ImageDraw, ImageFont
import requests
from urllib.parse import quote_plus
import json
import os
import time
import hashlib


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


def search_images_unsplash(query: str, max_results: int = 6) -> list:
    """Search Unsplash for the query. Requires UNSPLASH_ACCESS_KEY env var.

    Returns list of dicts: {url, thumbnail, source, attribution}
    """
    key = os.getenv("UNSPLASH_ACCESS_KEY")
    if not key:
        return []
    try:
        url = f"https://api.unsplash.com/search/photos?query={quote_plus(query)}&per_page={max_results}"
        headers = {"Authorization": f"Client-ID {key}"}
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        js = r.json()
        out = []
        for it in js.get("results", [])[:max_results]:
            out.append({
                "url": it.get("urls", {}).get("full"),
                "thumbnail": it.get("urls", {}).get("small"),
                "source": "unsplash",
                "attribution": it.get("user", {}).get("name"),
            })
        return out
    except Exception:
        return []


def search_images_duckduckgo(query: str, max_results: int = 6) -> list:
    """Fallback image search using DuckDuckGo's unofficial JSON endpoint."""
    out = []
    try:
        params = {"q": query}
        headers = {"User-Agent": "SocialBot/1.0"}
        r = requests.get("https://duckduckgo.com/i.js", params=params, headers=headers, timeout=10)
        r.raise_for_status()
        data = r.json()
        results = data.get("results", []) if isinstance(data, dict) else []
        for it in results[:max_results]:
            out.append({
                "url": it.get("image"),
                "thumbnail": it.get("thumbnail") or it.get("image"),
                "source": "duckduckgo",
                "attribution": None,
            })
    except Exception:
        pass
    return out


def search_images(query: str, max_results: int = 6) -> list:
    """Try Unsplash first, then fallback to DuckDuckGo."""
    # simple file-based TTL cache to avoid repeating search API calls
    try:
        cache_dir = os.path.join(os.getcwd(), ".image_search_cache")
        os.makedirs(cache_dir, exist_ok=True)
        key = hashlib.sha256((query + str(max_results)).encode("utf-8")).hexdigest()
        cache_file = os.path.join(cache_dir, key + ".json")
        ttl = 60 * 60 * 12  # 12 hours
        if os.path.exists(cache_file):
            stat = os.path.getmtime(cache_file)
            if time.time() - stat < ttl:
                with open(cache_file, "r", encoding="utf-8") as f:
                    try:
                        return json.load(f)
                    except Exception:
                        pass
    except Exception:
        cache_file = None

    res = search_images_unsplash(query, max_results)
    if not res:
        res = search_images_duckduckgo(query, max_results)

    try:
        if cache_file and res:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(res, f)
    except Exception:
        pass
    return res


def download_image_to(path: str, url: str) -> str:
    """Download an image URL to a local path. Returns the path."""
    r = requests.get(url, stream=True, timeout=15, headers={"User-Agent": "SocialBot/1.0"})
    r.raise_for_status()
    with open(path, "wb") as f:
        for chunk in r.iter_content(8192):
            if chunk:
                f.write(chunk)
    return path
