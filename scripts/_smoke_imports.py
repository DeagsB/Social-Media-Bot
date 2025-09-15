import importlib
import os
import sys

# Ensure the repository root (parent of this scripts/ folder) is on sys.path so
# top-level modules (e.g. ai_client.py) can be imported when this script is run
# from the scripts directory.
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

mods = ["openai_agent", "generator", "ai_client"]
for m in mods:
    try:
        importlib.import_module(m)
        print("OK", m)
    except Exception as e:
        print("ERR", m, e)
