import os
import sqlite3
import json
from typing import List, Dict, Optional

DB_PATH = os.path.join(os.getcwd(), "image_db.sqlite3")


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            path TEXT NOT NULL,
            title TEXT,
            description TEXT,
            tags TEXT,
            metadata TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def add_image(path: str, title: str = "", description: str = "", tags: Optional[List[str]] = None, metadata: Optional[Dict] = None) -> int:
    # compute metadata if not provided
    if metadata is None:
        try:
            from image_utils import compute_image_metadata

            metadata = compute_image_metadata(path)
        except Exception:
            metadata = {}
    tags_s = ",".join(tags or [])
    meta_s = json.dumps(metadata or {})
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO images (path, title, description, tags, metadata) VALUES (?, ?, ?, ?, ?)", (path, title, description, tags_s, meta_s))
    conn.commit()
    id_ = c.lastrowid
    conn.close()
    return id_


def list_images() -> List[Dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, path, title, description, tags, metadata FROM images ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    out = []
    for r in rows:
        out.append({
            "id": r[0],
            "path": r[1],
            "title": r[2] or "",
            "description": r[3] or "",
            "tags": [t for t in (r[4] or "").split(",") if t],
            "metadata": json.loads(r[5] or "{}"),
        })
    return out


def get_image(image_id: int) -> Optional[Dict]:
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, path, title, description, tags, metadata FROM images WHERE id=?", (image_id,))
    r = c.fetchone()
    conn.close()
    if not r:
        return None
    return {
        "id": r[0],
        "path": r[1],
        "title": r[2] or "",
        "description": r[3] or "",
        "tags": [t for t in (r[4] or "").split(",") if t],
        "metadata": json.loads(r[5] or "{}"),
    }


def update_image(image_id: int, title: str = None, description: str = None, tags: Optional[List[str]] = None, metadata: Optional[Dict] = None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cur = c.execute("SELECT id, path, title, description, tags, metadata FROM images WHERE id=?", (image_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return
    path, old_title, old_description, old_tags, old_meta = row[1], row[2], row[3], row[4], row[5]
    title = title if title is not None else old_title
    description = description if description is not None else old_description
    tags_s = ",".join(tags) if tags is not None else old_tags
    meta_s = json.dumps(metadata) if metadata is not None else old_meta
    c.execute("UPDATE images SET title=?, description=?, tags=?, metadata=? WHERE id=?", (title, description, tags_s, meta_s, image_id))
    conn.commit()
    conn.close()
