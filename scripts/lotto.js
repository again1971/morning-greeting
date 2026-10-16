// 로또 번호 추천 (GitHub Actions용)
// 사용법: node scripts/lotto.js  → lotto_out.json 에 메시지 저장
//
// 2026-10-16 개편 (어게인님 의견 반영)
//  1) 핵심번호: 최근 1년·6개월·3개월에서 공통으로 강한 번호 중, 최근 2주(2회) 쉬고 있는 번호로 선정
//  2) 핵심번호 순환: 직전 2회차에 핵심번호로 쓴 번호는 이번 회차 핵심번호에서 제외
//  3) 단기 패턴 제외: 최근 출현 패턴별 '다음 회차 출현율'을 매주 다시 계산해서,
//     전체·최근 5년·최근 2년 모두에서 기준선(6/45)보다 확실히 낮은 패턴의 번호는 제외
//     + 최근 1개월(4회) 안에 4번 이상 나온 번호는 항상 제외
//  4) 지난주 번호 감점은 약하게 (역대 데이터상 지난주 번호도 다시 나올 확률이 다른 번호와 같음)
//  유지: 역대 1등 조합 제외, 홀짝·합계·연속·구간 필터, 핵심번호 공유 5세트 구조, 세트 간 공통 최대 3개
const N = 45;
const BASELINE = 6 / 45;
const W1Y = 52, W6M = 26, W3M = 13, W1M = 4, REST = 2;
const CORE_ROTATION = 2;          // 직전 몇 회차의 핵심번호를 이번에 제외할지
const ROTATION_ANCHOR = 1243;     // 순환 계산 시작 회차 (이 회차부터 결정적으로 재계산)

function mulberry32(seed) {
  return function () {
    let t = (seed += 0x6D2B79F5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function weightedPick(items, weightOf, rng) {
  const total = items.reduce((a, n) => a + weightOf(n), 0);
  let r = rng() * total;
  for (let i = 0; i < items.length; i++) { r -= weightOf(items[i]); if (r <= 0) return i; }
  return items.length - 1;
}

// D: 회차순 Set 배열, upto: 이 인덱스까지(포함) 데이터만 사용
function countIn(D, upto, w, n) {
  let c = 0;
  for (let j = Math.max(0, upto - w + 1); j <= upto; j++) if (D[j].has(n)) c++;
  return c;
}

// ---- 3) 단기 패턴 검증: 최근 출현 패턴별 다음 회차 출현율 ----
function patternKey(D, t, n) {
  const k = c => (c >= 4 ? '4+' : String(c));
  return {
    last1: D[t].has(n) ? 'yes' : 'no',
    m1: k(countIn(D, t, W1M, n)),
    m2: k(countIn(D, t, 9, n)),
    m3: k(countIn(D, t, W3M, n)),
  };
}

function findWeakPatterns(D, upto) {
  // upto: 분석에 쓸 마지막 회차 인덱스 (이 회차 다음 결과까지 알고 있어야 하므로 t < upto)
  const periods = { all: 13, y5: Math.max(13, upto - 260), y2: Math.max(13, upto - 104) };
  const rates = {};
  for (const [p, from] of Object.entries(periods)) {
    const acc = {};
    for (let t = from; t < upto; t++) {
      for (let n = 1; n <= N; n++) {
        const hit = D[t + 1].has(n) ? 1 : 0;
        for (const [dim, val] of Object.entries(patternKey(D, t, n))) {
          const key = dim + ':' + val;
          (acc[key] ||= [0, 0]);
          acc[key][0] += hit; acc[key][1] += 1;
        }
      }
    }
    rates[p] = acc;
  }
  const minN = { all: 30, y5: 10, y2: 5 };
  const weak = [];
  for (const key of Object.keys(rates.all)) {
    let low = true;
    for (const p of ['all', 'y5', 'y2']) {
      const v = rates[p][key];
      if (!v || v[1] < minN[p] || v[0] / v[1] >= BASELINE * 0.85) { low = false; break; }
    }
    if (low) weak.push(key);
  }
  return weak;
}

// ---- 회차별 분석: 점수, 제외번호, 핵심번호 후보 ----
// idx: 마지막으로 알고 있는 회차의 인덱스 (다음 회차를 추천)
function analyze(D, idx, withPatterns) {
  const freqAll = {}, lastSeen = {};
  for (let n = 1; n <= N; n++) { freqAll[n] = 0; lastSeen[n] = -1; }
  for (let j = 0; j <= idx; j++) for (const n of D[j]) { freqAll[n]++; lastSeen[n] = j; }

  const win = {};
  for (const w of [W1Y, W6M, W3M]) {
    win[w] = {};
    for (let n = 1; n <= N; n++) win[w][n] = countIn(D, idx, w, n);
  }
  // 1) 기간별 공통 강세: 세 기간 각각 상위 15위 안 (동점 포함)
  const topSet = w => {
    const sorted = Object.values(win[w]).sort((a, b) => b - a);
    const cut = sorted[14];
    const s = new Set();
    for (let n = 1; n <= N; n++) if (win[w][n] >= cut) s.add(n);
    return s;
  };
  const t1 = topSet(W1Y), t6 = topSet(W6M), t3 = topSet(W3M);
  const multi = {};
  const mx = w => Math.max(...Object.values(win[w])) || 1;
  const m1y = mx(W1Y), m6 = mx(W6M), m3 = mx(W3M);
  for (let n = 1; n <= N; n++) multi[n] = (win[W1Y][n] / m1y + win[W6M][n] / m6 + win[W3M][n] / m3) / 3;
  const consensus = [];
  for (let n = 1; n <= N; n++) if (t1.has(n) && t6.has(n) && t3.has(n)) consensus.push(n);

  // 3) 제외번호
  const excluded = new Set();
  const reasons = [];
  for (let n = 1; n <= N; n++) if (countIn(D, idx, W1M, n) >= 4) excluded.add(n);
  if (excluded.size) reasons.push('최근 1개월 4회 이상 출현');
  let weak = [];
  if (withPatterns) {
    weak = findWeakPatterns(D, idx);
    const extra = new Set();
    for (let n = 1; n <= N; n++) {
      const pk = patternKey(D, idx, n);
      if (Object.entries(pk).some(([dim, val]) => weak.includes(dim + ':' + val))) extra.add(n);
    }
    if (extra.size && extra.size <= 12) { // 너무 많이 빠지면 적용하지 않음
      for (const n of extra) excluded.add(n);
      reasons.push('다음 회차 출현율이 낮은 단기 패턴(' + weak.join(', ') + ')');
    }
  }

  // 점수
  const lastIdx = idx;
  const adj = {};
  for (let n = 1; n <= N; n++) adj[n] = 0;
  for (const n of D[lastIdx]) for (let d = -2; d <= 2; d++) {
    const m = n + d;
    if (m >= 1 && m <= N) adj[m] += (2 - Math.abs(d)) * 0.5;
  }
  const gap = {};
  for (let n = 1; n <= N; n++) gap[n] = idx - lastSeen[n];
  const maxF = Math.max(...Object.values(freqAll)) || 1;
  const maxG = Math.max(...Object.values(gap)) || 1;
  const maxA = Math.max(...Object.values(adj)) || 1;
  const weights = {};
  for (let n = 1; n <= N; n++) {
    const s = 0.15 * freqAll[n] / maxF + 0.35 * multi[n] + 0.25 * gap[n] / maxG + 0.25 * adj[n] / maxA
      - (D[lastIdx].has(n) ? 0.08 : 0);
    weights[n] = Math.max(s, 0.01);
  }

  // 핵심번호 후보 점수: 공통 강세 우선
  const coreScore = {};
  for (let n = 1; n <= N; n++) coreScore[n] = multi[n] + (consensus.includes(n) ? 0.5 : 0);
  return { weights, excluded, reasons, consensus, coreScore, weak };
}

function pickCore(D, idx, info, prevCores, round) {
  const rng = mulberry32(round * 104729 + 7);
  const resting = new Set();
  for (let j = Math.max(0, idx - REST + 1); j <= idx; j++) for (const n of D[j]) resting.add(n);
  const banned = new Set([...info.excluded, ...prevCores.flat(), ...resting]);
  // 공통 강세 번호 중 후보 → 부족하면 강세 점수 상위 번호로 채워 최소 6개
  let pool = info.consensus.filter(n => !banned.has(n));
  const rest = [];
  for (let n = 1; n <= N; n++) if (!banned.has(n) && !pool.includes(n)) rest.push(n);
  rest.sort((a, b) => info.coreScore[b] - info.coreScore[a]);
  while (pool.length < 6 && rest.length) pool.push(rest.shift());
  pool.sort((a, b) => info.coreScore[b] - info.coreScore[a]);
  pool = pool.slice(0, 8);
  const core = [];
  while (core.length < 3) {
    const cand = pool.filter(n => !core.includes(n));
    core.push(cand[weightedPick(cand, n => info.coreScore[n] + 0.05, rng)]);
  }
  return core.sort((a, b) => a - b);
}

function recommend(draws) {
  draws = [...draws].sort((a, b) => a.draw_no - b.draw_no);
  const D = draws.map(d => new Set(d.numbers));
  const idx = D.length - 1;
  const currentRound = draws[idx].draw_no;
  const nextRound = currentRound + 1;

  // 2) 핵심번호 순환: 기준 회차부터 차례로 핵심번호를 재계산 (상태 저장 없이 항상 같은 결과)
  const cores = [];
  const startIdx = Math.max(13, draws.findIndex(d => d.draw_no === ROTATION_ANCHOR - 1));
  for (let i = startIdx >= 0 ? startIdx : idx; i <= idx; i++) {
    const info = analyze(D, i, i === idx);
    const core = pickCore(D, i, info, cores.slice(-CORE_ROTATION), draws[i].draw_no + 1);
    cores.push(core);
    if (i === idx) var finalInfo = info;
  }
  const core = cores[cores.length - 1];
  const prevCores = cores.slice(-1 - CORE_ROTATION, -1);
  const info = finalInfo;
  const weights = info.weights;

  const historySets = new Set(draws.map(d => JSON.stringify([...d.numbers].sort((a, b) => a - b))));
  function validCombo(s) {
    const odds = s.filter(x => x % 2 === 1).length;
    if (odds < 2 || odds > 4) return false;
    const total = s.reduce((a, b) => a + b, 0);
    if (total < 100 || total > 175) return false;
    let consec = 1, maxConsec = 1;
    for (let i = 1; i < s.length; i++) {
      if (s[i] === s[i - 1] + 1) { consec += 1; maxConsec = Math.max(maxConsec, consec); } else consec = 1;
    }
    if (maxConsec > 2) return false;
    if (new Set(s.map(x => Math.floor((x - 1) / 10))).size < 3) return false;
    if (historySets.has(JSON.stringify(s))) return false; // 역대 1등 조합 제외
    return true;
  }

  const rng = mulberry32(nextRound * 7919 + 13);
  function fillSet(fixed, banned) {
    const chosen = [...fixed];
    const pool = [];
    for (let n = 1; n <= N; n++) if (!chosen.includes(n) && !banned.includes(n) && !info.excluded.has(n)) pool.push(n);
    while (chosen.length < 6) {
      const i = weightedPick(pool, n => weights[n], rng);
      chosen.push(pool[i]);
      pool.splice(i, 1);
    }
    return chosen.sort((a, b) => a - b);
  }
  const shared = (a, b) => a.filter(x => b.includes(x)).length;
  function buildSets(maxShared) {
    const [c1, c2, c3] = core;
    const plan = [
      { fixed: [c1, c2, c3], banned: [] },
      { fixed: [c1, c2, c3], banned: [] },
      { fixed: [c1, c2], banned: [c3] },
      { fixed: [c2, c3], banned: [c1] },
      { fixed: [], banned: [c1, c2, c3] },
    ];
    const out = [];
    for (const step of plan) {
      let ok = null;
      for (let t = 0; t < 4000 && !ok; t++) {
        const s = fillSet(step.fixed, step.banned);
        if (!validCombo(s)) continue;
        if (out.some(o => JSON.stringify(o) === JSON.stringify(s) || shared(o, s) > maxShared)) continue;
        ok = s;
      }
      if (!ok) return null;
      out.push(ok);
    }
    return out;
  }
  const results = buildSets(3) || buildSets(4);
  if (!results) throw new Error('조건에 맞는 5세트를 만들지 못했습니다');

  const drawDate = new Date(draws[idx].date);
  const next = new Date(drawDate);
  next.setDate(next.getDate() + 7);
  const dateStr = `${next.getFullYear()}.${String(next.getMonth() + 1).padStart(2, '0')}.${String(next.getDate()).padStart(2, '0')}`;

  const excludedList = [...info.excluded].sort((a, b) => a - b);
  const lines = results.map((r, i) => `${i + 1}세트: ${r.join(', ')}`);
  let notes = `핵심번호: ${core.join(', ')}\n(1년·6개월·3개월 공통 강세 + 최근 2주 쉬는 번호, 1~4세트 공유)`;
  if (excludedList.length) notes += `\n제외번호: ${excludedList.join(', ')}`;
  const message =
    `[로또 ${nextRound}회 추천번호]\n` +
    `${dateStr}(토) 추첨분\n\n` +
    lines.join('\n') + '\n\n' + notes +
    `\n\n과거 당첨 데이터 패턴 분석 기반 참고용 조합이며,\n` +
    `당첨을 보장하지 않습니다. 즐거운 한 주 되세요!`;

  return {
    round: nextRound, draw_date: dateStr, core, prev_cores: prevCores,
    consensus: info.consensus, excluded: excludedList, exclude_reasons: info.reasons,
    weak_patterns: info.weak, sets: results, message,
  };
}

async function main() {
  const fs = require('fs');
  let draws;
  for (let i = 0; i < 3; i++) {
    try {
      const r = await fetch('https://smok95.github.io/lotto/results/all.json');
      if (!r.ok) throw new Error('HTTP ' + r.status);
      draws = await r.json();
      break;
    } catch (e) {
      console.log('[lotto data] 실패:', e.message);
      await new Promise(res => setTimeout(res, 3000 * (i + 1)));
    }
  }
  if (!draws) throw new Error('로또 당첨 데이터를 가져오지 못했습니다');
  const out = recommend(draws);
  console.log(out.message);
  console.log('[참고] 공통 강세:', out.consensus.join(','), '| 직전 핵심번호:', JSON.stringify(out.prev_cores),
    '| 약한 패턴:', out.weak_patterns.join(',') || '없음');
  fs.writeFileSync('lotto_out.json', JSON.stringify(out, null, 2));
}

if (typeof module !== 'undefined' && require.main === module) {
  main().catch(e => { console.error(e); process.exit(1); });
} else if (typeof module !== 'undefined') {
  module.exports = { recommend };
}
