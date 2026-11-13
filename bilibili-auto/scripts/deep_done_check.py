"""Return exit 0 when every Bilibili deep-collect account is finished.

Used by collect_run.cmd to skip the scheduled chunk once collection is done.
Exit 1 means "not finished / unknown -> continue collecting".
Pure ASCII source on purpose: it is invoked from a .cmd with a non-UTF8 codepage.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
STATE = os.path.join(ROOT, "1AMdata", "_state", "deep_collect.json")

try:
    with open(STATE, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    accounts = list((data.get("accounts") or {}).values())
    if not accounts:
        sys.exit(1)
    pending = [
        a for a in accounts
        if a.get("stage") not in ("finished", "error")
    ]
    sys.exit(0 if not pending else 1)
except Exception:
    sys.exit(1)
