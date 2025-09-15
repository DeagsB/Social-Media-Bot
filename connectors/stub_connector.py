class StubConnector:
    """A simple connector stub. Replace with real API client code.

    Example usage:
        c = StubConnector()
        c.post("Hello world")
    """

    def post(self, content: str, image_path: str = None, alt_text: str = None, hashtags: list = None) -> dict:
        # Replace this with an API call (and return value from the API).
        print(f"[StubConnector] Would post: {content}")
        if image_path:
            print(f"[StubConnector] with image: {image_path}")
        if alt_text:
            print(f"[StubConnector] alt_text: {alt_text}")
        if hashtags:
            print(f"[StubConnector] hashtags: {hashtags}")
        return {"status": "ok", "content": content, "image": image_path, "alt_text": alt_text, "hashtags": hashtags}
