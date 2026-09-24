"""2026 추석 카드 (수묵화 + 달토끼, 신승묵 배상) 생성 → images/ 에 PNG, special_out.json 기록
발송은 special_card.py send 가 담당."""
import base64, json, sys
from datetime import datetime
from pathlib import Path
import requests
from PIL import Image, ImageFilter
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from morning import IMAGES_DIR, KST, ROOT, log  # noqa: E402

FONT_BASE = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FONTS = {"brush": "nanumbrushscript/NanumBrushScript-Regular.ttf", "song": "songmyung/SongMyung-Regular.ttf",
         "gowun": "gowunbatang/GowunBatang-Regular.ttf"}
W, H = 900, 1600


def b64(data): return base64.b64encode(data).decode()


def main():
    font_css = "".join(f"@font-face{{font-family:'{k}';src:url(data:font/ttf;base64,{b64(requests.get(FONT_BASE + v, timeout=60).content)})}}"
                       for k, v in FONTS.items())
    bg = ROOT / "assets" / "bg3.jpg"
    up = Path("/tmp/bg3_up.jpg")
    Image.open(bg).resize((W, 1602), Image.LANCZOS).filter(ImageFilter.UnsharpMask(2, 60, 2)).save(up, quality=93)
    seal = ('<div style="position:absolute;left:520px;top:560px;width:62px;height:62px;background:#b3261e;color:#fff4e0;'
            'font:48px/62px song;text-align:center;border-radius:6px;box-shadow:0 2px 6px rgba(0,0,0,.3)">秋</div>')
    html = f"""<!doctype html><html><head><meta charset=utf-8><style>{font_css} body{{margin:0}}</style></head><body>
<div style="position:relative;width:{W}px;height:{H}px;overflow:hidden;background:url(data:image/jpeg;base64,{b64(up.read_bytes())}) center/cover">
<div style="position:absolute;top:470px;left:90px;color:#2b2622">
 <div style="font:190px/1 brush">한가위</div>
 <div style="font:40px/1.75 gowun;margin-top:34px">달이 가장 밝은 밤,<br>그리운 얼굴들과 함께<br>평안하고 넉넉한<br>추석 보내시길 바랍니다.</div>
 <div style="font:46px song;margin-top:44px;color:#2b2622;letter-spacing:6px">신승묵 <span style="font-size:36px;color:#6b5f55">배상</span></div>
</div>
{seal}
<div style="position:absolute;right:52px;top:640px;writing-mode:vertical-rl;font:34px song;color:#6b5f55;letter-spacing:8px">건강과 행복이 가득하기를</div>
</div></body></html>"""
    IMAGES_DIR.mkdir(exist_ok=True)
    name = f"special_{datetime.now(KST).strftime('%Y-%m-%d_%H%M%S')}.png"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.set_content(html)
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(IMAGES_DIR / name))
        b.close()
    (ROOT / "special_out.json").write_text(json.dumps({"image": f"images/{name}", "width": W, "height": H}), encoding="utf-8")
    log("추석 카드 생성:", name)


if __name__ == "__main__":
    main()
