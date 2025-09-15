class StubConnector:
    """A simple connector stub. Replace with real API client code.

    Example usage:
        c = StubConnector()
        c.post("Hello world")
    """

    def post(self, content: str, image_path: str = None) -> dict:
        # Replace this with an API call (and return value from the API).
        print(f"[StubConnector] Would post: {content}")
        if image_path:
            print(f"[StubConnector] with image: {image_path}")
        return {"status": "ok", "content": content, "image": image_path}
