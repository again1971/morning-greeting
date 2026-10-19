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


def ball(n, size=78, core=False):
    _, c1, c2 = ZONES[zone_of(n)]
    ring = "box-shadow:0 0 0 4px #fff,0 0 0 8px #e8a33d,0 4px 8px rgba(0,0,0,.18);" if core else \
        "box-shadow:inset -4px -6px 10px rgba(0,0,0,.12),0 3px 6px rgba(0,0,0,.15);"
    return (f'<div class="ball" style="width:{size}px;height:{size}px;font-size:{int(size*0.42)}px;'
            f'background:radial-gradient(circle at 32% 28%,#ffffffcc 0,#ffffff00 34%),'
            f'radial-gradient(circle at 50% 50%,{c1} 55%,{c2} 100%);{ring}">{n}</div>')


def build_html(out):
    sets = out["sets"]
    core = set(out.get("core", []))
    rows = []
    for i, s in enumerate(sets):
        z = [0] * 5
        for n in s:
            z[zone_of(n)] += 1
        dots = "".join(
            f'<span class="zd{"" if v else " z0"}" style="background:{ZONES[k][1] if v else "#e9e6df"}">{v}</span>'
            for k, v in enumerate(z))
        tag = "핵심 3" if core and core.issubset(s) else ("핵심 2" if len(core & set(s)) == 2 else ("집중" if (out.get("concentration") or {}).get("set_index") == i else "보험"))
        rows.append(f"""
        <div class="row">
          <div class="lbl"><span class="no">{chr(65 + i)}</span><span class="tag">{tag}</span></div>
          <div class="balls">{''.join(ball(n, 74, core=n in core) for n in s)}</div>
          <div class="zone">{dots}</div>
        </div>""")

    core_balls = "".join(ball(n, 58) for n in sorted(core))
    legend = "".join(
        f'<span class="lg"><i style="background:{c1}"></i>{html.escape(name)}</span>' for name, c1, _ in ZONES)
    excl = out.get("excluded") or []
    excl_html = (f'<div class="excl">제외번호 {", ".join(map(str, excl))}</div>' if excl else "")

    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{width:{W}px;height:{H}px;font-family:'Noto Sans CJK KR','Noto Sans KR',sans-serif;
  background:#f6f3ec;color:#1f2a44}}
.top{{background:#1f2a44;color:#fff;padding:44px 56px 36px;position:relative;overflow:hidden}}
.deco{{position:absolute;right:56px;top:58px;display:flex;gap:10px}}
.deco .ball{{opacity:.95}}
.kicker{{font-size:24px;letter-spacing:6px;color:#fbc400;font-weight:700}}
.title{{font-size:64px;font-weight:900;margin-top:8px;letter-spacing:-1px}}
.title b{{color:#fbc400}}
.date{{font-size:26px;margin-top:10px;color:#c9cfdd}}
.board{{margin:30px 40px 0;background:#fff;border-radius:28px;padding:14px 30px;
  box-shadow:0 6px 24px rgba(31,42,68,.08)}}
.row{{display:flex;align-items:center;padding:17px 0;border-bottom:2px dashed #ece7dc}}
.row:last-child{{border-bottom:none}}
.lbl{{width:92px;display:flex;flex-direction:column;align-items:flex-start;gap:6px}}
.no{{font-size:40px;font-weight:900;color:#1f2a44;line-height:1}}
.tag{{font-size:17px;font-weight:700;color:#8a7a55;background:#f3ecdc;border-radius:20px;padding:3px 10px}}
.balls{{display:flex;gap:12px;flex:1}}
.ball{{border-radius:50%;display:flex;align-items:center;justify-content:center;color:#fff;font-weight:800;
  text-shadow:0 1px 2px rgba(0,0,0,.35);flex:none}}
.zone{{display:flex;gap:4px;margin-left:10px}}
.zd{{width:22px;height:30px;border-radius:6px;font-size:16px;font-weight:800;color:#fff;
  display:flex;align-items:center;justify-content:center}}
.zd.z0{{color:#b9b4a8}}
.foot{{margin:30px 56px 0;display:flex;align-items:center;justify-content:space-between}}
.core{{display:flex;align-items:center;gap:14px}}
.core .t{{font-size:26px;font-weight:800;margin-right:6px}}
.core .t small{{display:block;font-size:17px;font-weight:500;color:#7a7f8c;margin-top:2px}}
.legend{{margin:26px 56px 0;display:flex;gap:22px;font-size:19px;color:#5a6070}}
.lg{{display:flex;align-items:center;gap:7px}}
.lg i{{width:18px;height:18px;border-radius:50%;display:inline-block}}
.excl{{margin:12px 56px 0;font-size:19px;color:#a0524a}}
.note{{margin:22px 56px 0;padding-top:16px;border-top:1px solid #e3ddcf;font-size:18px;color:#9a9ca4}}
</style></head><body>
<div class="top">
  <div class="kicker">LOTTO 6/45</div>
  <div class="title"><b>{out['round']}</b>회 추천번호</div>
  <div class="date">{html.escape(out['draw_date'])}(토) 추첨</div>
  <div class="deco">{''.join(ball(n, 46) for n in (7, 15, 23, 34, 42))}</div>
</div>
<div class="board">{''.join(rows)}</div>
<div class="foot">
  <div class="core"><div class="t">핵심번호<small>테두리 공 · A~D 세트 공유</small></div>{core_balls}</div>
</div>
<div class="legend">{legend}<span class="lg" style="margin-left:auto">오른쪽 칸 = 구간별 개수</span></div>
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
