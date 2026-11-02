// login.js — 그룹웨어(bizbox/Neos) 로그인 + 세션 유지
// config.json 의 id/pw 로 로그인해 JSESSIONID 세션을 돌려준다.
// 자격증명은 이 파일 밖으로 출력하지 않는다.
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

const BASE = 'https://gwa.askwhy.co.kr';
const CFG = require(path.join(__dirname, 'config.json'));

// 로그인 페이지 aes.js 와 동일: AES-128-CBC, key=iv="jIkzy7glpbkd8hIE", pkcs7,
// base64 → '!' 접두 → encodeURIComponent
function enc(s) {
  const k = Buffer.from('jIkzy7glpbkd8hIE', 'utf8');
  const c = crypto.createCipheriv('aes-128-cbc', k, k);
  const b = Buffer.concat([c.update(Buffer.from(s, 'utf8')), c.final()]).toString('base64');
  return encodeURIComponent('!' + b);
}

// 쿠키 저장소 (아주 단순: name=value 맵)
class Session {
  constructor() { this.cookies = {}; }
  header() { return Object.entries(this.cookies).map(([k, v]) => `${k}=${v}`).join('; '); }
  absorb(res) {
    let sc = res.headers.getSetCookie ? res.headers.getSetCookie() : null;
    if (!sc) { const one = res.headers.get('set-cookie'); sc = one ? [one] : []; }
    for (const line of sc) {
      const [pair] = line.split(';');
      const i = pair.indexOf('=');
      if (i > 0) this.cookies[pair.slice(0, i).trim()] = pair.slice(i + 1).trim();
    }
  }
  async fetch(url, opts = {}) {
    const res = await fetch(url.startsWith('http') ? url : BASE + url, {
      ...opts,
      redirect: 'manual',
      headers: { 'Cookie': this.header(), 'User-Agent': 'Mozilla/5.0', ...(opts.headers || {}) },
    });
    this.absorb(res);
    return res;
  }
}

async function login() {
  const s = new Session();
  // 1) 로그인 페이지 GET → 초기 JSESSIONID 획득
  await s.fetch('/gw/uat/uia/egovLoginUsr.do');
  // 2) actionLogin.do POST
  const body = new URLSearchParams({
    id: enc(CFG.id), id_sub1: '', id_sub2: '',
    password: enc(CFG.pw),
    isScLogin: '', scUserId: '', scUserPwd: '',
  }).toString();
  const res = await s.fetch('/gw/uat/uia/actionLogin.do', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  });
  // actionLogin.do 는 검증 후 Spring Security(j_spring_security_check)로
  // 자동 제출하는 중간 폼을 돌려준다. 그 폼의 hidden 값을 뽑아 2차 POST.
  const html = await res.text();
  const uname = (html.match(/name='j_username'\s+value='([^']*)'/) || [])[1];
  const pword = (html.match(/name='j_password'\s+value='([^']*)'/) || [])[1];
  const action = (html.match(/action='([^']*)'/) || [])[1] || '/gw/j_spring_security_check';
  if (!uname) {
    throw new Error(`로그인 실패 (actionLogin 단계, status=${res.status}, 본문=${html.slice(0, 200)})`);
  }
  const res2 = await s.fetch(action, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({ j_username: uname, j_password: pword }).toString(),
  });
  const loc = res2.headers.get('location') || '';
  // 성공: 메인으로 302, 실패: login_error / egovLoginUsr 로 되돌림
  const ok = res2.status === 302 && !/login_error|egovLoginUsr/.test(loc);
  if (!ok) {
    throw new Error(`로그인 실패 (spring 단계, status=${res2.status}, location=${loc || '없음'})`);
  }
  return s;
}

module.exports = { login, Session, enc, BASE };

// 단독 실행 시: 로그인만 확인 (자격증명은 안 찍음)
if (require.main === module) {
  login().then(s => {
    console.log('로그인 성공. JSESSIONID=' + (s.cookies.JSESSIONID ? '획득됨' : '없음'));
  }).catch(e => { console.error('로그인 실패:', e.message); process.exit(1); });
}
