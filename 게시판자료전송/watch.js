// watch.js — AI자동화 공유 게시판 감시 → 댓글의 @askwhy.co.kr 메일로 주차 링크 발송.
// 한 번 실행 = 한 바퀴 점검. 반복은 스케줄러(작업 스케줄러)로 평일 30분마다.
// 사용: node watch.js            실제 발송
//       node watch.js --dry-run  발송·기록 없이 무엇을 보낼지만 출력
const fs = require('fs');
const path = require('path');
const { login } = require('./login.js');
const { listPosts } = require('./board.js');
const { getComments } = require('./get_comments.js');
const { alert } = require('./alert.js');
const cfg = require('./config.json');

const DRY = process.argv.includes('--dry-run');
const SENT = path.join(__dirname, 'sent.json');
const EMAIL_RE = /[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/g;

const LOG_FILE = path.join(__dirname, 'watch.log');
const log = (m) => {
  const line = `[${new Date(Date.now() + 324e5).toISOString().slice(0, 19).replace('T', ' ')}] ${m}`;
  console.log(line);
  try { fs.appendFileSync(LOG_FILE, line + '\n'); } catch {}
};
const loadSent = () => { try { return JSON.parse(fs.readFileSync(SENT, 'utf8')); } catch { return {}; } };
const saveSent = (o) => fs.writeFileSync(SENT, JSON.stringify(o, null, 2), 'utf8');

// 제목 "N월 M주차" → { key, url, rnd }.  매핑 없으면 url=null.
// 제목에서 기계 키를 뽑는다. 두 형식을 다 받는다 (2026-09-21 「N번째 공유」 추가).
//   "9월 2주차 ..."        → 9-2      (주차 = 달력 주)
//   "9월 첫번째 공유 ..."  → 9-1      (번째 = 그 달의 N번째 공유)
// ⚠️ 두 형식은 같은 키 공간을 쓴다 — 한 달 안에서 섞어 쓰면 9월 2주차와 9월 두번째가
//    같은 "9-2" 가 되어 엉뚱한 회차 링크가 조용히 나간다. 달마다 한 형식만 쓸 것.
const 서수 = { 첫: 1, 두: 2, 세: 3, 네: 4, 다섯: 5, 여섯: 6 };

function weekLink(title) {
  const m = title.match(/(\d+)\s*월\s*(?:(\d+)\s*주차|(\d+|첫|두|세|네|다섯|여섯)\s*번째)/);
  if (!m) return null;
  const n = m[2] ? +m[2] : (서수[m[3]] ?? +m[3]);
  const key = `${+m[1]}-${n}`;
  const rnd = cfg.주차매핑[key];
  // 값이 http(s) 로 시작하면 그 주소를 그대로 쓴다 — 회차 산출물이 아닌 자료(예: AX_study 교육가이드)용.
  const url = !rnd ? null : (/^https?:\/\//.test(rnd) ? rnd : cfg.github링크형식.replace(/\{회차\}/g, rnd));
  return { key, rnd, url };
}

async function run() {
  // 중지 스위치 — config.json 의 "중지": true 면 한 바퀴도 돌지 않는다. (2026-09-21)
  if (cfg.중지) { log('중지 상태 — config.json 의 "중지": false 로 바꾸면 재개'); process.exit(0); }

  const s = await login();
  const posts = await listPosts(s);
  const sent = loadSent();
  let sends = 0;

  for (const p of posts) {
    const link = weekLink(p.title);
    if (!link) continue; // 'N월 M주차' 형식 아닌 글은 무시

    const comments = await getComments(s, p.artNo);
    const emails = new Set();
    for (const c of comments) {
      for (const e of (c.contents || '').match(EMAIL_RE) || []) {
        if (e.toLowerCase().endsWith('@' + cfg.허용도메인.toLowerCase())) emails.add(e.toLowerCase());
      }
    }
    const already = new Set(sent[p.artNo] || []);
    const fresh = [...emails].filter((e) => !already.has(e));
    if (fresh.length === 0) continue;

    if (!link.url) {
      log(`[스킵] "${p.title}" — 주차 ${link.key} 링크 매핑 없음. config.json 주차매핑에 추가 필요. 대상: ${fresh.join(', ')}`);
      // 요청은 왔는데 링크가 없다 = 사람이 손볼 때까지 아무도 못 받는다. 알려야 한다.
      if (!DRY) await alert('주차매핑 누락', `"${p.title}" 의 주차 ${link.key} 링크 매핑이 없어 발송 못 함`,
        [`대기 중 : ${fresh.join(', ')} (${fresh.length}명)`,
         `조치 : config.json 주차매핑에 "${link.key}": "<회차YYYYMMDD>" 추가 (해당 회차 GitHub 발행 선행)`]);
      continue;
    }
    for (const e of fresh) {
      if (DRY) {
        log(`[dry] 발송예정 → ${e} | ${link.url}`);
      } else {
        try {
          await require('./mailer.js').sendLink(e, cfg.메일제목형식.replace('{제목}', p.title), link.url, p.title);
        } catch (err) {
          // 한 명 실패가 나머지 수신자까지 막으면 안 된다. 기록·알림만 하고 다음 사람으로.
          log(`[실패] ${e} — ${err.message}`);
          await alert('메일 발송', `${e} 발송 실패 — ${err.message}`,
            [`대상 글 : ${p.title}`, '조치 : 다음 회차에 자동 재시도(발송기록 안 남김)']);
          continue;
        }
        already.add(e);
        log(`[발송] ${e} ← ${link.key} ${link.url}`);
        sends++;
      }
    }
    if (!DRY) sent[p.artNo] = [...already];
  }

  if (!DRY) saveSent(sent);
  log(DRY ? 'dry-run 종료 (발송·기록 없음)' : `완료: ${sends}건 발송`);
  process.exit(0);
}

module.exports = { weekLink };   // report.js 가 「발송 대상 글」 판정에 같은 규칙을 쓴다

if (require.main === module) run().catch(async (e) => {
  log('오류: ' + e.message);
  // 로그인·게시판 조회 등 한 바퀴가 통째로 깨진 경우. 알림 실패는 무시하고 종료코드는 유지.
  if (!DRY) await alert('watch.js', e.message, ['조치 : 일시적 접속 실패면 다음 회차에 자동 복구']);
  process.exit(1);
});
