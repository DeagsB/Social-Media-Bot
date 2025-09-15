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
        topic = topic.strip()
        if not topic:
            raise ValueError("topic required")

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
