"""로또 추천번호 카카오톡 '나에게 보내기' 발송 (카카오 토큰 처리는 morning.py 것을 그대로 사용)"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from morning import KST, ROOT, kakao_access_token, load_state, log, save_state  # noqa: E402

RESULT_URL = "https://www.dhlottery.co.kr/lt645/result"


def card_image_url(out):
    """카드 이미지가 GitHub에 올라가 있으면 그 주소, 없으면 None"""
    if not out.get("image") or not os.environ.get("GITHUB_REPOSITORY"):
        return None
    # 같은 날 다시 보내도 카카오가 예전 이미지를 재사용하지 않도록, 브랜치 이름 대신 커밋 주소 + 시각을 붙임 (2026-10-23)
    sha = subprocess.run(["git", "log", "-1", "--format=%H", "--", out["image"]],
                         capture_output=True, text=True).stdout.strip() or os.environ.get("GITHUB_REF_NAME", "main")
    url = (f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/"
           f"{sha}/{out['image']}?v={int(time.time())}")
    for _ in range(30):  # push 직후 주소가 열릴 때까지 확인
        try:
            if requests.head(url, timeout=10).status_code == 200:
                return url
        except Exception:
            pass
        time.sleep(3)
    log("카드 이미지 주소가 열리지 않아 글자로 보냅니다:", url)
    return None


def main():
    today = datetime.now(KST).strftime("%Y-%m-%d")
    state = load_state()
    if state.get("lottoLastSentDate") == today and os.environ.get("FORCE") != "true":
        log(f"오늘({today})은 이미 로또 번호 발송됨 → 건너뜀")
        return

    out = json.loads((ROOT / "lotto_out.json").read_text(encoding="utf-8"))

    if os.environ.get("NO_WAIT") != "true":  # 금요일 12:00 KST까지 대기
        now = datetime.now(KST)
        secs = (now.replace(hour=12, minute=0, second=0, microsecond=0) - now).total_seconds()
        if 0 < secs < 6 * 3600:
            log(f"12:00 KST까지 {int(secs)}초 대기")
            time.sleep(secs)
        # 기다리는 동안 아침인사 등이 state.json을 바꿨을 수 있으니 최신으로 받고 다시 확인
        subprocess.run(["git", "pull", "-q", "--rebase"], check=False)
        if load_state().get("lottoLastSentDate") == today and os.environ.get("FORCE") != "true":
            log(f"오늘({today})은 이미 로또 번호 발송됨 → 건너뜀")
            return

    token = kakao_access_token()
    text_template = {
        "object_type": "text",
        "text": out["message"],
        "link": {"web_url": RESULT_URL, "mobile_web_url": RESULT_URL},
    }
    templates = []
    image_url = card_image_url(out)
    if image_url:  # 카드 이미지가 있으면 이미지로, 실패하면 글자로
        templates.append({
            "object_type": "feed",
            "content": {
                "title": f"로또 {out['round']}회 추천번호",
                "description": f"{out['draw_date']}(토) 추첨 · 핵심번호 {', '.join(map(str, out.get('core', [])))}",
                "image_url": image_url, "image_width": 900, "image_height": 1125,
                "link": {"web_url": RESULT_URL, "mobile_web_url": RESULT_URL},
            },
            "buttons": [{"title": "당첨결과 보기", "link": {"web_url": RESULT_URL, "mobile_web_url": RESULT_URL}}],
        })
    templates.append(text_template)

    for template in templates:
        r = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
                          headers={"Authorization": f"Bearer {token}"},
                          data={"template_object": json.dumps(template, ensure_ascii=False)}, timeout=20)
        log(f"카카오 응답({template['object_type']}):", r.status_code, r.text[:300])
        if r.status_code == 200 and r.json().get("result_code") == 0:
            break
    else:
        raise SystemExit("카카오톡 발송 실패")

    state = load_state()
    state["lottoLastSentDate"] = today
    save_state(state)
    log(f"로또 {out['round']}회 추천번호 발송 성공")


if __name__ == "__main__":
    main()
