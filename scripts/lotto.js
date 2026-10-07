// 로또 번호 추천 (n8n "로또 번호 추천 카카오톡 발송" 워크플로우의 Code 노드를 그대로 옮김)
// 사용법: node scripts/lotto.js  → lotto_out.json 에 메시지 저장
const fs = require('fs');

async function main() {
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

  // ---- 여기부터 n8n Code 노드와 동일 ----
  draws.sort((a, b) => a.draw_no - b.draw_no);

  const currentRound = draws[draws.length - 1].draw_no;
  const nextRound = currentRound + 1;
  const N = 45;

  const freq = {};
  const lastSeen = {};
  const historySets = new Set();
  for (let i = 1; i <= N; i++) { freq[i] = 0; lastSeen[i] = 0; }

  for (const d of draws) {
    const nums = d.numbers;
    historySets.add(JSON.stringify([...nums].sort((a, b) => a - b)));
    for (const n of nums) {
      freq[n] += 1;
      lastSeen[n] = d.draw_no;
    }
  }

  const RECENT_W = 20;
  const recentDraws = draws.slice(-RECENT_W);
  const recentFreq = {};
  for (let i = 1; i <= N; i++) recentFreq[i] = 0;
  for (const d of recentDraws) for (const n of d.numbers) recentFreq[n] += 1;

  const lastDraw = draws[draws.length - 1].numbers;
  const prevDraw = draws[draws.length - 2].numbers;
  const overlap = lastDraw.filter(n => prevDraw.includes(n)).length;

  const adjacencyBonus = {};
  for (let i = 1; i <= N; i++) adjacencyBonus[i] = 0;
  for (const n of lastDraw) {
    for (let d = -2; d <= 2; d++) {
      const m = n + d;
      if (m >= 1 && m <= N) adjacencyBonus[m] += (2 - Math.abs(d)) * 0.5;
    }
  }

  const gap = {};
  for (let i = 1; i <= N; i++) gap[i] = currentRound - lastSeen[i];

  const maxFreq = Math.max(...Object.values(freq));
  const maxRecent = Math.max(...Object.values(recentFreq)) || 1;
  const maxGap = Math.max(...Object.values(gap)) || 1;
  const maxAdj = Math.max(...Object.values(adjacencyBonus)) || 1;

  const weights = {};
  for (let i = 1; i <= N; i++) {
    const fN = freq[i] / maxFreq;
    const rN = recentFreq[i] / maxRecent;
    const gN = gap[i] / maxGap;
    const aN = maxAdj ? adjacencyBonus[i] / maxAdj : 0;
    const repeatPenalty = lastDraw.includes(i) ? 0.35 : 0;
    const score = 0.30 * fN + 0.20 * rN + 0.30 * gN + 0.20 * aN - repeatPenalty;
    weights[i] = Math.max(score, 0.01);
  }

  function validCombo(sArr) {
    const s = [...sArr].sort((a, b) => a - b);
    const odds = s.filter(x => x % 2 === 1).length;
    if (odds < 2 || odds > 4) return false;
    const total = s.reduce((a, b) => a + b, 0);
    if (total < 100 || total > 175) return false;
    let consec = 1, maxConsec = 1;
    for (let i = 1; i < s.length; i++) {
      if (s[i] === s[i - 1] + 1) { consec += 1; maxConsec = Math.max(maxConsec, consec); }
      else consec = 1;
    }
    if (maxConsec > 2) return false;
    const bands = new Set(s.map(x => Math.floor((x - 1) / 10)));
    if (bands.size < 3) return false;
    if (historySets.has(JSON.stringify(s))) return false;
    return true;
  }

  // simple seeded RNG (mulberry32) so results are reproducible per round
  function mulberry32(seed) {
    return function () {
      let t = (seed += 0x6D2B79F5);
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  const rng = mulberry32(nextRound * 7919 + 13);

  function weightedSample() {
    let pool = [];
    for (let i = 1; i <= N; i++) pool.push(i);
    let wt = pool.map(i => weights[i]);
    const chosen = [];
    for (let k = 0; k < 6; k++) {
      const total = wt.reduce((a, b) => a + b, 0);
      const r = rng() * total;
      let upto = 0, idx = 0;
      for (; idx < wt.length; idx++) {
        upto += wt[idx];
        if (upto >= r) break;
      }
      chosen.push(pool[idx]);
      pool.splice(idx, 1);
      wt.splice(idx, 1);
    }
    return chosen;
  }

  // ---- 5세트 구성: 핵심번호(고정수) 공유 + 세트 간 중복 제한 (2026-10-07 개편) ----
  // 1등이 최종 목표지만 2·3등도 함께 노리기 위해, 점수 상위 '핵심번호' 3개를 여러 세트에 공유한다.
  //  - 1·2세트: 핵심번호 3개 모두 포함 (핵심번호가 나오는 회차에 여러 장이 동시에 등수권에 들도록)
  //  - 3·4세트: 핵심번호 중 2개씩 (서로 다른 짝)
  //  - 5세트  : 핵심번호 없이 완전히 다른 조합 (핵심번호가 빗나갈 때의 보험)
  //  - 어떤 두 세트도 공통 번호는 최대 3개 → 너무 몰리지 않게 분산
  const MAX_SHARED = 3;
  const ranked = Object.keys(weights).map(Number).sort((a, b) => weights[b] - weights[a]);

  // 핵심번호: 점수 상위 8개 중에서 가중치 비례로 3개 (매주 조금씩 달라지도록)
  function pickCore() {
    const pool = ranked.slice(0, 8);
    const core = [];
    while (core.length < 3) {
      const cand = pool.filter(n => !core.includes(n));
      const total = cand.reduce((a, n) => a + weights[n], 0);
      let r = rng() * total, idx = 0;
      for (; idx < cand.length - 1; idx++) { r -= weights[cand[idx]]; if (r <= 0) break; }
      core.push(cand[idx]);
    }
    return core.sort((a, b) => a - b);
  }

  // fixed 번호를 포함하고, banned 번호는 빼고, 나머지를 가중치 샘플링으로 채움
  function fillSet(fixed, banned) {
    const chosen = [...fixed];
    let pool = [];
    for (let i = 1; i <= N; i++) if (!chosen.includes(i) && !banned.includes(i)) pool.push(i);
    let wt = pool.map(i => weights[i]);
    while (chosen.length < 6) {
      const total = wt.reduce((a, b) => a + b, 0);
      const r = rng() * total;
      let upto = 0, idx = 0;
      for (; idx < wt.length; idx++) { upto += wt[idx]; if (upto >= r) break; }
      if (idx >= pool.length) idx = pool.length - 1;
      chosen.push(pool[idx]);
      pool.splice(idx, 1); wt.splice(idx, 1);
    }
    return chosen.sort((a, b) => a - b);
  }

  const sharedCount = (a, b) => a.filter(x => b.includes(x)).length;

  function buildSets(core, maxShared) {
    const [c1, c2, c3] = core;
    const plan = [
      { fixed: [c1, c2, c3], banned: [] },
      { fixed: [c1, c2, c3], banned: [] },
      { fixed: [c1, c2], banned: [c3] },
      { fixed: [c2, c3], banned: [c1] },
      { fixed: [], banned: [c1, c2, c3] },
    ];
    const out = [];
    const keys = new Set();
    for (const step of plan) {
      let ok = null;
      for (let t = 0; t < 4000 && !ok; t++) {
        const s = fillSet(step.fixed, step.banned);
        const key = JSON.stringify(s);
        if (keys.has(key) || !validCombo(s)) continue;
        if (out.some(o => sharedCount(o, s) > maxShared)) continue;
        ok = s;
      }
      if (!ok) return null;
      out.push(ok);
      keys.add(JSON.stringify(ok));
    }
    return out;
  }

  let core = null;
  let results = null;
  for (let tries = 0; tries < 30 && !results; tries++) {
    core = pickCore();
    results = buildSets(core, MAX_SHARED);
  }
  if (!results) { // 안전장치: 조건을 조금 완화
    for (let tries = 0; tries < 30 && !results; tries++) {
      core = pickCore();
      results = buildSets(core, MAX_SHARED + 1);
    }
  }
  if (!results) throw new Error('조건에 맞는 5세트를 만들지 못했습니다');

  const drawDate = new Date(draws[draws.length - 1].date);
  const nextDrawDate = new Date(drawDate);
  nextDrawDate.setDate(nextDrawDate.getDate() + 7);
  const dateStr = `${nextDrawDate.getFullYear()}.${String(nextDrawDate.getMonth() + 1).padStart(2, '0')}.${String(nextDrawDate.getDate()).padStart(2, '0')}`;

  const lines = results.map((r, i) => `${i + 1}세트: ${r.join(', ')}`);
  const coreLine = `핵심번호: ${core.join(', ')} (1~4세트에 공유, 5세트는 별도 조합)`;
  const message =
    `[로또 ${nextRound}회 추천번호]\n` +
    `${dateStr}(토) 추첨분\n\n` +
    lines.join('\n') + '\n\n' + coreLine +
    `\n\n과거 당첨 데이터 패턴 분석 기반 참고용 조합이며,\n` +
    `당첨을 보장하지 않습니다. 즐거운 한 주 되세요!`;
  // ---- 여기까지 n8n Code 노드와 동일 ----

  console.log(message);
  fs.writeFileSync('lotto_out.json', JSON.stringify({ round: nextRound, draw_date: dateStr, core, sets: results, message }, null, 2));
}

main().catch(e => { console.error(e); process.exit(1); });
