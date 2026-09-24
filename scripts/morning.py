"""
아침인사 자동 발송 (n8n → GitHub Actions 이전판)

사용법:
  python scripts/morning.py generate   # 데이터 수집 → 문구 조립 → 카드 이미지(PNG) 생성
  python scripts/morning.py send       # (이미지 push 후) 카카오 '나에게 보내기' 발송

n8n 워크플로우 2개(Daily Morning Briefing to KakaoTalk / Greeting Image Renderer)의
로직을 그대로 옮겼습니다. 문구 템플릿·레이아웃·사진 로테이션 규칙은 동일합니다.
"""
import base64
import html
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
import urllib3

urllib3.disable_warnings()

ROOT = Path(__file__).resolve().parent.parent
STATE_FILE = ROOT / "state.json"
IMAGES_DIR = ROOT / "images"
OUT_FILE = ROOT / "out.json"          # generate → send 사이에 넘기는 값 (커밋 안 함)
KST = timezone(timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}


def log(*a):
    print(*a, flush=True)


def load_state():
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"queryIndex": 0, "usedPhotoIds": [], "lastSentDate": ""}


def save_state(s):
    STATE_FILE.write_text(json.dumps(s, ensure_ascii=False, indent=2), encoding="utf-8")


def get(url, retries=3, headers=None, **kw):
    """HTTP GET with retries. 하나 실패해도 전체가 멈추지 않도록 호출부에서 예외 처리."""
    last = None
    for i in range(retries):
        try:
            r = requests.get(url, timeout=20, headers=headers or UA, **kw)
            r.raise_for_status()
            return r
        except requests.exceptions.SSLError as e:  # wttr.in SSL 이슈 대비 (n8n의 Ignore SSL Issues와 동일)
            last = e
            kw["verify"] = False
        except Exception as e:
            last = e
        time.sleep(2 * (i + 1))
    raise last


# ---------------------------------------------------------------- 날씨
def sky_desc(code):
    if code == 113: return "맑음"
    if code == 116: return "대체로 맑음"
    if code == 119: return "구름 많음"
    if code == 122: return "흐림"
    if code in (143, 248, 260): return "안개"
    if code in (176, 263, 266, 293, 296, 299, 302, 305, 308, 353, 356, 359): return "비"
    if code in (179, 227, 230, 323, 326, 329, 332, 335, 338, 368, 371): return "눈"
    if code in (200, 386, 389, 392, 395): return "천둥번개"
    return "구름 많음"


def fetch_weather():
    try:
        j = get("https://wttr.in/Seoul?format=j1").json()
        cc = j["current_condition"][0]
        return sky_desc(int(cc["weatherCode"])), round(float(cc["temp_C"]))
    except Exception as e:
        log("[weather] 실패:", e)
        return "구름 많음", None


# ---------------------------------------------------------------- 뉴스
def fetch_news():
    try:
        rss = get("https://news.google.com/rss?hl=ko&gl=KR&ceid=KR:ko").text
        items = re.findall(r"<item>([\s\S]*?)</item>", rss)
        heads = []
        for it in items:
            m = re.search(r"<title>(?:<!\[CDATA\[)?([\s\S]*?)(?:\]\]>)?</title>", it)
            if m:
                t = html.unescape(m.group(1).strip())
                t = re.sub(r"\s*-\s*[^-]+$", "", t)
                heads.append(t)
            if len(heads) == 3:
                break
        return heads or ["주요 뉴스 확인 필요"]
    except Exception as e:
        log("[news] 실패:", e)
        return ["주요 뉴스 확인 필요"]


# ---------------------------------------------------------------- 미국 증시
def fetch_pct(symbol):
    for host in ("query1", "query2"):
        try:
            j = get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{symbol}").json()
            meta = j["chart"]["result"][0]["meta"]
            cur = meta.get("regularMarketPrice")
            prev = meta.get("chartPreviousClose", meta.get("previousClose"))
            if cur is None or not prev:
                return None
            return (cur - prev) / prev * 100
        except Exception as e:
            log(f"[market {symbol} @{host}] 실패:", e)
    return None


def fmt(p):
    if p is None:
        return "-"
    return ("▲" if p >= 0 else "▼") + f"{abs(p):.2f}%"


# ---------------------------------------------------------------- 24절기 (KST)
SOLAR_TERMS = {
    2026: [
        (2, 4, "입춘"), (2, 19, "우수"), (3, 5, "경칩"), (3, 20, "춘분"), (4, 5, "청명"), (4, 20, "곡우"),
        (5, 5, "입하"), (5, 21, "소만"), (6, 6, "망종"), (6, 21, "하지"), (7, 7, "소서"), (7, 23, "대서"),
        (8, 7, "입추"), (8, 23, "처서"), (9, 7, "백로"), (9, 23, "추분"), (10, 8, "한로"), (10, 23, "상강"),
        (11, 7, "입동"), (11, 22, "소설"), (12, 7, "대설"), (12, 22, "동지"),
    ],
    2027: [
        (1, 5, "소한"), (1, 20, "대한"),
        (2, 4, "입춘"), (2, 19, "우수"), (3, 6, "경칩"), (3, 21, "춘분"), (4, 5, "청명"), (4, 20, "곡우"),
        (5, 6, "입하"), (5, 21, "소만"), (6, 6, "망종"), (6, 21, "하지"), (7, 7, "소서"), (7, 23, "대서"),
        (8, 8, "입추"), (8, 23, "처서"), (9, 8, "백로"), (9, 23, "추분"), (10, 8, "한로"), (10, 24, "상강"),
        (11, 8, "입동"), (11, 22, "소설"), (12, 7, "대설"), (12, 22, "동지"),
    ],
}
# TODO(2028): 2027년 연말 전에 2028년 절기 날짜 추가 필요


def compose_greeting(now):
    wd = ["월", "화", "수", "목", "금", "토", "일"][now.weekday()] + "요일"
    date_header = f"{now.year}년 {now.month}월 {now.day}일 {wd}"
    term = next((t for (m, d, t) in SOLAR_TERMS.get(now.year, []) if m == now.month and d == now.day), None)
    term_note = f" 오늘은 24절기 중 {term}이에요." if term else ""

    sky, temp = fetch_weather()
    heads = fetch_news()
    news_line = " ".join(f"{i + 1}) {h}" for i, h in enumerate(heads))
    dow, nasdaq, sox = fmt(fetch_pct("%5EDJI")), fmt(fetch_pct("%5EIXIC")), fmt(fetch_pct("%5ESOX"))
    temp_txt = f"{temp}" if temp is not None else "-"

    greeting = (
        f"{date_header}, 안녕하세요!\n"
        f"오늘 서울은 {sky}, 기온 {temp_txt}℃ 예상돼요.{term_note}\n"
        f"간밤 미국 증시는 다우 {dow}, 나스닥 {nasdaq}, 반도체 {sox} 마감했어요.\n"
        f"오늘의 주요 소식 — {news_line}\n"
        f"오늘도 활기차고 건강한 하루 보내세요!"
    )
    return greeting, sky


# ---------------------------------------------------------------- 배경 사진 (세계 명소 로테이션)
LANDMARK_QUERIES = [
    ("스위스", "Jungfrau Switzerland snow mountain peak"),
    ("호주", "Sydney Opera House harbour view"),
    ("미국", "Grand Canyon landscape sunset"),
    ("미국", "Yosemite national park landscape"),
    ("한국", "Jeju Island coast landscape Korea"),
    ("한국", "Seoraksan autumn foliage mountain Korea"),
    ("일본", "Mount Fuji landscape Japan"),
    ("러시아", "Moscow city night skyline Russia"),
    ("노르웨이", "Norway aurora borealis northern lights"),
    ("노르웨이", "Norway fjord landscape"),
    ("영국", "London city landscape England"),
    ("독일", "Neuschwanstein castle Germany landscape"),
    ("프랑스", "Eiffel Tower Paris cityscape"),
    ("프랑스", "French Alps mountain landscape"),
    ("이탈리아", "Venice canal Italy landscape"),
    ("이탈리아", "Cinque Terre coast Italy"),
    ("중국", "Great Wall of China mountain landscape"),
    ("이집트", "Egypt pyramids desert landscape"),
    ("캐나다", "Canadian Rockies lake mountain landscape"),
    ("뉴질랜드", "New Zealand mountain lake landscape"),
    ("그리스", "Santorini Greece sunset view"),
    ("스페인", "Sagrada Familia Barcelona Spain landscape"),
    ("태국", "Thailand tropical beach landscape"),
    ("아이슬란드", "Iceland waterfall landscape"),
    ("브라질", "Rio de Janeiro landscape Brazil"),
    ("터키", "Cappadocia Turkey landscape balloons"),
]


def search_photos(query, key):
    try:
        r = get("https://api.pexels.com/v1/search",
                params={"query": query, "per_page": 15, "orientation": "portrait"},
                headers={"Authorization": key})
        return r.json().get("photos", [])
    except Exception as e:
        log("[pexels] 실패:", e)
        return []


def find_scenic_photo(state):
    key = os.environ.get("PEXELS_API_KEY", "")
    used = set(state.get("usedPhotoIds", []))
    qi = int(state.get("queryIndex", 0))

    def remember(pid):
        state["usedPhotoIds"] = (state.get("usedPhotoIds", []) + [pid])[-300:]

    n = len(LANDMARK_QUERIES)
    for attempt in range(n):
        idx = (qi + attempt) % n
        country, query = LANDMARK_QUERIES[idx]
        fresh = next((p for p in search_photos(query, key) if p["id"] not in used), None)
        if fresh:
            state["queryIndex"] = (idx + 1) % n
            remember(fresh["id"])
            return {"url": fresh["src"]["portrait"], "country": country, "query": query, "photoId": fresh["id"]}
    # 모두 소진 시 기록 초기화 후 1회 재시도
    state["usedPhotoIds"] = []
    country, query = LANDMARK_QUERIES[qi % n]
    photos = search_photos(query, key)
    state["queryIndex"] = (qi + 1) % n
    if photos:
        remember(photos[0]["id"])
        return {"url": photos[0]["src"]["portrait"], "country": country, "query": query, "photoId": photos[0]["id"]}
    return {"url": "", "country": country, "query": query, "photoId": None}


# ---------------------------------------------------------------- 카드 SVG (n8n 렌더러와 동일 레이아웃)
def is_full_width(ch):
    c = ord(ch)
    return (0xAC00 <= c <= 0xD7A3 or 0x1100 <= c <= 0x11FF or 0x3130 <= c <= 0x318F
            or 0x3000 <= c <= 0x303F or 0xFF00 <= c <= 0xFFEF or ch in "—“”‘’·…")


def wrap_text(text, max_w, fs):
    space_w = fs * 0.28
    lines, cur, cur_w = [], "", 0.0
    for ch in text:
        w = space_w if ch == " " else (fs * 0.98 if is_full_width(ch) else fs * 0.56)
        if cur_w + w > max_w and cur.strip():
            lines.append(cur.rstrip())
            cur, cur_w = ("", 0.0) if ch == " " else (ch, w)
        else:
            cur += ch
            cur_w += w
    if cur.strip():
        lines.append(cur.rstrip())
    return lines


def wrap_paragraphs(text, max_w, fs):
    out = []
    for para in text.split("\n"):
        out.extend(wrap_text(para, max_w, fs))
    return out


def fetch_font_b64(text):
    """Google Fonts 동적 서브셋(필요한 글자만) → base64. 실패하면 None (시스템 Noto CJK 폰트로 대체)."""
    try:
        css = get("https://fonts.googleapis.com/css",
                  params={"family": "Noto Sans KR", "text": text},
                  headers={"User-Agent": "Mozilla/5.0 (Windows NT 5.1)"}).text
        m = re.search(r"url\((https:[^)]+)\)", css)
        if not m:
            return None
        return base64.b64encode(get(m.group(1)).content).decode()
    except Exception as e:
        log("[font] 실패:", e)
        return None


def build_svg(greeting, photo_url):
    panel_w, pad, max_h = 900, 40, 640
    max_w = panel_w - pad * 2
    fs = 48
    while True:
        lines = wrap_paragraphs(greeting, max_w, fs)
        lh = round(fs * 1.42)
        if len(lines) * lh + pad * 2 <= max_h or fs <= 30:
            break
        fs -= 2
    panel_h = len(lines) * lh + pad * 2
    photo_y, photo_h = panel_h, 1125 - panel_h

    def esc(s):
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    tspans = "".join(
        f'<tspan x="450" y="{pad + fs * 0.85 + i * lh}" text-anchor="middle">{esc(l)}</tspan>'
        for i, l in enumerate(lines))

    photo_tag = ""
    if photo_url:
        try:
            img = get(photo_url).content
            photo_tag = (f'<image href="data:image/jpeg;base64,{base64.b64encode(img).decode()}" x="0" y="{photo_y}" '
                         f'width="900" height="{photo_h}" preserveAspectRatio="xMidYMid slice"/>')
        except Exception as e:
            log("[photo download] 실패:", e)

    font_b64 = fetch_font_b64(greeting)
    font_css = (f"@font-face{{font-family:'KR';src:url(data:font/ttf;base64,{font_b64}) format('truetype');}}"
                if font_b64 else "")
    return f"""<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="900" height="1125" viewBox="0 0 900 1125">
<rect width="900" height="1125" fill="#cfd8dc"/>
<rect x="0" y="0" width="900" height="{panel_h}" fill="#ffffff"/>
<style>{font_css}</style>
<text font-family="'KR','Noto Sans KR','Noto Sans CJK KR',sans-serif" font-size="{fs}" font-weight="400" fill="#154f9e">{tspans}</text>
{photo_tag}
<rect x="0" y="{photo_y}" width="900" height="4" fill="#154f9e"/>
</svg>"""


def render_png(svg, out_path):
    from playwright.sync_api import sync_playwright
    page_html = f"<!doctype html><html><body style='margin:0'>{svg}</body></html>"
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 900, "height": 1125}, device_scale_factor=1)
        pg.set_content(page_html, wait_until="load")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(500)
        pg.screenshot(path=str(out_path), clip={"x": 0, "y": 0, "width": 900, "height": 1125})
        b.close()


def prune_old_images(keep_days=60):
    cutoff = (datetime.now(KST) - timedelta(days=keep_days)).strftime("%Y-%m-%d")
    for f in IMAGES_DIR.glob("*.png"):
        if f.name[:10] < cutoff:
            f.unlink()


# ---------------------------------------------------------------- generate
def cmd_generate():
    now = datetime.now(KST)
    today = now.strftime("%Y-%m-%d")
    state = load_state()
    if state.get("lastSentDate") == today and os.environ.get("FORCE") != "true":
        log(f"오늘({today})은 이미 발송됨 → 건너뜀")
        OUT_FILE.write_text(json.dumps({"skip": True}), encoding="utf-8")
        return

    greeting, sky = compose_greeting(now)
    log("----- 문구 -----\n" + greeting + "\n----------------")
    photo = find_scenic_photo(state)
    log(f"배경 사진: {photo['country']} / {photo['query']} / id={photo['photoId']}")

    IMAGES_DIR.mkdir(exist_ok=True)
    prune_old_images()
    name = f"{today}_{now.strftime('%H%M%S')}.png"
    render_png(build_svg(greeting, photo["url"]), IMAGES_DIR / name)
    save_state(state)
    OUT_FILE.write_text(json.dumps({"skip": False, "image": f"images/{name}", "greeting": greeting,
                                    "photo": photo}, ensure_ascii=False), encoding="utf-8")
    log("이미지 생성 완료:", name)


# ---------------------------------------------------------------- send
def kakao_access_token():
    data = {
        "grant_type": "refresh_token",
        "client_id": os.environ["KAKAO_REST_API_KEY"],
        "refresh_token": os.environ["KAKAO_REFRESH_TOKEN"],
    }
    if os.environ.get("KAKAO_CLIENT_SECRET"):
        data["client_secret"] = os.environ["KAKAO_CLIENT_SECRET"]
    r = requests.post("https://kauth.kakao.com/oauth/token", data=data, timeout=20)
    if r.status_code != 200:
        raise SystemExit(f"카카오 토큰 갱신 실패: {r.status_code} {r.text[:300]}")
    j = r.json()
    # 카카오는 refresh token 만료 1개월 전부터 새 refresh token을 같이 내려줌 → 워크플로우가 시크릿을 자동 갱신
    if j.get("refresh_token"):
        Path(os.environ.get("RUNNER_TEMP", "/tmp"), "new_refresh_token").write_text(j["refresh_token"])
        log("새 refresh token 수신 → 시크릿 갱신 예정")
    return j["access_token"]


def wait_until_7am():
    if os.environ.get("NO_WAIT") == "true":
        return
    now = datetime.now(KST)
    target = now.replace(hour=7, minute=0, second=0, microsecond=0)
    secs = (target - now).total_seconds()
    if 0 < secs < 3 * 3600:
        log(f"07:00 KST까지 {int(secs)}초 대기")
        time.sleep(secs)


def cmd_send():
    out = json.loads(OUT_FILE.read_text(encoding="utf-8"))
    if out.get("skip"):
        return
    repo = os.environ["GITHUB_REPOSITORY"]
    branch = os.environ.get("GITHUB_REF_NAME", "main")
    image_url = f"https://raw.githubusercontent.com/{repo}/{branch}/{out['image']}"

    for _ in range(30):  # push 직후 raw URL이 열릴 때까지 확인
        try:
            if requests.head(image_url, timeout=10).status_code == 200:
                break
        except Exception:
            pass
        time.sleep(3)

    wait_until_7am()
    token = kakao_access_token()
    template = {
        "object_type": "feed",
        "content": {
            "image_url": image_url, "image_width": 900, "image_height": 1125,
            "link": {"web_url": image_url, "mobile_web_url": image_url},
        },
    }
    r = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
                      headers={"Authorization": f"Bearer {token}"},
                      data={"template_object": json.dumps(template, ensure_ascii=False)}, timeout=20)
    log("카카오 응답:", r.status_code, r.text[:300])
    if r.status_code != 200 or r.json().get("result_code") != 0:
        raise SystemExit("카카오톡 발송 실패")

    state = load_state()
    state["lastSentDate"] = datetime.now(KST).strftime("%Y-%m-%d")
    save_state(state)
    log("카카오톡 발송 성공:", image_url)


if __name__ == "__main__":
    {"generate": cmd_generate, "send": cmd_send}[sys.argv[1]]()
