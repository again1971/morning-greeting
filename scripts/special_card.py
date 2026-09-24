"""명절/기념일 스페셜 카드 (사진 가득 + 인사말) → 카카오톡 '나에게 보내기'

사용법 (Actions "스페셜 카드 발송" 수동 실행):
  python scripts/special_card.py generate   # 카드 PNG 생성 (special_out.json)
  python scripts/special_card.py send       # (이미지 push 후) 카카오 발송
입력은 환경변수: CARD_TITLE, CARD_SUBTITLE, CARD_BODY('/'로 줄바꿈), CARD_PHOTO_URL, CARD_MOON(true/false)
"""
import html
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from morning import IMAGES_DIR, KST, ROOT, kakao_access_token, log  # noqa: E402

OUT = ROOT / "special_out.json"


def build_html():
    e = lambda s: html.escape(s or "")
    title = os.environ.get("CARD_TITLE", "")
    subtitle = os.environ.get("CARD_SUBTITLE", "")
    body = "<br>".join(e(x.strip()) for x in os.environ.get("CARD_BODY", "").split("/") if x.strip())
    photo = os.environ.get("CARD_PHOTO_URL", "")
    moon = os.environ.get("CARD_MOON", "true") == "true"
    moon_div = ('<div style="position:absolute;left:700px;top:46px;width:140px;height:140px;border-radius:50%;'
                'background:radial-gradient(circle at 42% 40%,#fffdf2 0%,#fff1c4 55%,#f6d98a 100%);'
                'box-shadow:0 0 60px 20px rgba(255,236,170,.55),0 0 160px 60px rgba(255,220,140,.25)"></div>') if moon else ""
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500&family=Noto+Serif+KR:wght@600;700&display=block">
<style>body{{margin:0}} .sans{{font-family:'Noto Sans KR','Noto Sans CJK KR',sans-serif}} .serif{{font-family:'Noto Serif KR','Noto Serif CJK KR',serif}}</style></head>
<body><div style="position:relative;width:900px;height:1125px;overflow:hidden;background:#111 url('{e(photo)}') center/cover no-repeat">
<div style="position:absolute;inset:0;background:linear-gradient(180deg,rgba(8,10,30,.72) 0%,rgba(8,10,30,.25) 38%,rgba(0,0,0,0) 55%,rgba(0,0,0,.35) 72%,rgba(0,0,0,.78) 100%)"></div>
{moon_div}
<div style="position:absolute;top:200px;left:0;right:0;text-align:center">
  <div class="sans" style="font-weight:500;font-size:30px;letter-spacing:12px;color:#f7e3ad">{e(subtitle)}</div>
  <div class="serif" style="font-weight:700;font-size:104px;line-height:1.2;color:#fff6de;text-shadow:0 4px 18px rgba(0,0,0,.6);margin-top:18px">{e(title)}</div>
</div>
<div class="sans" style="position:absolute;bottom:80px;left:60px;right:60px;text-align:center;font-size:38px;line-height:1.65;color:#fff;text-shadow:0 2px 10px rgba(0,0,0,.8)">{body}</div>
</div></body></html>"""


def cmd_generate():
    from playwright.sync_api import sync_playwright
    IMAGES_DIR.mkdir(exist_ok=True)
    name = f"special_{datetime.now(KST).strftime('%Y-%m-%d_%H%M%S')}.png"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 900, "height": 1125}, device_scale_factor=1)
        pg.set_content(build_html(), wait_until="networkidle")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(1500)
        pg.screenshot(path=str(IMAGES_DIR / name), clip={"x": 0, "y": 0, "width": 900, "height": 1125})
        b.close()
    OUT.write_text(json.dumps({"image": f"images/{name}"}), encoding="utf-8")
    log("스페셜 카드 생성:", name)


def cmd_send():
    out = json.loads(OUT.read_text(encoding="utf-8"))
    url = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{os.environ.get('GITHUB_REF_NAME', 'main')}/{out['image']}"
    for _ in range(30):
        try:
            if requests.head(url, timeout=10).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(3)
    token = kakao_access_token()
    template = {"object_type": "feed", "content": {"image_url": url, "image_width": 900, "image_height": 1125,
                                                   "link": {"web_url": url, "mobile_web_url": url}}}
    r = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
                      headers={"Authorization": f"Bearer {token}"},
                      data={"template_object": json.dumps(template, ensure_ascii=False)}, timeout=20)
    log("카카오 응답:", r.status_code, r.text[:300])
    if r.status_code != 200 or r.json().get("result_code") != 0:
        raise SystemExit("카카오톡 발송 실패")
    log("스페셜 카드 발송 성공:", url)


if __name__ == "__main__":
    {"generate": cmd_generate, "send": cmd_send}[sys.argv[1]]()
