# 아침인사 (GitHub Actions)

매일 07:00 KST에 날씨·미국증시·주요뉴스 카드를 만들어 카카오톡 "나에게 보내기"로 보냅니다.
n8n 체험 종료로 2026-09-24에 n8n에서 이곳으로 옮겼습니다.

- `scripts/morning.py` — 데이터 수집, 문구 조립, 카드 이미지 생성, 카카오 발송
- `.github/workflows/morning.yml` — 매일 06:30 KST 시작, 07:00 KST 발송 (Actions 탭에서 수동 실행 가능)
- `.github/workflows/kakao-token-setup.yml` — 카카오 토큰 최초 등록용 (한 번만)
- `state.json` — 사용한 배경 사진 기록(중복 방지), 마지막 발송일
- `images/` — 발송한 카드 이미지 (60일 보관)

## 필요한 Secrets (Settings → Secrets and variables → Actions)
| 이름 | 내용 |
|---|---|
| `KAKAO_REST_API_KEY` | 카카오 개발자 > 아침인사 앱 > REST API 키 |
| `KAKAO_CLIENT_SECRET` | (앱에서 Client Secret을 켜둔 경우만) |
| `PEXELS_API_KEY` | Pexels API 키 |
| `GH_PAT` | 이 저장소 Secrets 쓰기 권한이 있는 GitHub 토큰 (카카오 토큰 자동 갱신용) |
| `KAKAO_REFRESH_TOKEN` | "카카오 토큰 최초 등록" 워크플로우가 자동으로 저장 |
