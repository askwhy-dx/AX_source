// get_comments.js — 글(artNo)의 댓글 목록을 가져온다.
// 체인: viewPost.do(commentKey) → /gw/comment.do(암호화 moduleSeq) → /gw/api/SearchCommentList.do
// 사용: node get_comments.js [artNo] [boardNo]   (기본 104506 / 900000288)
const fs = require('fs');
const { login } = require('./login.js');
const BASE = 'https://gwa.askwhy.co.kr';

async function getComments(s, artNo, boardNo) {
  // 1) 상세 페이지에서 commentKey 추출
  const detailUrl = `${BASE}/edms/board/viewPost.do?currentPage=1&boardNo=${boardNo}&artNo=${artNo}&remarkNo=-1&siteflag=-1&fromMenu=board/viewBoardNewArt.do`;
  const html = await (await s.fetch(detailUrl)).text();
  const commentKey = (html.match(/name="commentKey"\s+value="([^"]*)"/) || [])[1];
  if (!commentKey) throw new Error('commentKey 못 찾음 (상세 페이지 구조 변경?)');

  // 2) comment.do 로 위젯 HTML 받아 암호화 moduleSeq 추출
  const widget = await (await s.fetch(`${BASE}/gw/comment.do`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ commentKey }).toString(),
  })).text();
  fs.writeFileSync(__dirname + '/comment_widget.html', widget, 'utf8'); // 폴백 점검용
  const moduleSeq = (widget.match(/moduleSeq\s*=\s*"([^"]+)"/) || [])[1];
  if (!moduleSeq) throw new Error('암호화 moduleSeq 못 찾음 → comment_widget.html 확인');
  // companyInfo 를 위젯에서 그대로 추출(하드코딩 없음)
  const companyInfo = {};
  for (const m of widget.matchAll(/companyInfo\.(\w+)\s*=\s*"([^"]*)"/g)) companyInfo[m[1]] = m[2];

  // 3) SearchCommentList.do 로 댓글 목록
  const payload = {
    header: {},
    body: {
      companyInfo, langCode: 'kr', moduleGbnCode: 'board', moduleSeq,
      commentType: '', type: 'main', commentSeq: '', sort: 'D', searchWay: 'D', pageSize: 1000,
    },
  };
  const res = await s.fetch(`${BASE}/gw/api/SearchCommentList.do`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json;charset=UTF-8' },
    body: JSON.stringify(payload),
  });
  const j = JSON.parse(await res.text());
  if (j.resultCode !== '0') throw new Error('SearchCommentList 실패: ' + j.resultMessage);
  return (j.result && j.result.commentList) || [];
}

module.exports = { getComments };

if (require.main === module) {
  const artNo = process.argv[2] || '104506';
  const boardNo = process.argv[3] || '900000288';
  (async () => {
    const s = await login();
    const list = await getComments(s, artNo, boardNo);
    console.log(`댓글 ${list.length}건:`);
    for (const c of list) console.log(`  [${c.createDate}] ${c.empName}: ${c.contents}`);
    process.exit(0);
  })().catch(e => { console.error('오류:', e.message); process.exit(1); });
}
