// mailer.js — 공용 _gdrive OAuth(Gmail)로 링크 메일 발송.
// counsel_report 와 동일 자격(발송자 jichang999@askwhy.co.kr) 재사용.
const fs = require('fs');
const path = require('path');
const { google } = require('googleapis');

const GDRIVE = process.env.GDRIVE_DIR || 'C:\\Users\\User\\Desktop\\test\\_gdrive';

function gmailClient() {
  const cs = JSON.parse(fs.readFileSync(path.join(GDRIVE, 'client_secret.json'), 'utf-8'));
  const tk = JSON.parse(fs.readFileSync(path.join(GDRIVE, 'gmail_token.json'), 'utf-8'));
  const c = cs.installed || cs.web;
  const o = new google.auth.OAuth2(c.client_id, c.client_secret, 'http://localhost');
  o.setCredentials({ refresh_token: tk.refresh_token });
  return google.gmail({ version: 'v1', auth: o });
}

function buildMime(to, subject, html) {
  const b64 = (s) => Buffer.from(s, 'utf-8').toString('base64');
  const headers = [
    `To: ${to}`,
    `Subject: =?UTF-8?B?${b64(subject)}?=`,
    'MIME-Version: 1.0',
    'Content-Type: text/html; charset="UTF-8"',
    'Content-Transfer-Encoding: base64',
  ].join('\r\n');
  return Buffer.from(headers + '\r\n\r\n' + b64(html), 'utf-8')
    .toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

// 본문 — counsel_report(성공 케이스)와 동일한 밋밋한 업무메일 스타일.
// 이모지·자동발송 꼬리말 제거(Gmail 프로모션/알림 분류 회피).
function body(url, title) {
  let b = '';
  b += '안녕하세요 담당자님,<br><br>';
  b += `요청하신 자료 안내드립니다. (${title || 'AI자동화 사례 공유'})<br><br>`;
  b += `자료 링크 : <a href="${url}">${url}</a><br><br>`;
  b += '감사합니다.';
  return b;
}

async function sendLink(to, subject, url, title) {
  const gmail = gmailClient();
  await gmail.users.messages.send({
    userId: 'me',
    requestBody: { raw: buildMime(to, subject, body(url, title)) },
  });
}

module.exports = { sendLink };
