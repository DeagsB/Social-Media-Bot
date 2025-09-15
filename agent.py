"""Agent orchestrator that combines Hugging Face and OpenAI clients to perform
generate -> critique -> refine loops for higher-quality social media posts.

Contract (simple):
- inputs: topic (str), brand (BrandProfile or None), tone (str)
- output: short post (<=280 chars)

The agent will:
1. Use HFClient (if available and ENABLE_HF) to generate an initial draft.
2. Use AIClient to critique the draft (identify promo words, length, tone).
3. Use HFClient or AIClient to refine the draft based on critique.

This is intentionally lightweight and defensive: if one client isn't available,
it falls back gracefully to the other or to generator templates.
"""
from typing import Optional


class Agent:
    def __init__(self, hf_client=None, ai_client=None):
        self.hf = hf_client
        self.ai = ai_client

    def _shorten(self, text: str, limit: int = 280) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 1].rsplit(" ", 1)[0] + "…"

    def generate_post(self, topic: str, tone: str = "friendly", brand: Optional[dict] = None) -> str:
        # Step 1: initial draft from HF (preferred) or AI
        draft = None
        if self.hf:
            try:
                prompt = f"Write a short social media post about: {topic}\nTone: {tone}\nDo NOT include promotions or discount language."
                if brand and brand.get("keywords"):
                    prompt += "\nUse brand keywords when appropriate: " + ", ".join(brand.get("keywords"))
                draft = self.hf.generate_text(prompt=prompt, model="gpt2", max_length=140)
            except Exception:
                draft = None

        if not draft and self.ai:
            try:
                prompt = f"Write a short social media post about: {topic}\nTone: {tone}\nDo NOT include promotions or discount language."
                if brand and brand.get("keywords"):
                    prompt += "\nUse brand keywords when appropriate: " + ", ".join(brand.get("keywords"))
                draft = self.ai.generate_text(prompt=prompt, max_tokens=120)
            except Exception:
                draft = None

        # If still missing, return a simple fallback
        if not draft:
            return self._shorten(f"Thoughts on {topic}?")

        draft = draft.strip()

        # Step 2: critique draft using whichever client is available (prefer AI for critique)
        critique = None
        critique_prompt = f"Critique this social media post for tone, banned words, and whether it contains promotional language. Return a short bulleted list of issues and suggestions.\nPost: {draft}"
        if self.ai:
            try:
                critique = self.ai.generate_text(prompt=critique_prompt, max_tokens=120)
            except Exception:
                critique = None

        if not critique and self.hf:
            try:
                critique = self.hf.generate_text(prompt=critique_prompt, model="gpt2", max_length=120)
            except Exception:
                critique = None

        # Step 3: refine using critique
        if critique:
            refine_prompt = f"Refine the following post to address these points:\n{critique}\n\nOriginal post:\n{draft}\n\nReturn only the refined post, <=280 chars."
            refined = None
            if self.hf:
                try:
                    refined = self.hf.generate_text(prompt=refine_prompt, model="gpt2", max_length=160)
                except Exception:
                    refined = None
            if not refined and self.ai:
                try:
                    refined = self.ai.generate_text(prompt=refine_prompt, max_tokens=120)
                except Exception:
                    refined = None

            if refined and refined.strip():
                return self._shorten(refined.strip())

        # No critique/refine produced better output, return shortened draft
        return self._shorten(draft)
