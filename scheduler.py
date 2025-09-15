import threading
import time
from typing import Callable


class Scheduler:
    """Very small scheduler that runs a posting function after a delay.

    This scheduler only demonstrates local delayed execution. Connectors should
    implement actual publishing using platform APIs.
    """

    def __init__(self):
        self.jobs = []

    def schedule_post(self, content: str, delay_seconds: int = 0, on_post: Callable[[str], None] = None):
        def job():
            if delay_seconds:
                time.sleep(delay_seconds)
            # call provided callback (if any) or print to console
            if on_post:
                on_post(content)
            else:
                print(f"[Scheduled post executed] {content}")

        t = threading.Thread(target=job, daemon=True)
        t.start()
        self.jobs.append(t)
