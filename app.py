import tkinter as tk
from tkinter import scrolledtext, messagebox, filedialog
from generator import PostGenerator, BrandProfile
from scheduler import Scheduler
import csv
import os
import threading
import time
import requests

from PIL import Image, ImageTk
from tkinter import simpledialog
from tkinter import ttk
import tkinter.font as tkfont

# --- Modern styling setup -------------------------------------------------
# Configure a clean ttk theme and default fonts/colors.
_style = ttk.Style()
try:
    _style.theme_use("clam")
except Exception:
    pass

# choose an Apple-like font when available, otherwise fall back
_candidates = ["SF Pro Text", "Helvetica Neue", "Helvetica", "Segoe UI", "Arial"]
try:
    _families = set(tkfont.families())
except Exception:
    _families = set()
_FONT_FAMILY = next((f for f in _candidates if f in _families), "TkDefaultFont")
FONT_BODY = tkfont.Font(family=_FONT_FAMILY, size=11)
FONT_TITLE = tkfont.Font(family=_FONT_FAMILY, size=13, weight="bold")

# color palette
_BG = "#F5F7FA"
_CARD = "#FFFFFF"
_ACCENT = "#007AFF"  # iOS blue
_TEXT = "#111827"

_style.configure("TButton", font=FONT_BODY, foreground=_ACCENT, padding=6)
_style.configure("TLabel", font=FONT_BODY, foreground=_TEXT, background=_BG)
_style.configure("TEntry", font=FONT_BODY)
_style.configure("Card.TFrame", background=_CARD)
# -------------------------------------------------------------------------

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
        ttk.Label(self.root, text="Topic / Focus:").pack(anchor="w", padx=8, pady=(8, 0))
        self.topic_entry = ttk.Entry(self.root)
        self.topic_entry.pack(fill="x", padx=8)

        # Tone
        ttk.Label(self.root, text="Tone (casual, professional, friendly):").pack(anchor="w", padx=8, pady=(8, 0))
        self.tone_entry = ttk.Entry(self.root)
        self.tone_entry.pack(fill="x", padx=8)

        # Generate button
        ttk.Button(self.root, text="Generate Post", command=self.generate_post).pack(pady=10)

        # Post preview
        ttk.Label(self.root, text="Post Preview:").pack(anchor="w", padx=8)
        self.preview = scrolledtext.ScrolledText(self.root, height=8)
        self.preview.pack(fill="both", expand=False, padx=8, pady=(0, 8))

        # Inline image suggestions container (populated asynchronously)
        self.img_suggestions_frame = ttk.Frame(self.root, style="Card.TFrame")
        self.img_suggestions_frame.pack(fill="both", expand=False, padx=8, pady=(0, 8))

        # Image options
        img_frame = ttk.Frame(self.root, style="Card.TFrame")
        img_frame.pack(fill="x", padx=8)
        ttk.Label(img_frame, text="Image option:").pack(side="left")
        self.img_option = tk.StringVar(value="none")
        # use standard tk.Radiobutton because ttk.Radiobutton has different styling
        tk.Radiobutton(img_frame, text="None", variable=self.img_option, value="none").pack(side="left")
        tk.Radiobutton(img_frame, text="Upload", variable=self.img_option, value="upload").pack(side="left")
        tk.Radiobutton(img_frame, text="From URL", variable=self.img_option, value="url").pack(side="left")
        tk.Radiobutton(img_frame, text="AI-generate", variable=self.img_option, value="ai").pack(side="left")
        ttk.Button(img_frame, text="Select / Generate Image", command=self.handle_image_choice).pack(side="left", padx=8)
        self.selected_image_path = None
        self.selected_image_label = ttk.Label(img_frame, text="No image selected")
        self.selected_image_label.pack(side="left", padx=8)

        # Actions frame
        frame = ttk.Frame(self.root, style="Card.TFrame")
        frame.pack(fill="x", padx=8, pady=(8, 8))
        ttk.Button(frame, text="Image Suggestions", command=self.open_image_suggestions).pack(side="left", padx=6)
        ttk.Button(frame, text="Save Draft", command=self.save_draft).pack(side="left")
        ttk.Button(frame, text="Export CSV", command=self.export_csv).pack(side="left", padx=6)
        ttk.Button(frame, text="Schedule Post", command=self.schedule_post).pack(side="left")
        ttk.Button(frame, text="Preview & Post", command=self.preview_and_post).pack(side="left", padx=6)
        ttk.Button(frame, text="Toggle Logs", command=self.toggle_logs).pack(side="left", padx=6)
        ttk.Button(frame, text="Quit", command=self.root.quit).pack(side="right")

        # Connector selection and dry-run toggle
        conn_frame = ttk.Frame(self.root, style="Card.TFrame")
        conn_frame.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Label(conn_frame, text="Connector:").pack(side="left")
        self.connector_var = tk.StringVar(value="Stub")
        # OptionMenu remains tk for simplicity
        tk.OptionMenu(conn_frame, self.connector_var, "Stub", "Facebook").pack(side="left")
        self.dry_run_var = tk.BooleanVar(value=True)
        tk.Checkbutton(conn_frame, text="Dry run (no network)", variable=self.dry_run_var).pack(side="left", padx=8)
        ttk.Button(conn_frame, text="Settings", command=self.open_settings).pack(side="right")
        ttk.Button(conn_frame, text="Image Library", command=self.open_image_library).pack(side="right", padx=8)

        # start a background poller for scheduled posts
        self._stop_poller = False
        t = threading.Thread(target=self._poll_scheduled_loop, daemon=True)
        t.start()

        # status bar and progress
        self.status_var = tk.StringVar(value="")
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill="x", side="bottom")
        self.status_label = ttk.Label(status_frame, textvariable=self.status_var, anchor="w")
        self.status_label.pack(side="left", padx=8)
        self.progress = ttk.Progressbar(status_frame, mode="indeterminate")
        # initially hidden

    def show_progress(self, text: str = ""):
        try:
            self.status_var.set(text)
            # pack progress to the right side
            self.progress.pack(side="right", padx=8)
            self.progress.start(10)
        except Exception:
            pass

    def hide_progress(self):
        try:
            self.progress.stop()
            self.progress.pack_forget()
            self.status_var.set("")
        except Exception:
            pass

    # --- Logging / visible error area ----------------------------------
    def _ensure_log_frame(self):
        if hasattr(self, '_log_ready') and self._log_ready:
            return
        self.log_frame = ttk.Frame(self.root)
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=8, state='disabled')
        self.log_text.pack(fill='both', expand=True, padx=6, pady=6)
        # ensure debug dir
        try:
            os.makedirs('.ai_debug', exist_ok=True)
        except Exception:
            pass
        self._log_ready = True
        self.log_visible = False

    def toggle_logs(self):
        self._ensure_log_frame()
        if getattr(self, 'log_visible', False):
            try:
                self.log_frame.pack_forget()
            except Exception:
                pass
            self.log_visible = False
        else:
            # pack logs above the status bar
            try:
                self.log_frame.pack(fill='both', side='bottom', padx=6, pady=(0,0))
            except Exception:
                pass
            self.log_visible = True

    def append_log(self, msg: str, level: str = 'INFO'):
        ts = time.strftime('%Y-%m-%d %H:%M:%S')
        line = f"[{ts}] {level}: {msg}\n"
        # UI update on main thread
        def write():
            try:
                self._ensure_log_frame()
                self.log_text['state'] = 'normal'
                self.log_text.insert('end', line)
                self.log_text.see('end')
                self.log_text['state'] = 'disabled'
            except Exception:
                pass
        try:
            self.root.after(0, write)
        except Exception:
            write()
        # also persist to a file
        try:
            with open(os.path.join('.ai_debug', 'log.txt'), 'a', encoding='utf-8') as f:
                f.write(line)
        except Exception:
            pass

    def append_error(self, exc: Exception, context: str = ''):
        import traceback

        tb = traceback.format_exc()
        self.append_log(f"{context} {exc}\n{tb}", level='ERROR')
    # --------------------------------------------------------------------

    def generate_post(self):
        topic = self.topic_entry.get().strip()
        tone = self.tone_entry.get().strip() or "friendly"
        if not topic:
            messagebox.showwarning("Missing topic", "Please enter a topic or focus for the post.")
            return

        # load brand profile from storage (fast)
        brand_raw = storage.get_setting("BRAND_PROFILE")
        brand = None
        if brand_raw:
            try:
                import json

                j = json.loads(brand_raw)
                brand = BrandProfile(name=j.get("name", ""), keywords=j.get("keywords", []), banned=j.get("banned", []))
            except Exception:
                brand = None

        # run generation in background to keep UI responsive
        def do_generate():
            try:
                self.show_progress("Generating post...")
                post = self.generator.generate(topic=topic, tone=tone, brand=brand)
                self.root.after(0, lambda: (self.preview.delete("1.0", tk.END), self.preview.insert(tk.END, post)))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Generate failed", str(e)))
            finally:
                self.root.after(0, lambda: self.hide_progress())

        threading.Thread(target=do_generate, daemon=True).start()

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
                        try:
                            from ai_client import AIClient

                            client = AIClient()
                            client.generate_image(prompt, out, size="1024x1024")
                        except Exception:
                            image_utils.generate_placeholder_image(prompt, out)
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
        # attempt to enrich with metadata if available in background
        topic = self.topic_entry.get().strip()
        tone = self.tone_entry.get().strip() or "friendly"
        brand_raw = storage.get_setting("BRAND_PROFILE")
        brand = None
        if brand_raw:
            try:
                import json

                j = json.loads(brand_raw)
                brand = BrandProfile(name=j.get("name", ""), keywords=j.get("keywords", []), banned=j.get("banned", []))
            except Exception:
                brand = None

        def do_metadata():
            try:
                self.show_progress("Fetching metadata...")
                metadata = None
                try:
                    metadata = self.generator.generate_with_metadata(topic=topic, tone=tone, brand=brand)
                except Exception:
                    metadata = None
                self.root.after(0, lambda: self._show_confirmation(content, self.selected_image_path, metadata))
            finally:
                self.root.after(0, lambda: self.hide_progress())

        threading.Thread(target=do_metadata, daemon=True).start()

    def _show_confirmation(self, content: str, image_path: str = None, metadata: dict = None):
        win = tk.Toplevel(self.root)
        win.title("Confirm Post")
        win.geometry("640x480")
        tk.Label(win, text="Post preview:").pack(anchor="w", padx=8, pady=(8, 0))
        # If variants are provided, show a selection list so user can pick one
        selected_text = tk.StringVar(value=content)
        if metadata and metadata.get("variants"):
            var_frame = tk.Frame(win)
            var_frame.pack(fill="x", padx=8)
            tk.Label(var_frame, text="Select a variant:").pack(anchor="w")
            listbox = tk.Listbox(var_frame, height=4)
            for v in metadata.get("variants", []):
                listbox.insert(tk.END, v)
            listbox.pack(fill="x")

            def on_variant_select(evt=None):
                sel = listbox.curselection()
                if not sel:
                    return
                txt = listbox.get(sel[0])
                selected_text.set(txt)

            listbox.bind("<<ListboxSelect>>", on_variant_select)

        text = tk.Text(win, height=6, wrap="word")
        text.insert("1.0", selected_text.get())
        text.pack(fill="x", padx=8)

        # allow edits to the final text
        def apply_selected_text():
            txt = text.get("1.0", tk.END).strip()
            selected_text.set(txt)

        tk.Button(win, text="Apply Text", command=apply_selected_text).pack(padx=8, pady=(4, 0))

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

        # show metadata if present and provide editing for hashtags/alt_text
        moderation_flagged = False
        override_var = tk.BooleanVar(value=False)
        if metadata:
            try:
                if metadata.get("hashtags"):
                    tk.Label(win, text="Hashtags:").pack(anchor="w", padx=8, pady=(4, 0))
                    tags_ent = tk.Entry(win)
                    tags_ent.insert(0, " ".join(metadata.get("hashtags", [])))
                    tags_ent.pack(fill="x", padx=8)
                else:
                    tags_ent = None

                if metadata.get("alt_text"):
                    tk.Label(win, text="Alt text:").pack(anchor="w", padx=8, pady=(4, 0))
                    alt_ent = tk.Entry(win)
                    alt_ent.insert(0, str(metadata.get("alt_text")))
                    alt_ent.pack(fill="x", padx=8)
                else:
                    alt_ent = None

                # moderation: handle both API-based moderation dicts and the legacy `ok`/`issues` shape
                mod = metadata.get("moderation") or {}
                # normalize
                mod_ok = mod.get("ok") if isinstance(mod, dict) and "ok" in mod else not bool(mod.get("flagged") if isinstance(mod, dict) else False)
                if not mod_ok:
                    moderation_flagged = True
                    issues = mod.get("issues") or (list(mod.get("categories", {}).keys()) if isinstance(mod.get("categories"), dict) else [])
                    tk.Label(win, text="Moderation issues: " + ", ".join(issues), fg="red").pack(anchor="w", padx=8, pady=(4, 0))
                    tk.Label(win, text="Check to override and allow posting:").pack(anchor="w", padx=8, pady=(2, 0))
                    tk.Checkbutton(win, text="Override moderation (I accept responsibility)", variable=override_var).pack(anchor="w", padx=8)
            except Exception:
                tags_ent = None
                alt_ent = None

        def do_confirm():
            # collect final text and metadata edits
            final_text = selected_text.get()
            try:
                final_text = text.get("1.0", tk.END).strip()
            except Exception:
                pass

            final_hashtags = None
            final_alt = None
            try:
                if 'tags_ent' in locals() and tags_ent:
                    final_hashtags = [h.strip() for h in tags_ent.get().split() if h.strip()]
                if 'alt_ent' in locals() and alt_ent:
                    final_alt = alt_ent.get().strip()
            except Exception:
                pass

            # enforce moderation unless overridden
            if moderation_flagged and not override_var.get():
                messagebox.showwarning("Moderation", "This content was flagged by moderation. Check override to proceed.")
                return

            win.destroy()
            self._post_confirmed(final_text, image_path, alt_text=final_alt, hashtags=final_hashtags)

        def do_cancel():
            win.destroy()

        btns = tk.Frame(win)
        btns.pack(pady=8)
        tk.Button(btns, text="Confirm and Post", command=do_confirm).pack(side="left", padx=8)
        tk.Button(btns, text="Cancel", command=do_cancel).pack(side="left")

    def _post_confirmed(self, content: str, image_path: str = None, alt_text: str = None, hashtags: list = None):
        connector_name = self.connector_var.get()
        dry = self.dry_run_var.get()

        def do_post():
            try:
                if connector_name == "Facebook":
                    conn = FacebookConnector(dry_run=dry)
                else:
                    conn = StubConnector()

                # pass alt_text and hashtags when available
                try:
                    res = conn.post(content, image_path=image_path, alt_text=alt_text, hashtags=hashtags)
                except TypeError:
                    # older connectors might not accept the args
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
        tk.Label(win, text="Unsplash Access Key (optional):").pack(anchor="w", padx=8, pady=(8, 0))
        unsplash_key = tk.Entry(win)
        unsplash_key.pack(fill="x", padx=8)
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
        unsplash_key.insert(0, storage.get_setting("UNSPLASH_ACCESS_KEY") or "")
        # no HF settings
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
            storage.set_setting("UNSPLASH_ACCESS_KEY", unsplash_key.get().strip())
            storage.set_setting("ENABLE_AI", "1" if enable_ai.get() else "0")
            messagebox.showinfo("Saved", "Settings saved")

        def on_test_ai():
            # run test in background to avoid blocking the settings window
            def run_test():
                try:
                    self.show_progress("Testing AI connection...")
                    try:
                        from ai_client import AIClient

                        client = AIClient()
                        resp = client.generate_text(prompt="Say OK", max_tokens=10, temperature=0.0)
                        self.root.after(0, lambda: messagebox.showinfo("AI Test Success", f"Response:\n{resp}"))
                    except Exception as e:
                        self.root.after(0, lambda: messagebox.showerror("AI Test Failed", str(e)))
                finally:
                    self.root.after(0, lambda: self.hide_progress())

            threading.Thread(target=run_test, daemon=True).start()

        ttk.Button(win, text="Test AI Connection", command=on_test_ai).pack(pady=6)
        ttk.Button(win, text="Save", command=save).pack(pady=6)

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

    def open_image_suggestions(self):
        topic = self.topic_entry.get().strip()
        tone = self.tone_entry.get().strip() or "friendly"
        if not topic:
            messagebox.showinfo("Missing topic", "Enter a topic to generate image suggestions.")
            return

        # Clear previous inline suggestions and show progress
        for child in self.img_suggestions_frame.winfo_children():
            child.destroy()
        self.show_progress("Loading image suggestions...")

        def fetch_and_render():
            try:
                # get metadata
                try:
                    brand_raw = storage.get_setting("BRAND_PROFILE")
                    brand = None
                    if brand_raw:
                        import json

                        j = json.loads(brand_raw)
                        brand = BrandProfile(name=j.get("name", ""), keywords=j.get("keywords", []), banned=j.get("banned", []))
                except Exception:
                    brand = None

                try:
                    meta = self.generator.generate_with_metadata(topic=topic, tone=tone, brand=brand)
                except Exception:
                    meta = None

                final_text = meta.get("final") if meta else topic
                alt = meta.get("alt_text") if meta else None
                tags = meta.get("hashtags") if meta else None

                # get suggestions via AI client if possible
                suggestions = []
                try:
                    from ai_client import AIClient

                    client = AIClient()
                    suggestions = self.generator.get_image_suggestions(client, post_text=final_text, alt_text=alt, hashtags=tags, n_queries=2, max_results=6)
                except Exception:
                    try:
                        import image_utils

                        suggestions = image_utils.search_images(final_text, max_results=6)
                    except Exception:
                        suggestions = []

                # render thumbnails on main thread
                def render():
                    for child in self.img_suggestions_frame.winfo_children():
                        child.destroy()
                    grid = tk.Frame(self.img_suggestions_frame)
                    grid.pack(fill="both", expand=True)

                    def on_select(url):
                        try:
                            out = os.path.join(os.getcwd(), ".tmp_image_found.jpg")
                            import image_utils

                            image_utils.download_image_to(out, url)
                            self.selected_image_path = out
                            self.selected_image_label.config(text=os.path.basename(out))
                            messagebox.showinfo("Selected", f"Image downloaded to {out}")
                        except Exception as e:
                            messagebox.showerror("Download failed", str(e))

                    for i, s in enumerate(suggestions):
                        fr = tk.Frame(grid, bd=1, relief="groove")
                        fr.grid(row=i // 3, column=i % 3, padx=6, pady=6)
                        lbl = tk.Label(fr, text="Loading...")
                        lbl.pack()
                        tk.Label(fr, text=f"Source: {s.get('source')}").pack()
                        btn = tk.Button(fr, text="Select", command=lambda url=s.get("url"): on_select(url))
                        btn.pack(pady=4)

                        # load thumbnail in background per-item
                        def load_thumb(idx, info, label):
                            try:
                                img_url = info.get("thumbnail") or info.get("url")
                                r = requests.get(img_url, stream=True, timeout=10)
                                r.raise_for_status()
                                tmp = os.path.join(os.getcwd(), f".tmp_thumb_{idx}.jpg")
                                with open(tmp, "wb") as f:
                                    for chunk in r.iter_content(2048):
                                        if chunk:
                                            f.write(chunk)
                                im = Image.open(tmp)
                                im.thumbnail((220, 140))
                                photo = ImageTk.PhotoImage(im)
                                def put_image():
                                    label.config(image=photo, text="")
                                    label.image = photo
                                self.root.after(0, put_image)
                            except Exception:
                                pass

                        threading.Thread(target=load_thumb, args=(i, s, lbl), daemon=True).start()

                self.root.after(0, render)
            finally:
                self.root.after(0, lambda: self.hide_progress())

        threading.Thread(target=fetch_and_render, daemon=True).start()

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
