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
    template = {
        "object_type": "text",
        "text": out["message"],
        "link": {"web_url": RESULT_URL, "mobile_web_url": RESULT_URL},
    }
    r = requests.post("https://kapi.kakao.com/v2/api/talk/memo/default/send",
                      headers={"Authorization": f"Bearer {token}"},
                      data={"template_object": json.dumps(template, ensure_ascii=False)}, timeout=20)
    log("카카오 응답:", r.status_code, r.text[:300])
    if r.status_code != 200 or r.json().get("result_code") != 0:
        raise SystemExit("카카오톡 발송 실패")

    state = load_state()
    state["lottoLastSentDate"] = today
    save_state(state)
    log(f"로또 {out['round']}회 추천번호 발송 성공")


if __name__ == "__main__":
    main()
