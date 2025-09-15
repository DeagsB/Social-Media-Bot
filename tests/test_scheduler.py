import unittest
import time
from scheduler import Scheduler


class TestScheduler(unittest.TestCase):
    def test_schedule_immediate(self):
        s = Scheduler()
        results = []

        def cb(content):
            results.append(content)

        s.schedule_post("hello", delay_seconds=0, on_post=cb)
        # Give thread a moment
        time.sleep(0.1)
        self.assertEqual(results, ["hello"])


if __name__ == "__main__":
    unittest.main()
