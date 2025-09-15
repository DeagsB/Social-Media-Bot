"""Quick test script to verify ChatGPT availability via ai_client and stored settings.

Run with the project's venv python so it uses the same environment and storage DB:

    ./.venv/Scripts/python.exe scripts/test_ai.py

The script prints whether AI is enabled, whether an API key is stored, and attempts a small generation.
"""
import json
import traceback
import os
import sys
# ensure repo root is on sys.path so local modules can be imported when running this script
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from storage import get_setting

print("Checking settings from storage...")
enabled = get_setting("ENABLE_AI")
print("ENABLE_AI:", enabled)
key = get_setting("OPENAI_API_KEY")
print("OPENAI_API_KEY present:", bool(key))

if enabled != "1":
    print("AI is not enabled. Enable AI in the Settings UI or set ENABLE_AI to '1'.")

if not key:
    print("No OpenAI API key found in storage. You can set it in the Settings UI or export OPENAI_API_KEY in your shell.")

if enabled == "1" and key:
    print("Attempting to call AI client...")
    try:
        from ai_client import AIClient
        client = AIClient()
        prompt = "Write a 20-word friendly social post about testing ChatGPT integration for a business, without promotions."
        resp = client.generate_text(prompt, max_tokens=80)
        print("AI response:")
        print(resp)
    except Exception as e:
        print("AI call failed:")
        traceback.print_exc()
else:
    print("Skipping AI call (disabled or missing key)")
