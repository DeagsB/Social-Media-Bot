import unittest
from generator import PostGenerator


class TestGenerator(unittest.TestCase):
    def test_generate_basic(self):
        g = PostGenerator()
        post = g.generate("social media marketing", tone="friendly")
        self.assertIsInstance(post, str)
        self.assertTrue(len(post) > 0)
        # ensure no promo words
        for w in ["discount", "sale", "promo", "free"]:
            self.assertNotIn(w, post.lower())


if __name__ == "__main__":
    unittest.main()
