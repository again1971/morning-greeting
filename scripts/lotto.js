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
//  5) 구간 배분 (2026-10-16 추가): 1~9 / 10~19 / 20~29 / 30~39 / 40~45 다섯 구간 기준
//     - 한 구간 최대 3개, 빈 구간 최대 2개 (역대 당첨번호의 약 94%가 이 범위)
//     - 5세트 모양을 역대 비율대로: 빈 구간 0개 1세트, 1개 3세트, 2개 1세트
//       (역대: 0개 12%, 1개 53%, 2개 32%)
//  6) 구간 집중 주기 (2026-10-19 추가, 1246회 20번대 5개 몰림 이후 어게인님 제안)
//     - '집중' = 한 구간에 4개 이상. 매주 역대 데이터로 다시 계산:
//       ① 마지막 집중 후 몇 회 지났는지 → 그 간격대에서 실제로 집중이 나온 비율(도래확률)
//       ② 마지막 집중 구간 → 다음 집중 구간 전이 비율(어느 번대에 몰릴지)
//       ③ 집중 직후 회차의 모양(직후엔 분산형이 많음: 빈 구간 1개 61%)
//     - 도래확률이 역대 평균(약 5.8%) 이상이면 5세트를 '집중 대비 세트'로: 예상 구간에 4개 + 다른 구간 2개
//       (역대 집중 모양 4-1-1 65%, 4-2 26%), 집중 직후·장기 공백 구간처럼 낮으면 기존 규칙 그대로
//  유지: 역대 1등 조합 제외, 홀짝·합계·연속 필터, 핵심번호 공유 5세트 구조, 세트 간 공통 최대 3개
const N = 45;
const BASELINE = 6 / 45;
const W1Y = 52, W6M = 26, W3M = 13, W1M = 4, REST = 2;
const CORE_ROTATION = 2;          // 직전 몇 회차의 핵심번호를 이번에 제외할지
const ROTATION_ANCHOR = 1243;     // 순환 계산 시작 회차 (이 회차부터 결정적으로 재계산)
const zoneOf = n => (n <= 9 ? 0 : n <= 19 ? 1 : n <= 29 ? 2 : n <= 39 ? 3 : 4);
function zoneCounts(s) {
  const z = [0, 0, 0, 0, 0];
  for (const n of s) z[zoneOf(n)]++;
  return z;
}

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

// ---- 6) 구간 집중 주기 분석 ----
const ZONE_NAMES = ['1~9', '10번대', '20번대', '30번대', '40번대'];
const GAP_BINS = [[1, 1], [2, 5], [6, 10], [11, 15], [16, 20], [21, 30], [31, 9999]];
function concentrationInfo(draws, idx) {
  const zs = draws.slice(0, idx + 1).map(d => zoneCounts(d.numbers));
  const ev = [];
  zs.forEach((z, i) => { if (Math.max(...z) >= 4) ev.push(i); });
  const topZone = i => zs[i].indexOf(Math.max(...zs[i]));
  const avg = ev.length / zs.length;
  if (ev.length < 10) return { apply: false, avg, prob: avg, gap: null };
  const gaps = ev.slice(1).map((v, i) => v - ev[i]);
  const gap = idx - ev[ev.length - 1] + 1;      // 다음 회차가 마지막 집중 후 몇 번째인지
  const bin = GAP_BINS.find(([lo, hi]) => gap >= lo && gap <= hi);
  let risk = 0, hit = 0;
  for (const g of gaps) for (let k = bin[0]; k <= bin[1]; k++) { if (g >= k) risk++; if (g === k) hit++; }
  const prob = (hit + avg * 5) / (risk + 5);      // 표본이 적으면 평균 쪽으로 당김
  // 전이: 마지막 집중 구간 → 다음 집중 구간 (전체 비율로 보정)
  const base = [0, 0, 0, 0, 0];
  ev.forEach(i => base[topZone(i)]++);
  const last = topZone(ev[ev.length - 1]);
  const tr = [0, 0, 0, 0, 0];
  for (let i = 1; i < ev.length; i++) if (topZone(ev[i - 1]) === last) tr[topZone(ev[i])]++;
  const trTot = tr.reduce((a, b) => a + b, 0);
  const zoneProb = tr.map((c, k) => (c + 5 * base[k] / ev.length) / (trTot + 5));
  const zone = zoneProb.indexOf(Math.max(...zoneProb));
  return {
    apply: prob >= avg, avg, prob, gap, lastRound: draws[ev[ev.length - 1]].draw_no,
    lastZone: last, zone, zoneProb,
  };
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
    // 핵심번호 3개가 연속(예: 7,8,9)이면 '연속 최대 2' 필터에 걸려 세트를 못 만드므로 제외
    const run3 = n => { const t = [...core, n].sort((a, b) => a - b); return t.length === 3 && t[1] === t[0] + 1 && t[2] === t[1] + 1; };
    let cand = pool.filter(n => !core.includes(n) && !run3(n));
    if (!cand.length) cand = pool.filter(n => !core.includes(n));
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
  const conc = concentrationInfo(draws, idx);
  function validCombo(s, concZone) {
    const odds = s.filter(x => x % 2 === 1).length;
    if (odds < 2 || odds > 4) return false;
    const total = s.reduce((a, b) => a + b, 0);
    if (total < 100 || total > 175) return false;
    let consec = 1, maxConsec = 1;
    for (let i = 1; i < s.length; i++) {
      if (s[i] === s[i - 1] + 1) { consec += 1; maxConsec = Math.max(maxConsec, consec); } else consec = 1;
    }
    if (maxConsec > 2) return false;
    const z = zoneCounts(s);
    if (concZone !== undefined) {                          // 집중 대비 세트: 지정 구간 정확히 4개
      if (z[concZone] !== 4 || z.some((v, k) => k !== concZone && v > 2)) return false;
    } else {
      if (Math.max(...z) > 3) return false;                  // 한 구간 최대 3개
      if (z.filter(v => v === 0).length > 2) return false;  // 빈 구간 최대 2개
    }
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
  function fillConc(zone, banned) {
    const pick = (cands, k) => {
      const pool = cands.filter(n => !banned.includes(n) && !info.excluded.has(n));
      const out = [];
      while (out.length < k && pool.length) { const i = weightedPick(pool, n => weights[n], rng); out.push(pool[i]); pool.splice(i, 1); }
      return out;
    };
    const inZ = [], outZ = [];
    for (let n = 1; n <= N; n++) (zoneOf(n) === zone ? inZ : outZ).push(n);
    return [...pick(inZ, 4), ...pick(outZ, 2)].sort((a, b) => a - b);
  }
  const shared = (a, b) => a.filter(x => b.includes(x)).length;
  function buildSets(maxShared, useShape, useConc = conc.apply) {
    const [c1, c2, c3] = core;
    // empty: 이 세트의 빈 구간 개수 목표 (역대 비율대로 0개 1세트, 1개 3세트, 2개 1세트)
    const plan = [
      { fixed: [c1, c2, c3], banned: [], empty: 1 },
      { fixed: [c1, c2, c3], banned: [], empty: 0 },
      { fixed: [c1, c2], banned: [c3], empty: 1 },
      { fixed: [c2, c3], banned: [c1], empty: 2 },
      useConc
        ? { fixed: [], banned: [c1, c2, c3], conc: conc.zone }
        : { fixed: [], banned: [c1, c2, c3], empty: 1 },
    ];
    const out = [];
    for (const step of plan) {
      let ok = null;
      for (let t = 0; t < 4000 && !ok; t++) {
        const s = step.conc !== undefined ? fillConc(step.conc, step.banned) : fillSet(step.fixed, step.banned);
        if (s.length !== 6 || !validCombo(s, step.conc)) continue;
        if (useShape && step.conc === undefined && zoneCounts(s).filter(v => v === 0).length !== step.empty) continue;
        if (out.some(o => JSON.stringify(o) === JSON.stringify(s) || shared(o, s) > maxShared)) continue;
        ok = s;
      }
      if (!ok) return null;
      out.push(ok);
    }
    return out;
  }
  let results = buildSets(3, true) || buildSets(4, true) || buildSets(3, false) || buildSets(4, false);
  if (!results && conc.apply) {           // 집중 대비 세트를 못 만들면 기존 규칙으로
    conc.apply = false;
    results = buildSets(3, true, false) || buildSets(4, true, false) || buildSets(3, false, false) || buildSets(4, false, false);
  }
  if (!results) throw new Error('조건에 맞는 5세트를 만들지 못했습니다');

  const drawDate = new Date(draws[idx].date);
  const next = new Date(drawDate);
  next.setDate(next.getDate() + 7);
  const dateStr = `${next.getFullYear()}.${String(next.getMonth() + 1).padStart(2, '0')}.${String(next.getDate()).padStart(2, '0')}`;

  const excludedList = [...info.excluded].sort((a, b) => a - b);
  const lines = results.map((r, i) => `${i + 1}세트: ${r.join(', ')}  [${zoneCounts(r).join('-')}]`);
  let notes = `핵심번호: ${core.join(', ')}\n(1년·6개월·3개월 공통 강세 + 최근 2주 쉬는 번호, 1~4세트 공유)`;
  if (excludedList.length) notes += `\n제외번호: ${excludedList.join(', ')}`;
  const pct = v => (v * 100).toFixed(1) + '%';
  if (conc.gap !== null) {
    notes += `\n구간 집중: 마지막 ${conc.lastRound}회(${ZONE_NAMES[conc.lastZone]}) 후 ${conc.gap}번째 회차, 도래확률 ${pct(conc.prob)}(평균 ${pct(conc.avg)})`;
    notes += conc.apply
      ? `\n→ 5세트는 집중 대비 세트(${ZONE_NAMES[conc.zone]} 4개, 예상 ${pct(conc.zoneProb[conc.zone])})`
      : `\n→ 도래확률이 낮아 집중 대비 세트 없이 분산형으로 구성`;
  }
  notes += `\n[ ]는 구간별 개수 (1~9 / 10번대 / 20번대 / 30번대 / 40번대)`;
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
    concentration: { ...conc, set_index: conc.apply ? 4 : null },
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
