#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""p_works.py — 只列主页作品清单，不采集。用来看清规模再定采集参数。"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from douyin_collect import list_works, PROFILE, CHROME, captcha_hit, pause  # noqa: E402

url = sys.argv[1]
scroll = int(sys.argv[2]) if len(sys.argv) > 2 else 12

from patchright.sync_api import sync_playwright

with sync_playwright() as pw:
    ctx = pw.chromium.launch_persistent_context(
        user_data_dir=str(PROFILE), executable_path=str(CHROME), headless=False,
        viewport={"width": 1400, "height": 900},
        args=["--disable-blink-features=AutomationControlled",
              "--no-first-run", "--no-default-browser-check"])
    page = ctx.pages[0] if ctx.pages else ctx.new_page()
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    pause(3, 5)
    if captcha_hit(page):
        print("captcha")
        ctx.close()
        sys.exit(2)
    works = list_works(page, rounds=scroll)
    print(json.dumps({"count": len(works),
                      "ids": [w["aweme_id"] for w in works][:5]}, ensure_ascii=False))
    for w in works[:3]:
        print(' 首次:', w["aweme_id"])
    ctx.close()
