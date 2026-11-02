// report.js — 게시물별 「자료 발송 건수」를 슬랙 DM(유삐 봇)으로 보고한다.
// 평일 18:30 하루 1회 작업 스케줄러가 부른다(2026-10-06 · 옛 하루 4회).
//
// 세는 값 = sent.json 의 글별 수신자 수(= 실제 메일이 나간 횟수, 중복 제외).
// watch.js 와 같은 weekLink 규칙으로 「발송 대상 글」만 추린다 — 규칙이 갈리면
// 화면엔 0건인데 실제로는 나가는(또는 그 반대) 상태가 조용히 생긴다.
//
// 사용: node report.js            실제 발송
//       node report.js --dry-run  발송 없이 본문만 출력
//       node report.js --self-test 로그인 없이 본문 조립만 점검
const fs = require('fs');
const path = require('path');
const { postSlack } = require('./alert.js');
const { weekLink } = require('./watch.js');

const SENT = path.join(__dirname, 'sent.json');
const kst = () => new Date(Date.now() + 324e5).toISOString().slice(0, 16).replace('T', ' ');

function buildText(posts, sent) {
  const targets = posts.filter((p) => weekLink(p.title));
  const seen = new Set(targets.map((p) => p.artNo));
  // 목록에서 밀려난 글도 셈에서 빠지면 안 된다 — 제목은 못 붙여도 건수는 남긴다.
  for (const artNo of Object.keys(sent)) {
    if (!seen.has(artNo)) targets.push({ artNo, title: `(제목 확인 필요 · artNo ${artNo})` });
  }

  const lines = targets.map((p) => {
    const to = sent[p.artNo] || [];
    const who = to.length ? `  \u2014 ${to.map((e) => e.split('@')[0]).join(', ')}` : '';
    return `\u2022 ${p.title} : *${to.length}건*${who}`;
  });
  const total = targets.reduce((n, p) => n + (sent[p.artNo] || []).length, 0);

  return [
    '*<AI자동화 자료 전송 현황>*',
    `\u2022 시각 : ${kst()} (KST)`,
    `\u2022 대상 글 : ${targets.length}건 / 누적 발송 : ${total}건`,
    '',
    ...(lines.length ? lines : ['\u2022 발송 대상 글이 없습니다.']),
  ].join('\n');
}

async function run() {
  const sent = JSON.parse(fs.readFileSync(SENT, 'utf8'));
  const { login } = require('./login.js');
  const { listPosts } = require('./board.js');
  const posts = await listPosts(await login());
  const text = buildText(posts, sent);

  if (process.argv.includes('--dry-run')) { console.log(text); console.log('\n[dry-run] 발송하지 않았습니다.'); return; }
  console.log((await postSlack(text)) ? '발송 완료' : '발송 안 됨');
}

module.exports = { buildText };

if (require.main === module) {
  if (process.argv.includes('--self-test')) {
    const assert = require('assert');
    const t = buildText(
      [{ artNo: '1', title: '9월 두번째 공유 - AI자동화 사례' }, { artNo: '9', title: '공지사항' }],
      { 1: ['a@askwhy.co.kr', 'b@askwhy.co.kr'], 7: ['c@askwhy.co.kr'] }
    );
    assert(t.includes('9월 두번째 공유 - AI자동화 사례 : *2건*'), '대상 글 건수');
    assert(t.includes('a, b'), '수신자 로컬파트');
    assert(!t.includes('공지사항'), '주차 형식 아닌 글은 제외');
    assert(t.includes('artNo 7') && t.includes('artNo 7) : *1건*'), '목록에 없는 글도 건수는 남긴다');
    assert(t.includes('대상 글 : 2건 / 누적 발송 : 3건'), '합계');
    console.log(t + '\n\nself-test OK');
    process.exit(0);
  }
  run().catch((e) => { console.error('오류: ' + e.message); process.exit(1); });
}
