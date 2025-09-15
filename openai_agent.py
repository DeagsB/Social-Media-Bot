"""OpenAI-only agent that performs generate -> critique -> refine loops using AIClient.

This is designed to be a drop-in for the repo's `PostGenerator` when you want the
best single-model pipeline for social media posts.

Contract:
- input: topic (str), tone (str), brand dict or None
- output: refined post (<=280 chars)

The agent is defensive: if any step fails it falls back gracefully.
"""
from typing import Optional, Dict, Any


class OpenAIAgent:
    def __init__(self, ai_client):
        self.ai = ai_client

    def _shorten(self, text: str, limit: int = 280) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 1].rsplit(" ", 1)[0] + "…"

    def _moderation_check(self, text: str, banned: list) -> Dict[str, Any]:
        """Lightweight moderation: looks for banned words and promo keywords."""
        issues = []
        low = text.lower()
        for b in (banned or []):
            if b and b.lower() in low:
                issues.append(f"banned:{b}")
        # promo keywords
        PROMO = ["discount", "sale", "promo", "coupon", "deal", "free", "save"]
        for p in PROMO:
            if p in low:
                issues.append(f"promo:{p}")
        return {"ok": len(issues) == 0, "issues": issues}

    def generate_post(self, topic: str, tone: str = "friendly", brand: Optional[dict] = None) -> Dict[str, Any]:
        """Return structured output with variants, final, hashtags, alt_text, and moderation result."""
        def build_prompt(stage: str, data: str) -> str:
            prompt = f"Stage: {stage}\nTopic: {topic}\nTone: {tone}\n"
            if brand:
                kw = brand.get("keywords") or []
                banned = brand.get("banned") or []
                if kw:
                    prompt += "Brand keywords: " + ", ".join(kw) + "\n"
                if banned:
                    prompt += "Banned words: " + ", ".join(banned) + "\n"
            prompt += "\n" + data
            return prompt

        variants = []
        # Draft stage: generate 3 variants (try/except for robustness)
        try:
            draft_prompt = (
                "Generate 3 distinct short social media post variants, labeled 1/2/3. "
                "Each <=280 chars, avoid promotional language. Return only the posts, each on its own line."
            )
            raw = self.ai.generate_text(prompt=build_prompt("draft", draft_prompt), max_tokens=300, temperature=0.8)
            if raw and raw.strip():
                # naive splitting: lines or numbered list
                lines = [l.strip() for l in raw.splitlines() if l.strip()]
                if len(lines) >= 3:
                    variants = lines[:3]
                else:
                    # try comma split as fallback
                    parts = [p.strip() for p in raw.split("\n") if p.strip()]
                    variants = parts[:3] if parts else [raw.strip()]
        except Exception:
            variants = []

        if not variants:
            try:
                raw = self.ai.generate_text(prompt=build_prompt("draft", "Generate 1 short social post."), max_tokens=120, temperature=0.7)
                variants = [raw.strip()] if raw and raw.strip() else [f"Thoughts on {topic}?"]
            except Exception:
                variants = [f"Thoughts on {topic}?"]

        # Critique + score each variant
        scored = []
        for v in variants:
            try:
                critique_prompt = (
                    "Critique the post for tone, banned words, promotional language, emoji use, and length. "
                    "Give a one-line numeric score 0-10 and a short suggestion.\nPost:\n" + v
                )
                critique = self.ai.generate_text(prompt=build_prompt("critique", critique_prompt), max_tokens=120, temperature=0.2)
                # parse numeric score
                import re

                m = re.search(r"(\d{1,2})", critique or "")
                score = int(m.group(1)) if m else 5
                scored.append((score, v, critique))
            except Exception:
                scored.append((5, v, ""))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[0][1]

        # Refine top
        final = None
        try:
            refine_prompt = (
                "Refine the following post to address the critique and improve clarity and engagement. Return only the final post <=280 chars.\n\n"
                f"Post:\n{top}\n\nCritique:\n{scored[0][2]}"
            )
            final = self.ai.generate_text(prompt=build_prompt("refine", refine_prompt), max_tokens=150, temperature=0.6)
            final = final.strip() if final else None
        except Exception:
            final = None

        chosen = final or top

        # Hashtags — ask the model for 3-6 relevant hashtags
        hashtags = []
        try:
            hs = self.ai.generate_text(prompt=build_prompt("hashtags", "Suggest 3-6 relevant hashtags (comma separated)."), max_tokens=60, temperature=0.4)
            if hs:
                tags = [t.strip() for t in hs.replace('#','').replace(';',',').split(',') if t.strip()]
                hashtags = [('#' + t) if not t.startswith('#') else t for t in tags][:6]
        except Exception:
            hashtags = []

        # Alt text — short image description
        alt_text = None
        try:
            at = self.ai.generate_text(prompt=build_prompt("alt_text", "Write a concise alt text (one sentence) for an image representing the topic."), max_tokens=60, temperature=0.2)
            alt_text = at.strip() if at else None
        except Exception:
            alt_text = None

        # moderation: prefer API-based moderation if AIClient exposes moderate_text
        banned = (brand.get("banned") if brand else [])
        mod = None
        try:
            if hasattr(self.ai, "moderate_text"):
                try:
                    mod = self.ai.moderate_text(chosen)
                except Exception:
                    mod = None
        except Exception:
            mod = None

        if not mod:
            mod = self._moderation_check(chosen, banned)

        return {
            'variants': variants,
            'final': self._shorten(chosen),
            'hashtags': hashtags,
            'alt_text': alt_text,
            'moderation': mod,
        }
