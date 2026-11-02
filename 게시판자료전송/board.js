// board.js — "AI자동화 공유" 게시판(900000288) 글 목록을 가져와 파싱한다.
//
// ⚠️ viewBoardNewArt.do 를 쓰면 안 된다 (2026-09-21 발견). 그건 게시판 목록이 아니라
//    **전사 최근글 피드**다 — boardNo 를 줘도 다른 게시판 글이 섞여 오고, 우리 글은
//    새 글에 밀려 피드에서 빠지는 순간 **조용히 사라진다**(에러도 0건도 아니고 목록이 빔).
//    viewBoard.do 는 그 게시판 글만 exData 에 담아 준다(cat_seq_no 없음, totalCount 로 전건).
const { login } = require('./login.js');
const BASE = 'https://gwa.askwhy.co.kr';
const BOARD_NO = '900000288';

// viewBoard.do 응답의 exData 배열에서 글을 뽑는다. 응답이 그 게시판만 담으므로 따로 거르지 않는다.
function parsePosts(html) {
  const posts = [];
  // 각 글 객체: { "art_seq_no": 104506, ... "art_title": "...", ... "write_date": "2026-09-15" }
  for (const m of html.matchAll(/"art_seq_no":\s*(\d+)[\s\S]*?"art_title":\s*"((?:[^"\\]|\\.)*)"/g)) {
    posts.push({ artNo: m[1], title: m[2].replace(/\\"/g, '"') });
  }
  return posts;
}

async function listPosts(s, boardNo = BOARD_NO) {
  const url = `${BASE}/edms/board/viewBoard.do?boardNo=${boardNo}`;
  const html = await (await s.fetch(url)).text();
  return parsePosts(html);
}

module.exports = { listPosts, parsePosts, BOARD_NO };

// 단독 실행: 로컬 파일 파싱 테스트 (인자로 html 파일) 또는 라이브 목록
if (require.main === module) {
  const fileArg = process.argv[2];
  if (fileArg) {
    const html = require('fs').readFileSync(fileArg, 'utf8');
    console.log(parsePosts(html));
  } else {
    login().then(listPosts).then(p => { console.log(p); process.exit(0); })
      .catch(e => { console.error('오류:', e.message); process.exit(1); });
  }
}
