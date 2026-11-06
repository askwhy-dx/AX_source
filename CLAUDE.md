# AX_source 작업 규칙 (Claude Code)

유튜브에서 AI 업무 사례를 모아 사내 AX 회차(T1 부서장회의 덱 · T2 인스타툰 · 게시판 글)를 만드는 폴더다.
**정본은 `README.md`** (§0 → §1 → §7 순서로 읽는다). 이 파일은 에이전트가 먼저 알아야 할 것만 추린다.
둘이 갈리면 README 가 맞고, 이 파일을 README 에 맞춰 고친다.

## 1. 지금 상태 (2026-09-28)

- **자동 배치 없음 · 수동 전용.** 수·목 09:40 스케줄러, `run_plan.bat` · `run_weekly.bat` · `tools/refill.py` ·
  `tools/notify.py` · `tools/run_hidden.vbs` 는 `archive/20260928_auto_removed/` 에 있다(스케줄러 XML 포함).
  README 본문의 「수요일 배치 · 목요일 배치 · 슬랙 알림 · 재고 자동 보충」은 **설계 이력**이다.
- 사용자가 「수집해줘」 「기획서 만들어줘」 「발행해줘」라고 요청하면 그때 README §3.3 순서로 손으로 돌린다.
- 같은 폴더의 `게시판자료전송/` 은 별개다 — 스케줄러 `board_material_send`(평일 30분) · `board_material_report`(평일 18:30 하루 1회 · 10-06 사용자)는
  **살아 있고 건드리지 않는다**(메모리 「게시판 자료전송」). **2026-10-16 메일 발송 재가동**(10-06~10-16 슬랙 알림만 · 사용자 · `게시판자료전송/README.md` 머리 참조) — 새 게시 글마다 주차매핑 추가 필요.

## 2. 회차 폴더 (`out/`)

| 폴더 | 회차 이름 (`config/회차이름.json`) | 페이지 버튼 (`config/회차버튼이름.json`) | 비고 |
|---|---|---|---|
| `20260908` | 9월 시범 회차 | — | 미발행 |
| `20260909` | 9월 첫번째 | 1tr-AI사례 | |
| `20260916` | 9월 두번째 (특별편) | 2tr-starter-1step | |
| `20260923-후보` | (9월 네번째) | — (10-02 버튼 이름을 20261006 으로 옮김) | 날짜 폴더가 아니라 **회차로 안 읽힌다**. 공개본 `out/20260923/` 은 리포에 남아 있음 |
| `20260928` | 9월 세번째 (특별편 · 체험 툰) | 3tr-starter-2step | 옛 `20260929`. 옛 공개 링크도 200 유지 |
| `20261006` | 10월 네번째 (특별편 · 초급 교육) | 4tr-basic-1step | **10-06 T2 툰 11장 + 기획서 발행(`--plan`, 커밋 1da6f19)** · 원고 = 「사내 데이터로 스킬 · 자동화 에이전트를 만들었다」 · 게시판 제목 훅 「우리 회사 기준을 아는 AI 직원, 직접 만들어 봤어요」 · 기획서 PDF 「직영」 표기는 **그대로 발행으로 결정**(10-06 사용자) · 주차매핑 `10-4` = claude-code-skills-agents.html (10-16 추가) |
| `20261012` | 10월 다섯번째 (특별편 · 초급 체험 · 10-02 이름 확정) | 5tr-basic-2step | **10-06 「외부 데이터 연결」 체험으로 교체**(MCP 구글 시트 · 국가법령정보 API · 교육청 보도자료 크롤링 → 엑셀 모으기 · 슬랙 없음) · 칩 = 새 초급 체험가이드(`ax_study/claude-code-external-data.html`) · 옛 서브 · 팀 판 = `archive/20261012_옛체험_master용/`(마스터 체험용) · **툰 그림 대기** |
| `20261102` | 11월 첫번째 (Advance 교육 · 10-29) | 6tr-advance-1step | 정본 = `AX_study/advance/1step/advance_1step_기획.html` · 링크 칩 = advance-1step(`claude-code-automation.html`) · advance-2step · 가이드 v2.0(19단계)에 맞춰 10-29 재발행(커밋 807c337) · 가이드는 10-30 v2.2(카드 실측 반영 · 단계 번호 그대로 · 회차 재발행 안 함) · 툰 · 게시판 글 없음 |
| `20261109` | 11월 두번째 (advance 2step 팀 꾸리기 · 11-05) | 7tr-advance-2step | 정본 = `AX_study/advance/2step/advance_2step_기획.html` · 칩 = advance-2step(가이드 v3.0) · 툰 · 게시판 글 없음 |
| `20261116` | 11월 세번째 (master 1step 스스로 지키기 · 11-05) | 8tr-master-1step | 정본 = `AX_study/master/1step/master_1step_기획.html` · 날짜는 자리 잡기 · 칩·③ 교육 = master-1step(`claude-code-self-guard.html` · 가이드 v1.0 · 11-06) |
| `20261123` | 11월 네번째 (master 2step 팀에 퍼뜨리기 · 11-05) | 9tr-master-2step | 정본 = `AX_study/master/2step/master_2step_기획.html` · 날짜는 자리 잡기 · 11-06 개편 = 교육생 슬랙 봇 + 헤르메스(1~3) · 플러그인 · 모드 = 강사 시연 · 칩·③ 교육 = master-2step(`claude-code-team-share.html` · 가이드 v2.0) |

- **과정 표기 = AX_study 폴더 이름**(10-30 통일: starter/basic/advance/master · 1step/2step): 버튼 `Ntr-<과정>-<1step|2step>` · 가이드 칩(`out/<회차>/회차유형.json` 링크 「이름」) = `starter-1step` · `starter-2step` · `basic-1step` · `basic-2step`. 새 과정 회차도 이 꼴로.
- **회차 이름**(`회차이름.json`)은 게시판 글 제목과 자료 메일 발송 키(`9-3` 등)까지 쓴다. **바꾸면 `게시판자료전송/config.json` 주차매핑도 같이.**
- **버튼 글자만** 바꿀 때는 `회차버튼이름.json` 만 고친다.
- **페이지 제목(2026-10-28 사용자)** = 「AX 확산 한눈에」 고정(회차 이름 없음) + 부제 한 줄. 소재풀 건수 줄은 ② 사례 카드 안. 파일 이름 `소재추천.html` 은 바꾸지 않는다(공개 링크).
- **페이지 구조(2026-10-28 사용자)** = 맨 위 교육 진행 버튼(`config/교육목록.json` 「진행표」 · 비공개 아티팩트) → 접힌 카드 ① 기획(회차별 보기) · ② 사례 · ③ 교육(`config/교육목록.json` — 새 가이드 발행 시 링크 채움) · ④ 게시글(`게시판글_*.txt` + `config/게시글번호.json` — **새 게시판 글을 올리면 회차 → artNo 한 줄**, 조회는 `게시판자료전송/board.js`) · ⑤ 활용(`config/교육목록.json` 「활용」 — 직무별 활용 자료 · 비공개 아티팩트 링크). 머리 칩 · `setCaseOnly` 는 없다.
- 회차 안 **산출물 칩**(T2교육 등) 글자는 `tools/build_page.py` 의 `CHIP_NAME` 에서 바꾼다(지금 `T2교육 → 교육-인스타툰` 하나). 키 자체를 바꾸면 `startswith("T2")` 판정이 깨져 툰 칩이 조용히 빠진다.
- 도구는 `YYYYMMDD` 8자리 폴더만 회차로 본다. 접미어(`-후보`)를 붙이면 페이지에서 빠진다.

## 3. 반드시 지킬 것

1. **모든 도구에 `AX_ROUND_DAY=<회차 폴더 날짜>` 를 준다.** 없으면 `round_day()` 가 「그 주 수요일」을 골라
   빈 회차 폴더를 새로 만들고 **LLM 기획까지 호출**한다(2026-09-28 `build_page.py` 로 실제 발생). 지금 회차 폴더는 수요일이 아니다.
2. **`build_page.py` 는 항상 마지막.** 그 순간 폴더에 있는 파일만 버튼에 건다.
3. **README·핵심 스크립트를 고치면 `python tools/sysdoc.py` → `python tools/self_test.py`.** 시스템정리 HTML 스탬프가 어긋나면 FAIL.
4. **`publish.py` 는 사용자가 요청할 때만**, 먼저 `--dry-run`. 리포가 **public** 이다(추측 불가 경로 + noindex 뿐).
   체험·교육처럼 T1 덱이 없는 회차는 `--plan`. 올린 뒤 40~60초 기다려 공개 URL 200 을 확인한다
   (한글 경로는 curl 대신 `urllib.parse.quote` 로 확인 — curl 은 윈도우에서 한글이 깨져 404 가 난다).
5. **`out/` 폴더는 자주 잠긴다** — `mv` 가 Permission denied 면 `cp -r` → `diff -r` 동일 확인 → 원본 삭제.
6. **덮어쓰기·이동 전 `archive/` 에 백업**하고 README §8 변경 이력에 한 절을 남긴다.
7. **README 에서 T1·T2·배치·소재 기준을 바꾸면 `docs/AX확산/` 기준 문서도 같은 작업 안에서 고친다**(README 머리 🔗 표). 옛 `test\AX_Adoption` 은 2026-10-12 에 여기로 흡수·삭제됐다.
   한쪽만 고쳐도 에러가 안 난다.
8. **툰 · 게시판 글에 「직영」 · 회사 세부 기준(제외 프로그램 등) · 회사 숫자를 내지 않는다**(2026-10-06 사용자). 연출 3칸(장면설명 · 화면문구 · 메모문구)을 **대본에 다 적는다** — 비우면 LLM 이 회차유형을 보고 채워 다시 샌다. 대본을 고치면 `build_brief` → `build_toon_prompt` 순(거꾸로면 옛 기획서 PDF 가 첨부물로 간다).
9. `build_brief.py` 는 부를 때마다 고른 두 건의 설명을 다시 받을 수 있다(YouTube 1 unit). `collect.py` 는 약 40 units.

## 4. 자주 하는 일

```bash
export AX_ROUND_DAY=20261006 PYTHONUTF8=1 PYTHONIOENCODING=utf-8
python tools/collect.py && python tools/axis_llm.py && python tools/collect.py --rebuild   # 수집
python tools/build_brief.py            # 기획서
python tools/collect_toon.py --ax 체험  # 구워 온 툰 그림 정리 (toon/<축>/받은/01~NN.png)
python tools/build_board_post.py --round $AX_ROUND_DAY
python tools/build_page.py && python tools/sysdoc.py && python tools/self_test.py
python tools/publish.py --round $AX_ROUND_DAY --plan --dry-run
```

회차 폴더 이름을 바꿀 때: 폴더 복사 → `회차이름.json`·`회차버튼이름.json` 키 교체 → 위 생성기를 새 날짜로 다시 돌려
파일명(`_YYYYMMDD`)을 맞춤 → `toon/첨부.md` 경로 치환 → 옛 이름 파일 삭제 → 발행(요청 시). 옛 공개 링크는 리포에 남는다.
