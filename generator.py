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

        # If AI is enabled in settings, use the OpenAI-only agent pipeline (generate->critique->refine)
        try:
            from storage import get_setting

            if get_setting("ENABLE_AI") == "1":
                try:
                    from openai_agent import OpenAIAgent
                    from ai_client import AIClient

                    agent = OpenAIAgent(AIClient())
                    result = agent.generate_post(topic=topic, tone=tone, brand=(brand.__dict__ if brand else None))
                    # OpenAIAgent returns a dict with metadata; extract final text if so
                    if isinstance(result, dict):
                        final_text = result.get("final") or (result.get("variants") and result.get("variants")[0])
                        if final_text and isinstance(final_text, str) and final_text.strip():
                            return final_text[:280]
                    elif isinstance(result, str):
                        if result.strip():
                            return result[:280]
                except Exception:
                    # fall back to templates below
                    pass
        except Exception:
            # storage not available; fall back to templates
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

        # If AI enabled, use AIClient to write a post from image metadata
        try:
            from storage import get_setting

            if get_setting("ENABLE_AI") == "1":
                try:
                    from ai_client import AIClient

                    client = AIClient()
                    prompt_parts = [
                        f"Write a short social post about: {topic}",
                        f"Tags: {', '.join(image_record.get('tags', []))}",
                        "Write a short social post (<=280 chars) that highlights the product and why a customer would like it. Do NOT include promotions or discount language.",
                    ]
                    if brand and brand.keywords:
                        prompt_parts.append("Use brand keywords when appropriate: " + ", ".join(brand.keywords))
                    prompt = "\n".join(p for p in prompt_parts if p)
                    ai_text = client.generate_text(prompt=prompt, max_tokens=140)
                    if ai_text and ai_text.strip():
                        lowered = ai_text.lower()
                        if self._contains_promo(lowered) or any(re.search(r"\b" + re.escape(b) + r"\b", lowered) for b in (brand.banned if brand else [])):
                            ai_text = None
                        else:
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

    def generate_with_metadata(self, topic: str, tone: str = "friendly", brand: BrandProfile = None) -> dict:
        """Return structured metadata for a generated post: variants, final, hashtags, alt_text, moderation."""
        try:
            from storage import get_setting

            if get_setting("ENABLE_AI") == "1":
                try:
                    from openai_agent import OpenAIAgent
                    from ai_client import AIClient

                    agent = OpenAIAgent(AIClient())
                    return agent.generate_post(topic=topic, tone=tone, brand=(brand.__dict__ if brand else None))
                except Exception:
                    pass
        except Exception:
            pass

        # fallback: simple metadata from template
        post = self.generate(topic=topic, tone=tone, brand=brand)
        return {
            "variants": [post],
            "final": post,
            "hashtags": [],
            "alt_text": None,
            "moderation": {"ok": True, "issues": []},
        }

    def get_image_suggestions(self, ai_client, post_text: str, alt_text: str = None, hashtags: list = None, n_queries: int = 2, max_results: int = 6) -> list:
        """Generate image search queries using the ai_client and return aggregated image search results.

        Returns a list of candidate dicts with keys: url, thumbnail, source, attribution
        """
        # build prompt to ask AI for short image search queries
        try:
            prompt = (
                f"Produce {n_queries} short image search queries (2-6 words each) to find photos matching this social media post.\n\n"
                f"Post: {post_text}\nAlt: {alt_text or ''}\nHashtags: {', '.join(hashtags or [])}\n\nReturn a JSON array of strings only."
            )
            out = ai_client.generate_text(prompt=prompt, max_tokens=120, temperature=0.2)
        except Exception:
            out = None

        queries = []
        if out:
            import json, re

            try:
                m = re.search(r"(\[.*\])", out, re.S)
                if m:
                    arr = json.loads(m.group(1))
                    queries = [a.strip() for a in arr if isinstance(a, str)]
                else:
                    lines = [l.strip("-• \t") for l in out.splitlines() if l.strip()]
                    queries = [l for l in lines if len(l.split()) <= 6][:n_queries]
            except Exception:
                queries = []

        if not queries:
            # fallback: derive simple queries from post_text
            tokens = post_text.split()
            queries = [" ".join(tokens[:4]), " ".join(tokens[-4:])] if len(tokens) > 1 else [post_text]

        # search for each query and aggregate
        results = []
        try:
            import image_utils

            for q in queries[:n_queries]:
                found = image_utils.search_images(q, max_results=max_results)
                for f in found:
                    # avoid duplicates by url
                    if not any(existing.get("url") == f.get("url") for existing in results):
                        results.append(f)
                        if len(results) >= max_results:
                            break
                if len(results) >= max_results:
                    break
        except Exception:
            pass
        return results
