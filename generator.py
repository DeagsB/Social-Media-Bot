import os
import random
import re

PROMO_WORDS = [
    "discount", "sale", "promo", "coupon", "deal", "offer", "free", "save", "clearance"
]


class BrandProfile:
    def __init__(self, name: str = "", keywords=None, banned=None):
        self.name = name
        self.keywords = keywords or []
        self.banned = banned or []


class PostGenerator:
    """Generate short social posts focused on engagement without promotions."""

    def __init__(self):
        # Simple templates focused on engagement: questions, tips, behind-the-scenes, stories
        self.templates = [
            "{emoji} {topic} — what's one tip you'd add?",
            "Quick insight about {topic}: {insight} {emoji}",
            "Behind the scenes: {topic} {emoji} Tell us your experience.",
            "We tried a new approach to {topic} and learned: {insight} {emoji}",
            "Did you know? {topic} {emoji} Share your thoughts.",
        ]

        self.insights = [
            "small changes matter",
            "consistency wins over time",
            "audience feedback shaped this",
            "we simplified the process",
            "focus on the customer experience",
        ]

        self.emojis = ["🔍", "✨", "💡", "📣", "👀", "🤝"]

    def _contains_promo(self, text: str) -> bool:
        txt = text.lower()
        for p in PROMO_WORDS:
            if re.search(r"\b" + re.escape(p) + r"\b", txt):
                return True
        return False

    def generate(self, topic: str, tone: str = "friendly", brand: BrandProfile = None) -> str:
        # sanitize and limit topic early so templates fit
        if not isinstance(topic, str):
            raise ValueError("topic required")
        topic = topic.strip()
        if not topic:
            raise ValueError("topic required")
        # limit very long topics to keep templates readable
        if len(topic) > 100:
            topic = topic[:100].rstrip()

        # If AI is enabled in settings, try using ChatGPT to generate a brand-aligned post
        try:
            from storage import get_setting

            if get_setting("ENABLE_AI") == "1":
                try:
                    from ai_client import AIClient

                    client = AIClient()
                    # build a clear prompt that includes brand keywords and banned words
                    prompt_parts = [
                        f"Write a short social media post about: {topic}",
                        f"Tone: {tone}",
                        "Do NOT include promotions or discount language.",
                    ]
                    if brand:
                        if brand.keywords:
                            prompt_parts.append("Include these brand keywords when appropriate: " + ", ".join(brand.keywords))
                        if brand.banned:
                            prompt_parts.append("Never use these words/phrases: " + ", ".join(brand.banned))
                    prompt = "\n".join(prompt_parts)
                    ai_text = client.generate_text(prompt=prompt, max_tokens=120)
                    # guard: ensure AI returned something useful
                    if not ai_text or not ai_text.strip():
                        raise RuntimeError("AI returned empty output; falling back")
                    # guard against promo words and banned words using helper
                    lowered = ai_text.lower()
                    banned_list = (brand.banned if brand else []) + PROMO_WORDS
                    if self._contains_promo(lowered) or any(
                        re.search(r"\b" + re.escape(b) + r"\b", lowered) for b in (brand.banned if brand else [])
                    ):
                        # fall back to rule-based
                        raise RuntimeError("AI output contained banned words; falling back")
                    return ai_text[:280]
                except Exception:
                    # if AI client fails for any reason, continue to template generation
                    pass
        except Exception:
            # if storage isn't available, ignore and continue
            pass

        # create candidate posts until one passes the promo filter
        attempts = 0
        while attempts < 10:
            tmpl = random.choice(self.templates)
            insight = random.choice(self.insights)
            emoji = random.choice(self.emojis)
            post = tmpl.format(topic=topic, insight=insight, emoji=emoji)
            # apply tone tweaks
            if tone == "casual":
                post = post.replace("we", "we").replace("Tell us", "Tell us")
            elif tone == "professional":
                post = post.replace("Tell us your experience.", "We welcome your feedback.")

            # inject brand keywords if provided
            if brand and brand.keywords:
                kw = random.choice(brand.keywords)
                post = f"{post} {kw}"

            # filter banned words from brand
            banned = set((brand.banned if brand else []) + PROMO_WORDS)
            if any(re.search(r"\b" + re.escape(b) + r"\b", post.lower()) for b in banned):
                attempts += 1
                continue

            # ensure length suitable for Twitter/X style platforms (<= 280 chars)
            return post[:280]
            attempts += 1

        # fallback: sanitize topic and return neutral post
        safe_topic = re.sub(r"\W+", " ", topic)
        return f"{random.choice(self.emojis)} Thoughts on {safe_topic}?"

    def generate_from_image(self, image_record: dict, tone: str = "friendly", brand: BrandProfile = None) -> str:
        """Generate a post based on an image record from image_db.list_images()/get_image().

        image_record should contain: path, title, description, tags (list), metadata (dict).
        """
        if not image_record or not isinstance(image_record, dict):
            raise ValueError("image_record required")

        # Build a short description from available fields
        parts = []
        if image_record.get("title"):
            parts.append(image_record["title"])
        if image_record.get("description"):
            parts.append(image_record["description"])
        if image_record.get("tags"):
            parts.append("tags: " + ", ".join(image_record.get("tags", [])))

        topic = " ".join(parts).strip() or os.path.basename(image_record.get("path", ""))

        # If AI enabled, ask AI to write a post describing the item and suggesting why a customer might like it.
        try:
            from storage import get_setting

            if get_setting("ENABLE_AI") == "1":
                try:
                    from ai_client import AIClient

                    client = AIClient()
                    prompt_parts = [
                        f"Look at this product image and metadata: {topic}",
                        f"Tags: {', '.join(image_record.get('tags', []))}",
                        f"Write a short social post (<=280 chars) that highlights the product and why a customer would like it. Do NOT include promotions or discount language.",
                    ]
                    if brand and brand.keywords:
                        prompt_parts.append("Use brand keywords when appropriate: " + ", ".join(brand.keywords))
                    prompt = "\n".join(p for p in prompt_parts if p)
                    ai_text = client.generate_text(prompt=prompt, max_tokens=140)
                    if not ai_text or not ai_text.strip():
                        raise RuntimeError("AI returned empty output; falling back")
                    lowered = ai_text.lower()
                    banned_list = (brand.banned if brand else []) + PROMO_WORDS
                    if self._contains_promo(lowered) or any(re.search(r"\b" + re.escape(b) + r"\b", lowered) for b in (brand.banned if brand else [])):
                        raise RuntimeError("AI output contained banned words; falling back")
                    return ai_text[:280]
                except Exception:
                    pass
        except Exception:
            pass

        # fallback to a template using the detected topic/tags
        base_topic = topic or "this product"
        post = random.choice(self.templates).format(topic=base_topic, insight=random.choice(self.insights), emoji=random.choice(self.emojis))
        if brand and brand.keywords:
            post = f"{post} {random.choice(brand.keywords)}"
        if self._contains_promo(post.lower()):
            return f"{random.choice(self.emojis)} Check out {base_topic}."
        return post[:280]
