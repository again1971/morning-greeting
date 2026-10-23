"""로또 추천번호 카드 이미지 만들기 (lotto_out.json → images/YYYY-MM-DD_lotto.png)

공 색깔은 동행복권 홈페이지 색을 따르되, 구간은 어게인님 기준(1~9 / 10번대 / 20번대 / 30번대 / 40번대)
사용법: python scripts/lotto_card.py [입력 json] [출력 png]
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
W, H = 900, 1125

# 동행복권 공 색 (노랑 / 파랑 / 빨강 / 회색 / 초록)
ZONES = [
    ("1~9", "#fbc400", "#e0a800"),
    ("10번대", "#69c8f2", "#3fa9dc"),
    ("20번대", "#ff7272", "#e54d4d"),
    ("30번대", "#aaaaaa", "#8a8a8a"),
    ("40번대", "#b0d840", "#8fbb1f"),
]


def zone_of(n):
    return 0 if n <= 9 else 1 if n <= 19 else 2 if n <= 29 else 3 if n <= 39 else 4


NUM_FONT = "'DejaVu Sans','Noto Sans CJK KR',sans-serif"   # 숫자 전용: 1·7·4 모양이 또렷한 글꼴


def ball(n, size=110, core=False):
    """색 테두리 + 흰 바탕 + 검은 굵은 숫자 (휴대폰에서 작게 보여도 읽히도록, 2026-10-23)"""
    _, c1, c2 = ZONES[zone_of(n)]
    ring = int(size * 0.13)
    outer = (f"box-shadow:0 0 0 5px #fff,0 0 0 11px #e8a33d,0 4px 10px rgba(0,0,0,.18);" if core
             else "box-shadow:0 3px 8px rgba(0,0,0,.16);")
    return (f'<div class="ball" style="width:{size}px;height:{size}px;background:{c1};{outer}">'
            f'<div class="inner" style="inset:{ring}px;font-size:{int(size * 0.5)}px">{n}</div></div>')


def build_html(out):
    sets = out["sets"]
    core = set(out.get("core", []))
    conc_idx = (out.get("concentration") or {}).get("set_index")
    rows = []
    for i, s in enumerate(sets):
        z = [0] * 5
        for n in s:
            z[zone_of(n)] += 1
        tag = "핵심 3" if core and core.issubset(s) else ("핵심 2" if len(core & set(s)) == 2 else ("집중" if conc_idx == i else "보험"))
        rows.append(f"""
        <div class="row">
          <div class="lbl"><span class="no">{chr(65 + i)}</span><span class="tag">{tag}</span><span class="zs">{'-'.join(map(str, z))}</span></div>
          <div class="balls">{''.join(ball(n, 102, core=n in core) for n in s)}</div>
        </div>""")

    core_balls = "".join(ball(n, 74) for n in sorted(core))
    legend = "".join(
        f'<span class="lg"><i style="background:{c1}"></i>{html.escape(name)}</span>' for name, c1, _ in ZONES)
    excl = out.get("excluded") or []
    excl_html = (f'<div class="excl">제외번호 {", ".join(map(str, excl))}</div>' if excl else "")

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{width:{W}px;height:{H}px;font-family:'Noto Sans CJK KR','Noto Sans KR',sans-serif;
  background:#f6f3ec;color:#1f2a44}}
.top{{background:#1f2a44;color:#fff;padding:30px 44px 26px;display:flex;align-items:flex-end;justify-content:space-between}}
.kicker{{font-size:22px;letter-spacing:6px;color:#fbc400;font-weight:700}}
.title{{font-size:60px;font-weight:900;margin-top:4px;letter-spacing:-1px;line-height:1.1}}
.title b{{color:#fbc400;font-family:{NUM_FONT}}}
.date{{font-size:30px;color:#dfe3ec;font-weight:700;font-family:{NUM_FONT};padding-bottom:6px}}
.board{{margin:20px 16px 0;background:#fff;border-radius:26px;padding:6px 18px;
  box-shadow:0 6px 24px rgba(31,42,68,.08)}}
.row{{display:flex;align-items:center;padding:17px 0;border-bottom:2px dashed #ece7dc}}
.row:last-child{{border-bottom:none}}
.lbl{{width:78px;display:flex;flex-direction:column;align-items:flex-start;gap:5px;flex:none}}
.no{{font-size:44px;font-weight:900;line-height:1;font-family:{NUM_FONT}}}
.tag{{font-size:17px;font-weight:700;color:#7a6a45;background:#f3ecdc;border-radius:20px;padding:2px 9px}}
.zs{{font-size:15px;color:#9a9284;font-family:{NUM_FONT}}}
.balls{{display:flex;gap:14px;flex:1;justify-content:space-between;padding:0 12px 0 10px}}
.ball{{border-radius:50%;position:relative;flex:none}}
.inner{{position:absolute;border-radius:50%;background:#fff;display:flex;align-items:center;justify-content:center;
  font-family:{NUM_FONT};font-weight:700;color:#111;letter-spacing:-2px;line-height:1}}
.foot{{margin:24px 44px 0;display:flex;align-items:center;gap:18px}}
.foot .t{{font-size:28px;font-weight:800;margin-right:6px}}
.foot .t small{{display:block;font-size:17px;font-weight:500;color:#7a7f8c;margin-top:2px}}
.legend{{margin:22px 44px 0;display:flex;gap:20px;font-size:19px;color:#5a6070;flex-wrap:wrap}}
.lg{{display:flex;align-items:center;gap:7px}}
.lg i{{width:18px;height:18px;border-radius:50%;display:inline-block}}
.excl{{margin:10px 44px 0;font-size:19px;color:#a0524a}}
.note{{margin:18px 44px 0;padding-top:14px;border-top:1px solid #e3ddcf;font-size:17px;color:#9a9ca4}}
</style></head><body>
<div class="top">
  <div><div class="kicker">LOTTO 6/45</div>
  <div class="title"><b>{out['round']}</b>회 추천번호</div></div>
  <div class="date">{html.escape(out['draw_date'])}(토)</div>
</div>
<div class="board">{''.join(rows)}</div>
<div class="foot"><div class="t">핵심번호<small>주황 테두리 · A~D 공유</small></div>{core_balls}</div>
<div class="legend">{legend}<span class="lg" style="margin-left:auto">왼쪽 작은 숫자 = 구간별 개수</span></div>
{excl_html}
<div class="note">과거 당첨 데이터 패턴 분석 기반 참고용 조합이며, 당첨을 보장하지 않습니다.</div>
</body></html>"""


def render(out, png_path):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.set_content(build_html(out), wait_until="load")
        pg.evaluate("document.fonts.ready")
        pg.wait_for_timeout(300)
        pg.screenshot(path=str(png_path), clip={"x": 0, "y": 0, "width": W, "height": H})
        b.close()


if __name__ == "__main__":
    # 인자 없이 실행하면: lotto_out.json → images/YYYY-MM-DD_lotto.png 를 만들고 lotto_out.json 에 "image" 경로 기록
    if len(sys.argv) > 2:
        render(json.loads(Path(sys.argv[1]).read_text(encoding="utf-8")), Path(sys.argv[2]))
        print(sys.argv[2])
    else:
        from datetime import datetime, timedelta, timezone
        out_file = ROOT / "lotto_out.json"
        out = json.loads(out_file.read_text(encoding="utf-8"))
        today = datetime.now(timezone(timedelta(hours=9))).strftime("%Y-%m-%d")
        (ROOT / "images").mkdir(exist_ok=True)
        rel = f"images/{today}_lotto.png"
        render(out, ROOT / rel)
        out["image"] = rel
        out_file.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        print(rel)
