# 게시판 자료 전송

「사내게시판 > AI자동화 공유」(그룹웨어 bizbox) 글에 댓글이 달리면,
댓글에 적힌 **@askwhy.co.kr** 메일주소로 그 주차 GitHub 링크를 자동 발송한다.

> **✅ 2026-10-16 메일 발송 재가동 (사용자 지시)** — `watch.js` 를 `../archive/watch.261006_before_notify_only.js` 로 원복(도메인 게이트·주차매핑 다시 탐), 주차매핑 `10-4` 추가. 슬랙 알림판은 `../archive/watch.261016_notify_only.js`. 아래 10-06 절은 이력.
>
> **(이력) 2026-10-06 ~ 10-16 메일(자료) 발송 중단 → 슬랙 알림만 (사용자 지시)**
> `watch.js` 는 새 댓글의 이메일을 메일로 보내지 않고, 슬랙 **`D0BA6SULQUU`**(유삐 봇 ↔ JC Kim DM)에
> 「게시글 제목 + 이메일」만 알린다. 알림 본문 머리 `*<AI자동화 공유 댓글 알림>*`.
> - 링크를 안 보내므로 **도메인 게이트(@askwhy.co.kr)·주차매핑을 타지 않는다** — 외부 도메인 이메일도 알리고, 매핑 없는 글도 알린다.
> - 그대로인 것: 제목 형식(`weekLink`) 필터 · `sent.json` 중복방지(의미 = 「알림 보낸 이메일」) · 슬랙 실패 시 기록 안 남김 → 30분 뒤 재시도.
> - `report.js` 문구는 「발송」 그대로 둔다(사용자 결정). 10-06 이후 늘어나는 건수는 **알림 건수**다.
> - 바뀐 파일: `watch.js`(발송 루프 → 슬랙 알림) · `alert.js`(`postSlack(text, channel)` 채널 인자 추가, 기본값은 기존 DM).
> - 원복: `../archive/watch.261006_before_notify_only.js` 를 `watch.js` 로 되돌리면 메일 발송 복귀(`alert.js` 변경은 하위호환이라 그대로 둬도 됨).
>
> 아래 본문의 「발송」·도메인 게이트·주차매핑 설명은 메일 발송 시절 기준이다(원복 대비 보존).

## 동작 흐름

```
login.js      AES + Spring Security 2단계 로그인, 세션 유지
board.js      게시판 900000288 글 목록 (제목 + artNo)
get_comments.js  글 상세 → comment.do(암호화 moduleSeq) → SearchCommentList.do → 댓글
mailer.js     공용 _gdrive OAuth(Gmail)로 발송 (발송자 jichang999@askwhy.co.kr)  ※ 10-06부터 미사용
watch.js      위를 엮어 한 바퀴: 댓글 이메일 추출 → 중복제외 → 슬랙 D0BA6SULQUU 알림 (10-06 이전: 도메인필터 → 메일 발송)
alert.js      사고 발생 시 슬랙 DM 알림 (정상일 땐 조용함)
```

## 중지 / 재개  *(2026-09-21)*

`config.json` 의 **`"중지": true`** 면 `watch.js` 가 로그인도 않고 즉시 끝난다
(2026-09-22 기준 **`false` = 가동 중**).
스케줄러는 계속 30분마다 돌지만 아무것도 발송하지 않는다. 재개는 `false`.
(스케줄러 자체를 끄려면 `Disable-ScheduledTask -TaskName board_material_send` — 관리자 권한 필요)

## 실행

```
node watch.js --dry-run   # 무엇을 보낼지만 출력 (발송·기록 없음)
node watch.js             # 실제 발송

node report.js --dry-run  # 발송 건수 보고 본문만 출력 (슬랙 발송 없음)
node report.js            # 슬랙 DM 으로 정기 보고 (아래 「정기 보고」 절)
```

## 자동 실행 (등록 완료)

작업 스케줄러 작업 **둘**이다 — **`board_material_send`**(평일 30분마다 · 발송)와
**`board_material_report`**(평일 18:30 하루 1회 · 건수 보고, 아래 「정기 보고」 절). 아래 표는 발송 쪽이고,
보고 쪽은 작업 이름만 바꿔 같은 명령을 쓴다.

작업 스케줄러 **`board_material_send`** 로 **평일(월~금) 30분마다** 무인 실행 중(00:00부터 24시간, `PT30M` · 2026-10-07 10분→30분 · 공휴일은 `run_hidden.vbs` 가 건너뜀).
창이 안 뜨게 **`run_hidden.vbs` (wscript //B, 창 숨김 + stdout 리다이렉트)** 를 물린다.
한글 폴더경로의 .bat cp949 함정을 피해 vbs 안에서 node.exe 를 직접 부른다
(vbs 는 **ASCII·BOM 없이** 유지 — 800A0408).

| 작업 | 명령 (PowerShell) |
|---|---|
| 상태 확인 | `Get-ScheduledTaskInfo -TaskName board_material_send` |
| 즉시 실행 | `Start-ScheduledTask -TaskName board_material_send` |
| 잠시 끄기 | `Disable-ScheduledTask -TaskName board_material_send` |
| 완전 삭제 | `Unregister-ScheduledTask -TaskName board_material_send` |

- 로그온 상태에서 실행 + `StartWhenAvailable`(PC 꺼졌다 켜지면 따라잡음).
- 실행 로그: `watch.log`. `watch.console.out` 은 마지막 회차 콘솔 원본(매회 덮어씀).
- ⚠️ `run_hidden.vbs` 는 **첫 인자로 실행할 스크립트**를 받는다(없으면 `watch.js`). 두 작업이 같은 러너를 쓴다.

## 사고 알림 (슬랙 DM)

문제가 생기면 `alert.js` 가 **슬랙 DM(JC Kim)** 으로 알린다. 정상일 땐 아무 말도 안 한다.
제목은 `<인스타툰 자료 전송 오류 보고>` 고정.

| 알리는 경우 | 위치 표기 |
|---|---|
| 한 바퀴가 통째로 깨짐 (로그인·게시판 조회 실패 등) | `watch.js` |
| 주차매핑이 없어 발송 못 함 (댓글은 달렸는데 링크가 없음) | `주차매핑 누락` |
| 특정 수신자 메일 발송 실패 (나머지 수신자는 계속 진행) | `메일 발송` |

- 자격: `test\.env` 의 `SLACK_BOT_TOKEN`(yuppi 봇) → `chat.postMessage`, 수신 `U0B4RTB73TK`(JC Kim).
  웹훅(`tools/notify.py`)은 채널이 URL 에 박혀 있어 DM 이 안 돼서 봇 토큰을 쓴다.
  ⚠️ **yuppi 봇과의 DM 으로 들어온다** — 본인 자기 DM(「나」) 칸에 넣으려면 user token(xoxp)이 필요하다.
- **30분 배치라 같은 오류가 이어지면 하루 48통**이 된다 → 같은 오류는 **1시간에 1통**만
  (`alert_state.json`). 억제 시간은 `alert.js` 의 `SUPPRESS_MIN`.
- 알림 실패는 배치를 죽이지 않는다(부수 효과).
- 점검: `node alert.js --dry-run`(본문만 출력) / `node alert.js --test`(실제 DM 1통).
- **못 잡는 것**: 배치 자체가 안 돈 경우(PC 꺼짐·스케줄러 중지)는 watch.js 가 실행되지 않으므로
  알림도 안 간다. 그건 `Get-ScheduledTaskInfo -TaskName board_material_send` 로 본다.

## 점검 (사람이 손으로 볼 때)

```
grep -v "완료: 0건 발송" watch.log     # 발송·스킵·오류만 추림 (정상 회차는 전부 "완료: 0건")
cat sent.json                          # {artNo: [보낸 주소]} — 발송 실적 정본
Get-ScheduledTaskInfo -TaskName board_material_send   # 마지막 실행·결과·다음 실행
```

- 2026-09-16 11:30 기준: 49회 실행 / 발송 2건 / 오류 1회(09-15 20:22 `fetch failed`, 자동 복구).
- `watch.log` 타임스탬프가 30분 간격에서 크게 벌어져 있으면 **PC 절전 구간**이다(사고 아님).

## 새 주차 글을 올릴 때

0. 글 문구는 **손으로 쓰지 않는다** — 툰 대본에서 낸다.
   `python tools/build_board_post.py` → `out/<회차>/게시판글_<회차>.txt` (제목 + 본문).
   `collect_toon.py` 가 두 축을 다 정리하면 자동으로 같이 만든다.
1. 게시글 제목을 **`N월 M번째 공유 - AI자동화 사례 - <훅>`** 꼴로 쓴다 (2026-09-21 규칙).
   `python tools/build_board_post.py` 가 이 형식으로 만들어 주므로 그대로 붙여 넣으면 된다.
   번호는 **달력 주차가 아니라 그 달에 올린 공유글 순번**이다(9월 2주차 글 = 9월 **첫번째** 공유).
   옛 `N월 M주차` 꼴도 계속 읽는다(이미 올라간 글이 죽지 않게).
   서수(첫·두·세…)도 `9월 3번째` 같은 숫자도 된다.
   ⚠️ `9월 셋째주`·`9/3주차` 는 **안 걸린다** — 글이 통째로 무시되고 알림도 안 온다.
   ⚠️ **붙여 넣을 때 「N월」이 빠지기 쉽다** — 2026-10-06 4번째 글이 `네번째 공유 - …` 로 올라가
      18:30 보고에서 빠졌다(「대상 글 3건」). 올린 뒤 목록에서 제목 맨 앞 `N월` 을 눈으로 확인하고,
      그날 18:30 보고의 「대상 글」 수가 늘었는지 본다. 제목만 고치면 다음 30분 회차부터 잡힌다(그 사이 댓글 포함).
   ⚠️ 두 형식은 **같은 키**를 쓴다(`9월 2주차` = `9월 두번째` = `9-2`). 한 달 안에서 섞으면
      엉뚱한 회차 링크가 조용히 나간다.
2. `config.json` 의 `주차매핑` 에 그 키 → 자료 회차(YYYYMMDD) 한 줄 추가.
   예: `"9-2": "20260916"`
   보낼 자료가 회차 산출물(T1)이 아니면 **링크 전체**를 값으로 적는다(`http` 로 시작하면 그대로 나간다).
   예: `"9-2": "https://jichang999-dotcom.github.io/tes2/ax_study/claude-code-setup-guide.html"`
   (2026-09-22 추가. 20260916 체험 회차의 자료는 AX_study 교육가이드라 회차 링크가 아예 없었다.)
3. 그 회차가 `AX_source/tools/publish.py` 로 **GitHub 발행**돼 있어야 링크가 산다(안 하면 404).
   링크를 직접 적는 경우에도 발송 전에 `curl -s -o /dev/null -w "%{http_code}" "<링크>"` = 200 을 확인한다.

## 글 목록이 통째로 비는 함정 *(2026-09-21 수정)*

`viewBoardNewArt.do` 는 **게시판 목록이 아니라 전사 최근글 피드**였다. `boardNo` 를 줘도
다른 게시판 글이 섞여 오고, 우리 글은 새 글에 밀려 피드에서 빠지는 순간 목록에서 사라진다.
**에러도 아니고 「0건 발송」과 구분도 안 된다** — 로그는 정상처럼 보이는데 댓글을 아무도 못 받는다.
09-15 에 올린 글이 09-21 에 이 상태였다(댓글 4건, 그중 링크 오류 문의 1건).

`board.js` 를 **`viewBoard.do?boardNo=...`** 로 바꿔 그 게시판만 받는다.
점검은 `node board.js` — 우리 글이 나와야 한다. **빈 배열 `[]` 이면 발송은 0건이 맞는 게 아니라 눈이 먼 것이다.**

## 리포·주소를 옮겼을 때 *(2026-09-18 추가)*

`config.json` 의 `github링크형식` 을 고치면 **그 뒤에 오는 요청**만 새 링크를 받는다.
**이미 메일을 받은 사람은 `sent.json` 때문에 재발송되지 않는다** — 죽은 옛 링크를 그대로 들고 있고,
같은 글에 댓글을 다시 달아도 안 온다. 주소를 옮기면 코드·설정만 고치고 끝내지 말 것.

1. 무엇이 나갔는지 본다 — `grep "\[발송\]" watch.log` 의 URL 이 옛 주소인지 새 주소인지로 가른다.
   (설정을 고친 시점보다 **전에** 찍힌 줄이 전부 옛 링크다.)
2. 새 주소가 사는지 확인한다 — `curl -s -o /dev/null -w "%{http_code}" "<새 링크>"` = 200.
   한글 경로는 퍼센트 인코딩해야 한다.
3. 재발송은 **관리자 판단** — `sent.json` 에서 해당 글번호 항목(또는 그 이메일 한 줄)을 지우면
   다음 회차(30분 내)에 **실제로 메일이 다시 나간다.** 지우기 전에 반드시 묻는다.
   지우지 않기로 했으면 새 링크를 **사람이 직접 전달**하거나 게시판 글을 갱신한다.

> 2026-09-17 tes1 → tes2 이전 때 실제로 이 상태가 됐다. 링크형식은 09-17 에 tes2 로 바뀌었지만
> 09-16 에 발송된 3명은 tes1 링크를 들고 있었고, 09-18 확인 시 재발송하지 않기로 했다(사용자 결정).

## 규칙·주의

- 댓글 이메일이 **@askwhy.co.kr** 이 아니면 발송하지 않는다(`config.json` 허용도메인, 고정).
  ※ 10-06 알림 전용으로 바뀐 뒤엔 이 게이트를 안 탄다. **메일 발송으로 되돌릴 땐 게이트도 같이 돌아와야 한다**(원복본에 있음).
- 중복방지: `sent.json` 에 글(artNo)별 발송한 이메일을 기록, 이미 보낸 주소는 재발송 안 함.
  ⚠️ 이건 **링크가 바뀌어도 마찬가지다** — 위 「리포·주소를 옮겼을 때」 참조.
- 트리거는 **댓글 본문에 이메일이 있으면**. 이메일이 곧 수신 주소다.
- `config.json` 에 계정 평문이 들어가므로 **외부 공유 금지**.
- 보내는 T1 링크는 public GitHub Pages다. 도메인 게이트(@askwhy.co.kr)가 유일한 통제이므로
  허용도메인을 넓히지 말 것. (배경: AX_source 발행 메모)
- `comment_widget.html` 은 `get_comments.js` 가 매 실행 재생성하는 임시 덤프(점검용). 지워도 됨.

## 그룹웨어 도착 지연은 정상

`askwhy.co.kr` 은 Google Workspace 수신이고, 그룹웨어 "메일"은 외부메일을 **POP로 주기적으로
당겨온다**. 그래서 발송은 즉시지만 **그룹웨어함 표시는 그 주기만큼 지연**될 수 있다(Gmail 은 즉시).
발송 코드는 counsel_report(성공 케이스)와 동일하므로 지연은 코드 문제가 아님. (2026-09-15 실증)

## 정기 보고 — 게시물별 발송 건수 (슬랙 DM)  *(2026-09-23 신설)*

`report.js` — 게시판 글 목록 + `sent.json` 을 합쳐 **글별 발송 건수와 수신자**를 슬랙 DM 으로 보낸다.
사고 알림(`alert.js`)과 같은 유삐 봇·같은 DM 으로 가지만, **억제 없이 매번 보낸다**(정상 보고이므로).

- 작업 스케줄러 **`board_material_report`** = `run_hidden.vbs report.js`, **평일(월~금) 18:30 하루 1회**
  (트리거 1개, StartWhenAvailable, 창 숨김 · 2026-10-06 사용자 지시로 09:30 · 12:00 · 15:00 삭제, 원복 XML `../archive/board_material_report.261006_before_1830only.xml`).
- 세는 값 = `sent.json` 의 글별 수신자 수. **실제 메일이 나간 횟수**이고 중복은 없다(= 사람 수).
  ※ 10-06부터는 **슬랙 알림을 보낸 이메일 수**다(문구 「발송」은 사용자 결정으로 유지).
- 대상 글 판정은 `watch.js` 의 `weekLink` 를 그대로 재사용한다 — 규칙이 갈리면 보고는 0건인데
  실제로는 나가는(또는 그 반대) 상태가 **조용히** 생긴다. 그래서 복제하지 않고 require 한다.
- 글 목록에서 밀려난 글은 제목을 못 붙이므로 `(제목 확인 필요 · artNo …)` 로 건수만 남긴다.
- 점검: `node report.js --dry-run`(발송 없이 본문 출력) / `node report.js --self-test`(로그인 없이 조립만).
- ⚠️ `run_hidden.vbs` 는 이제 **첫 인자로 실행할 스크립트를 받는다**(기본 `watch.js`).
  콘솔 덤프는 `<스크립트명>.console.out` 으로 나뉜다(`watch.console.out` / `report.console.out`).
- ⚠️ `watch.js` 는 `module.exports` 가 생기면서 **`require.main` 가드**가 붙었다. 직접 실행 동작은 그대로.
- ⚠️ PC 가 꺼져 있거나 절전이면 그 회차는 건너뛴다(StartWhenAvailable 로 복귀 후 1회 따라잡기).
