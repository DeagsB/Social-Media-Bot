import os, traceback, sys

# Ensure repo root is on sys.path when running from scripts/
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

from storage import get_setting

print('ENV OPENAI_API_KEY =', bool(os.getenv('OPENAI_API_KEY')))
print('STORED OPENAI_API_KEY =', bool(get_setting('OPENAI_API_KEY')))

try:
    from ai_client import AIClient
    print('Imported AIClient, attempting to instantiate...')
    c = AIClient()
    print('AIClient instantiated. client_type=', getattr(c, '_client_type', None))
    # try a lightweight call if possible
    try:
        out = c.generate_text('Say hi', max_tokens=5, temperature=0.2)
        print('generate_text succeeded (len):', len(out) if out is not None else None)
    except Exception as e:
        print('generate_text failed:', type(e).__name__, e)
        traceback.print_exc()
except Exception as e:
    print('AIClient import/instantiation error:', type(e).__name__, e)
    traceback.print_exc()
