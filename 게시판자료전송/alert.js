// alert.js — 사고 발생 시 슬랙 DM 알림. 정상일 땐 아무 말도 안 한다.
//
// 수신: JC Kim DM (U0B4RTB73TK).  자격: test\.env 의 SLACK_BOT_TOKEN (yuppi 봇).
// 웹훅(notify.py)은 채널이 URL 에 박혀 있어 DM 이 안 된다 — 그래서 봇 토큰 chat.postMessage.
//
// ⚠️ 30분마다 도는 배치라 같은 오류가 이어지면 하루 48통이 된다.
//    그래서 같은 오류는 SUPPRESS_MIN 분 안에 한 번만 보낸다(alert_state.json).
const fs = require('fs');
const path = require('path');

const ENV = 'C:/Users/User/Desktop/test/.env';   // 슬래시로 쓴다 - 역슬래시는 편집 도중 조용히 한 겹 벗겨진다
const TO = 'U0B4RTB73TK';           // JC Kim
const TITLE = '<인스타툰 자료 전송 오류 보고>';
const STATE = path.join(__dirname, 'alert_state.json');
const SUPPRESS_MIN = 60;

const env = (key) => {
  try {
    for (const line of fs.readFileSync(ENV, 'utf8').split(/\r?\n/)) {
      const m = line.match(/^\s*([A-Za-z0-9_]+)\s*=\s*(.*)$/);
      if (m && m[1] === key) return m[2].trim().replace(/^["']|["']$/g, '');
    }
  } catch {}
  return '';
};

const kst = () => new Date(Date.now() + 324e5).toISOString().slice(0, 19).replace('T', ' ');

// 같은 오류 반복 억제. 반환 true = 이번엔 조용히 넘어간다.
function muted(key) {
  let s = {};
  try { s = JSON.parse(fs.readFileSync(STATE, 'utf8')); } catch {}
  const now = Date.now();
  if (s[key] && now - s[key] < SUPPRESS_MIN * 60000) return true;
  s[key] = now;
  try { fs.writeFileSync(STATE, JSON.stringify(s, null, 2), 'utf8'); } catch {}
  return false;
}

// where: 어디서 터졌나(예: 'watch.js'), detail: 오류 메시지, extra: 덧붙일 줄들
async function alert(where, detail, extra = [], { dry = false, force = false } = {}) {
  const text = [
    `*${TITLE}*`,
    `• 시각 : ${kst()} (KST)`,
    `• 위치 : 게시판 자료 전송 / ${where}`,
    `• 내용 : ${detail}`,
    ...extra.map((l) => `• ${l}`),
    '• 로그 : `' + path.join(__dirname, 'watch.log') + '`',
    '• 다음 회차(30분 뒤)에 자동 재시도합니다. 같은 오류는 1시간에 한 번만 알립니다.',
  ].join('\n');

  if (dry) { console.log(text); return true; }
  if (!force && muted(`${where}|${detail}`.slice(0, 200))) return false;
  return postSlack(text);
}

// 같은 DM 으로 아무 글이나 보낸다(억제 없음). 정기 보고(report.js)가 쓴다.
async function postSlack(text, channel = TO) {
  const token = env('SLACK_BOT_TOKEN');
  if (!token) { console.log('[alert] SLACK_BOT_TOKEN 없음 — 발송 못 함'); return false; }
  try {
    const r = await fetch('https://slack.com/api/chat.postMessage', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json; charset=utf-8', Authorization: `Bearer ${token}` },
      body: JSON.stringify({ channel, text, unfurl_links: false }),
    });
    const j = await r.json();
    if (!j.ok) console.log('[alert] 슬랙 실패: ' + j.error);
    return !!j.ok;
  } catch (e) {
    // 알림 실패가 배치를 죽이면 안 된다 — 알림은 부수 효과다.
    console.log('[alert] 슬랙 발송 실패(무시): ' + e.message);
    return false;
  }
}

module.exports = { alert, postSlack };

// 점검용:  node alert.js --dry-run   /  node alert.js --test
if (require.main === module) {
  const dry = process.argv.includes('--dry-run');
  alert('점검', '테스트 알림입니다 (실제 사고 아님)', ['조치 : 불필요'], { dry, force: true })
    .then((ok) => console.log(dry ? '[dry-run] 발송하지 않았습니다.' : ok ? '발송 완료' : '발송 안 됨'));
}
