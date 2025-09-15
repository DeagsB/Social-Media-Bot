import os
import json
from typing import Optional
import requests
from storage import get_setting


class FacebookConnector:
    """Connector for Facebook / Meta Graph API.

    This implementation supports a dry-run mode (no network request) for testing.
    To enable real posting set environment variables:
      - FB_PAGE_ID
      - FB_ACCESS_TOKEN

    Note: You must follow Meta's API docs and ensure your token has the 'pages_manage_posts' and
    'pages_read_engagement' scopes as required by your app.
    """

    GRAPH_API_URL = "https://graph.facebook.com/v17.0"

    def __init__(self, page_id: Optional[str] = None, access_token: Optional[str] = None, dry_run: bool = True):
        # try settings storage if env vars not set
        page = page_id if page_id is not None else os.getenv("FB_PAGE_ID")
        if page is None:
            page = get_setting("FB_PAGE_ID")
        token = access_token if access_token is not None else os.getenv("FB_ACCESS_TOKEN")
        if token is None:
            token = get_setting("FB_ACCESS_TOKEN")
        self.page_id = page
        self.access_token = token
        self.dry_run = bool(dry_run)

    def post(self, message: str, image_path: str = None) -> dict:
        if self.dry_run:
            # Simulate a successful post response
            return {"status": "dry_run", "message": message, "image": image_path}

        if not self.page_id or not self.access_token:
            raise RuntimeError("FB_PAGE_ID and FB_ACCESS_TOKEN must be set for real posting")

        url = f"{self.GRAPH_API_URL}/{self.page_id}/feed"
        payload = {"message": message, "access_token": self.access_token}
        files = None
        if image_path:
            # If the Graph API requires multipart upload use 'source' instead (not implemented here)
            files = {"source": open(image_path, "rb")}

        resp = requests.post(url, data=payload, files=files, timeout=30)
        if files:
            files["source"].close()
        resp.raise_for_status()
        return resp.json()
