import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
from generator import PostGenerator, BrandProfile
from scheduler import Scheduler
import csv
import os
import threading
import time

from PIL import Image, ImageTk
from tkinter import simpledialog

# connectors
from connectors import StubConnector, FacebookConnector
import storage
import image_utils

APP_TITLE = "Social Media Post Generator"


class App:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("820x680")

        # ensure DB/tables exist
        storage.init_db()

        self.generator = PostGenerator()
        self.scheduler = Scheduler()

        # Topic input
        tk.Label(self.root, text="Topic / Focus:").pack(anchor="w", padx=8, pady=(8, 0))
        self.topic_entry = tk.Entry(self.root)
        self.topic_entry.pack(fill="x", padx=8)

        # Tone
        tk.Label(self.root, text="Tone (casual, professional, friendly):").pack(anchor="w", padx=8, pady=(8, 0))
        self.tone_entry = tk.Entry(self.root)
        self.tone_entry.pack(fill="x", padx=8)

        # Generate button
        tk.Button(self.root, text="Generate Post", command=self.generate_post).pack(pady=10)

        # Post preview
        tk.Label(self.root, text="Post Preview:").pack(anchor="w", padx=8)
        self.preview = scrolledtext.ScrolledText(self.root, height=8)
        self.preview.pack(fill="both", expand=False, padx=8, pady=(0, 8))

        # Image options
        img_frame = tk.Frame(self.root)
        img_frame.pack(fill="x", padx=8)
        tk.Label(img_frame, text="Image option:").pack(side="left")
        self.img_option = tk.StringVar(value="none")
        tk.Radiobutton(img_frame, text="None", variable=self.img_option, value="none").pack(side="left")
        tk.Radiobutton(img_frame, text="Upload", variable=self.img_option, value="upload").pack(side="left")
        tk.Radiobutton(img_frame, text="From URL", variable=self.img_option, value="url").pack(side="left")
        tk.Radiobutton(img_frame, text="AI-generate", variable=self.img_option, value="ai").pack(side="left")
        tk.Button(img_frame, text="Select / Generate Image", command=self.handle_image_choice).pack(side="left", padx=8)
        self.selected_image_path = None
        self.selected_image_label = tk.Label(img_frame, text="No image selected")
        self.selected_image_label.pack(side="left", padx=8)

        # Actions frame
        frame = tk.Frame(self.root)
        frame.pack(fill="x", padx=8, pady=(8, 8))
        tk.Button(frame, text="Save Draft", command=self.save_draft).pack(side="left")
        tk.Button(frame, text="Export CSV", command=self.export_csv).pack(side="left", padx=6)
        tk.Button(frame, text="Schedule Post", command=self.schedule_post).pack(side="left")
        tk.Button(frame, text="Preview & Post", command=self.preview_and_post).pack(side="left", padx=6)
        tk.Button(frame, text="Quit", command=self.root.quit).pack(side="right")

        # Connector selection and dry-run toggle
        conn_frame = tk.Frame(self.root)
        conn_frame.pack(fill="x", padx=8, pady=(0, 8))
        tk.Label(conn_frame, text="Connector:").pack(side="left")
        self.connector_var = tk.StringVar(value="Stub")
        tk.OptionMenu(conn_frame, self.connector_var, "Stub", "Facebook").pack(side="left")
        self.dry_run_var = tk.BooleanVar(value=True)
        tk.Checkbutton(conn_frame, text="Dry run (no network)", variable=self.dry_run_var).pack(side="left", padx=8)
        tk.Button(conn_frame, text="Settings", command=self.open_settings).pack(side="right")
        tk.Button(conn_frame, text="Image Library", command=self.open_image_library).pack(side="right", padx=8)

        # start a background poller for scheduled posts
        self._stop_poller = False
        t = threading.Thread(target=self._poll_scheduled_loop, daemon=True)
        t.start()

    def generate_post(self):
        topic = self.topic_entry.get().strip()
        tone = self.tone_entry.get().strip() or "friendly"
        if not topic:
            messagebox.showwarning("Missing topic", "Please enter a topic or focus for the post.")
            return
        # load brand profile from storage
        brand_raw = storage.get_setting("BRAND_PROFILE")
        brand = None
        if brand_raw:
            try:
                import json

                j = json.loads(brand_raw)
                brand = BrandProfile(name=j.get("name", ""), keywords=j.get("keywords", []), banned=j.get("banned", []))
            except Exception:
                brand = None

        post = self.generator.generate(topic=topic, tone=tone, brand=brand)
        self.preview.delete("1.0", tk.END)
        self.preview.insert(tk.END, post)

    def save_draft(self):
        content = self.preview.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("Empty", "Nothing to save. Generate a post first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text", "*.txt")])
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Saved", f"Draft saved to {path}")

    def export_csv(self):
        content = self.preview.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("Empty", "Nothing to export. Generate a post first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            with open(path, "w", newline='', encoding="utf-8") as csvfile:
                writer = csv.writer(csvfile)
                writer.writerow(["post"])
                writer.writerow([content])
            messagebox.showinfo("Exported", f"CSV exported to {path}")

    def schedule_post(self):
        content = self.preview.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("Empty", "Nothing to schedule. Generate a post first.")
            return
        # Simple local scheduler: schedule now or in N seconds
        def on_schedule():
            seconds = simpledialog.getinteger("Delay seconds", "Post delay in seconds (0 for immediate):", minvalue=0)
            if seconds is None:
                return
            run_at = int(time.time()) + int(seconds)
            storage.add_scheduled_post(content, run_at)
            messagebox.showinfo("Scheduled", f"Post scheduled in {seconds} seconds.")

        # Import here to keep top-level simple
        from tkinter import simpledialog
        on_schedule()

    def handle_image_choice(self):
        opt = self.img_option.get()
        if opt == "none":
            self.selected_image_path = None
            self.selected_image_label.config(text="No image selected")
            return
        if opt == "upload":
            path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")])
            if path:
                self.selected_image_path = path
                self.selected_image_label.config(text=os.path.basename(path))
            return
        if opt == "url":
            url = simpledialog.askstring("Image URL", "Enter image URL:")
            if not url:
                return
            out = os.path.join(os.getcwd(), ".tmp_image.jpg")
            try:
                image_utils.download_image(url, out)
                self.selected_image_path = out
                self.selected_image_label.config(text=os.path.basename(out))
            except Exception as e:
                messagebox.showerror("Download failed", str(e))
            return
        if opt == "ai":
            prompt = simpledialog.askstring("AI image text", "Enter short text for image generation (brand/phrase):")
            if not prompt:
                return
            out = os.path.join(os.getcwd(), ".tmp_image_ai.jpg")
            try:
                # if AI enabled in settings, use ai_client to generate a real image
                try:
                    from storage import get_setting

                    if get_setting("ENABLE_AI") == "1":
                        from ai_client import AIClient

                        client = AIClient()
                        client.generate_image(prompt, out, size="1024x1024")
                    else:
                        image_utils.generate_placeholder_image(prompt, out)
                except Exception:
                    image_utils.generate_placeholder_image(prompt, out)
                self.selected_image_path = out
                self.selected_image_label.config(text=os.path.basename(out))
            except Exception as e:
                messagebox.showerror("Generate failed", str(e))

    def preview_and_post(self):
        content = self.preview.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("Empty", "Nothing to post. Generate a post first.")
            return
        # show confirmation dialog with image preview (if any)
        self._show_confirmation(content, self.selected_image_path)

    def _show_confirmation(self, content: str, image_path: str = None):
        win = tk.Toplevel(self.root)
        win.title("Confirm Post")
        win.geometry("640x480")
        tk.Label(win, text="Post preview:").pack(anchor="w", padx=8, pady=(8, 0))
        text = tk.Text(win, height=6, wrap="word")
        text.insert("1.0", content)
        text.configure(state="disabled")
        text.pack(fill="x", padx=8)

        img_label = None
        photo = None
        if image_path and os.path.exists(image_path):
            try:
                img = Image.open(image_path)
                img.thumbnail((560, 300))
                photo = ImageTk.PhotoImage(img)
                img_label = tk.Label(win, image=photo)
                img_label.image = photo
                img_label.pack(padx=8, pady=8)
            except Exception:
                tk.Label(win, text="(Could not open image)").pack()

        def do_confirm():
            win.destroy()
            self._post_confirmed(content, image_path)

        def do_cancel():
            win.destroy()

        btns = tk.Frame(win)
        btns.pack(pady=8)
        tk.Button(btns, text="Confirm and Post", command=do_confirm).pack(side="left", padx=8)
        tk.Button(btns, text="Cancel", command=do_cancel).pack(side="left")

    def _post_confirmed(self, content: str, image_path: str = None):
        connector_name = self.connector_var.get()
        dry = self.dry_run_var.get()

        def do_post():
            try:
                if connector_name == "Facebook":
                    conn = FacebookConnector(dry_run=dry)
                else:
                    conn = StubConnector()

                res = conn.post(content, image_path=image_path)
                self.root.after(0, lambda: messagebox.showinfo("Posted", f"Result: {res}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Post failed", str(e)))

        t = threading.Thread(target=do_post, daemon=True)
        t.start()

    def open_settings(self):
        win = tk.Toplevel(self.root)
        win.title("Settings")
        win.geometry("500x300")

        # Brand profile
        tk.Label(win, text="Brand name:").pack(anchor="w", padx=8, pady=(8, 0))
        name_ent = tk.Entry(win)
        name_ent.pack(fill="x", padx=8)
        tk.Label(win, text="Brand keywords (comma separated):").pack(anchor="w", padx=8, pady=(8, 0))
        kw_ent = tk.Entry(win)
        kw_ent.pack(fill="x", padx=8)
        tk.Label(win, text="Brand banned words (comma separated):").pack(anchor="w", padx=8, pady=(8, 0))
        banned_ent = tk.Entry(win)
        banned_ent.pack(fill="x", padx=8)

        # Facebook creds
        tk.Label(win, text="Facebook Page ID:").pack(anchor="w", padx=8, pady=(8, 0))
        fb_page = tk.Entry(win)
        fb_page.pack(fill="x", padx=8)
        tk.Label(win, text="Facebook Page Access Token:").pack(anchor="w", padx=8, pady=(8, 0))
        fb_token = tk.Entry(win)
        fb_token.pack(fill="x", padx=8)
        tk.Label(win, text="OpenAI API Key (optional):").pack(anchor="w", padx=8, pady=(8, 0))
        openai_key = tk.Entry(win)
        openai_key.pack(fill="x", padx=8)
        tk.Label(win, text="Hugging Face API Token (optional):").pack(anchor="w", padx=8, pady=(8, 0))
        hf_key = tk.Entry(win)
        hf_key.pack(fill="x", padx=8)
        tk.Label(win, text="Enable ChatGPT generation:").pack(anchor="w", padx=8, pady=(8, 0))
        enable_ai = tk.BooleanVar(value=False)
        tk.Checkbutton(win, text="Enable AI (ChatGPT) generation", variable=enable_ai).pack(anchor="w", padx=8)

        # load existing
        try:
            import json

            bp = storage.get_setting("BRAND_PROFILE")
            if bp:
                j = json.loads(bp)
                name_ent.insert(0, j.get("name", ""))
                kw_ent.insert(0, ",".join(j.get("keywords", [])))
                banned_ent.insert(0, ",".join(j.get("banned", [])))
        except Exception:
            pass
        fb_page.insert(0, storage.get_setting("FB_PAGE_ID") or "")
        fb_token.insert(0, storage.get_setting("FB_ACCESS_TOKEN") or "")
        openai_key.insert(0, storage.get_setting("OPENAI_API_KEY") or "")
        hf_key.insert(0, storage.get_setting("HF_API_TOKEN") or "")
        try:
            enable_ai.set(storage.get_setting("ENABLE_AI") == "1")
        except Exception:
            enable_ai.set(False)

        def save():
            import json

            j = {
                "name": name_ent.get().strip(),
                "keywords": [k.strip() for k in kw_ent.get().split(",") if k.strip()],
                "banned": [b.strip() for b in banned_ent.get().split(",") if b.strip()],
            }
            storage.set_setting("BRAND_PROFILE", json.dumps(j))
            storage.set_setting("FB_PAGE_ID", fb_page.get().strip())
            storage.set_setting("FB_ACCESS_TOKEN", fb_token.get().strip())
            storage.set_setting("OPENAI_API_KEY", openai_key.get().strip())
            storage.set_setting("HF_API_TOKEN", hf_key.get().strip())
            storage.set_setting("ENABLE_AI", "1" if enable_ai.get() else "0")
            messagebox.showinfo("Saved", "Settings saved")

        tk.Button(win, text="Save", command=save).pack(pady=12)

    def open_image_library(self):
        # ensure DB
        try:
            import image_db

            image_db.init_db()
        except Exception:
            messagebox.showerror("Error", "Could not initialize image DB")
            return

        win = tk.Toplevel(self.root)
        win.title("Image Library")
        win.geometry("700x500")

        listbox = tk.Listbox(win)
        listbox.pack(fill="both", expand=True, padx=8, pady=8)

        def refresh_list():
            listbox.delete(0, tk.END)
            for img in image_db.list_images():
                listbox.insert(tk.END, f"{img['id']}: {img['title']} ({os.path.basename(img['path'])})")

        def add_image():
            path = filedialog.askopenfilename(filetypes=[("Image files", "*.png;*.jpg;*.jpeg;*.gif;*.bmp")])
            if not path:
                return
            title = simpledialog.askstring("Title", "Enter title for image:") or ""
            desc = simpledialog.askstring("Description", "Enter description (optional):") or ""
            tags = simpledialog.askstring("Tags", "Comma separated tags (optional):") or ""
            try:
                image_db.add_image(path, title=title, description=desc, tags=[t.strip() for t in tags.split(",") if t.strip()], metadata={})
                refresh_list()
            except Exception as e:
                messagebox.showerror("Add failed", str(e))

        def view_selected():
            sel = listbox.curselection()
            if not sel:
                return
            idx = listbox.get(sel[0])
            image_id = int(idx.split(":", 1)[0])
            img = image_db.get_image(image_id)
            if not img:
                messagebox.showerror("Not found", "Image not found")
                return
            # show a simple preview window
            pv = tk.Toplevel(win)
            pv.title(img.get("title") or f"Image {image_id}")
            try:
                im = Image.open(img["path"])
                im.thumbnail((560, 360))
                photo = ImageTk.PhotoImage(im)
                l = tk.Label(pv, image=photo)
                l.image = photo
                l.pack(padx=8, pady=8)
            except Exception:
                tk.Label(pv, text="(Could not load image)").pack(padx=8, pady=8)
            tk.Label(pv, text=f"Title: {img.get('title')}").pack(anchor="w", padx=8)
            tk.Label(pv, text=f"Description: {img.get('description')}").pack(anchor="w", padx=8)
            tk.Label(pv, text=f"Tags: {', '.join(img.get('tags', []))}").pack(anchor="w", padx=8)

        def generate_from_selected():
            sel = listbox.curselection()
            if not sel:
                messagebox.showinfo("Select image", "Please select an image first")
                return
            idx = listbox.get(sel[0])
            image_id = int(idx.split(":", 1)[0])
            img = image_db.get_image(image_id)
            if not img:
                messagebox.showerror("Not found", "Image not found")
                return
            # build brand profile from storage
            brand_raw = storage.get_setting("BRAND_PROFILE")
            brand = None
            if brand_raw:
                try:
                    import json

                    j = json.loads(brand_raw)
                    brand = BrandProfile(name=j.get("name", ""), keywords=j.get("keywords", []), banned=j.get("banned", []))
                except Exception:
                    brand = None
            post = self.generator.generate_from_image(img, tone="friendly", brand=brand)
            # insert into main preview
            self.preview.delete("1.0", tk.END)
            self.preview.insert(tk.END, post)

        def find_similar():
            sel = listbox.curselection()
            if not sel:
                messagebox.showinfo("Select image", "Please select an image first")
                return
            idx = listbox.get(sel[0])
            image_id = int(idx.split(":", 1)[0])
            src = image_db.get_image(image_id)
            if not src:
                messagebox.showerror("Not found", "Image not found")
                return
            # simple similarity: compare average color distance and size
            def color_dist(a, b):
                if not a or not b:
                    return float("inf")
                return sum((a[i] - b[i]) ** 2 for i in range(3)) ** 0.5

            candidates = []
            for img in image_db.list_images():
                if img["id"] == image_id:
                    continue
                a = src.get("metadata", {}).get("avg_color")
                b = img.get("metadata", {}).get("avg_color")
                d = color_dist(a, b)
                # also size diff
                sw = src.get("metadata", {}).get("width") or 0
                sh = src.get("metadata", {}).get("height") or 0
                iw = img.get("metadata", {}).get("width") or 0
                ih = img.get("metadata", {}).get("height") or 0
                size_diff = abs(sw - iw) + abs(sh - ih)
                score = d + (size_diff / 100.0)
                candidates.append((score, img))
            candidates.sort(key=lambda x: x[0])
            # show top 5
            if not candidates:
                messagebox.showinfo("No matches", "No other images to compare")
                return
            out = "Similar images:\n" + "\n".join([f"{c[1]['id']}: {c[1]['title']} ({os.path.basename(c[1]['path'])})" for c in candidates[:5]])
            messagebox.showinfo("Search results", out)

        def caption_selected():
            sel = listbox.curselection()
            if not sel:
                messagebox.showinfo("Select image", "Please select an image first")
                return
            idx = listbox.get(sel[0])
            image_id = int(idx.split(":", 1)[0])
            img = image_db.get_image(image_id)
            if not img:
                messagebox.showerror("Not found", "Image not found")
                return
            try:
                import vision

                caption = vision.caption_image(img["path"])
                if not caption:
                    messagebox.showinfo("Caption", "No caption available (missing model or failed).")
                    return
                # save caption as description
                image_db.update_image(image_id, description=caption)
                messagebox.showinfo("Saved", "Caption saved to image description")
                refresh_list()
            except Exception as e:
                messagebox.showerror("Caption failed", str(e))

        btns = tk.Frame(win)
        btns.pack(fill="x", padx=8, pady=(0, 8))
        tk.Button(btns, text="Add Image", command=add_image).pack(side="left")
        tk.Button(btns, text="View Selected", command=view_selected).pack(side="left", padx=8)
        tk.Button(btns, text="Generate Post", command=generate_from_selected).pack(side="left", padx=8)
        tk.Button(btns, text="Caption", command=caption_selected).pack(side="left", padx=8)
        tk.Button(btns, text="Find Similar", command=find_similar).pack(side="left", padx=8)
        tk.Button(btns, text="Refresh", command=refresh_list).pack(side="right")

        refresh_list()

    def _poll_scheduled_loop(self):
        # simple poll loop that runs every 30 seconds
        while not getattr(self, "_stop_poller", False):
            now = int(time.time())
            try:
                rows = storage.list_scheduled()
                for r in rows:
                    if r["status"] != "pending":
                        continue
                    if r["run_at"] <= now:
                        # perform post
                        content = r["content"]
                        try:
                            conn = FacebookConnector(dry_run=True)
                            # use stored page/token; respect dry_run true to avoid accidental posting
                            res = conn.post(content)
                            storage.mark_scheduled_sent(r["id"])
                        except Exception:
                            # leave as pending for retry
                            pass
            except Exception:
                pass
            time.sleep(30)


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
