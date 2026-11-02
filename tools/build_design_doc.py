# -*- coding: utf-8 -*-
"""시스템 기획서 — AX_source 가 무엇을 어떻게 푸는지 한 문서(PDF)로. (2026-09-09 신설)

  python tools/build_design_doc.py
  python tools/build_design_doc.py --open

산출: out/시스템_기획서_<YYYYMMDD>.pdf  (+ 같은 이름의 .html)

## 왜 스크립트로 만드나 — 숫자를 옮겨 적으면 조용히 틀리기 때문이다
기획서에 「시드 채널 6개」·「조회수 3만 이상」·「수 09:40 기획 / 목 09:40 제작」을 손으로 적어 두면,
코드가 바뀐 뒤에도 **문서는 에러 없이 옛날 숫자를 계속 말한다.** 그래서 이 문서는
**살아 있는 값을 읽어서** 만든다.

  · 시드 채널 표 · 게이트 수치      collect.py 의 상수
  · 로테이션 4주                    build_page.SLOTS
  · 소품·표정 가짓수                build_t2.PROPS · assets/유삐
  · 현재 재고 건수                  out/pool/소재풀.csv
  · 스케줄 시각·요일·실행 명령       config/task_AX_Source_Weekly_0940.xml

**서술(왜 그렇게 정했나)만 이 파일에 있다.** 기준이 바뀌면 README 를 먼저 고치고
(README 가 정본), 코드를 맞춘 다음, 이걸 다시 돌린다.
"""
import argparse, io, os, re, sys, webbrowser
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_page as B
import collect as C
import llm as L
import pdfdoc as D

E = D.esc
TASK_XML = os.path.join(C.ROOT, "config", "task_AX_Source_Weekly_0940.xml")


def read_task():
    """스케줄러 정의에서 시각·요일·실행 명령을 읽는다. 없으면 (없음)."""
    out = {"시각": "(없음)", "요일": "(없음)", "명령": "(없음)", "작업폴더": "(없음)"}
    if not os.path.exists(TASK_XML):
        return out
    raw = io.open(TASK_XML, "rb").read()
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    s = raw.decode(enc, "replace")
    m = re.search(r"StartBoundary>[^T]*T(\d\d:\d\d)", s)
    if m:
        out["시각"] = m.group(1)
    days = re.findall(r"<(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*/>", s)
    ko = {"Monday": "월", "Tuesday": "화", "Wednesday": "수", "Thursday": "목",
          "Friday": "금", "Saturday": "토", "Sunday": "일"}
    if days:
        out["요일"] = " · ".join(ko[d] + "요일" for d in days)
    for k, tag in (("명령", "Command"), ("작업폴더", "WorkingDirectory")):
        m = re.search(tag + r">([^<]*)<", s)
        if m:
            out[k] = m.group(1)
    m = re.search(r"Arguments>([^<]*)<", s)
    if m:
        out["명령"] = (out["명령"] + " " + m.group(1)).strip()
    return out


def stock():
    """지금 원장에 무엇이 얼마나 있나. 파일이 없으면 0."""
    try:
        all_rows, rows, n_ex = B.load_rows()
    except SystemExit:
        return {"원장": 0, "게재": 0, "제외": 0, "축": {}}
    return {"원장": len(all_rows), "게재": len(rows), "제외": n_ex,
            "축": {ax: sum(1 for r in rows if r["축"] == ax) for ax in C.AXES}}


def build(out_html, out_pdf):
    t, st = read_task(), stock()
    H = []

    # ── 표지 ────────────────────────────────────────────────
    H.append(
        '<section class="cover">'
        '<div class="brand">DX팀 · AX 확산</div>'
        '<h1>AX_source<br>시스템 기획서</h1>'
        '<div class="lead">사내 AX 확산 세션(T1 부서장회의)과 정보채널(T2)의 '
        '<b>소재를 유튜브에서 캐 오고, 회차를 기획하고, 원고와 산출물까지 자동으로 만드는</b> 파이프라인.</div>'
        f'<div class="meta">{date.today():%Y년 %m월 %d일} 생성 · '
        f'살아 있는 값(채널·게이트·재고·스케줄)은 코드와 데이터에서 직접 읽었습니다<br>'
        f'현재 재고 — 원장 {st["원장"]}건 · 게재 {st["게재"]}건 '
        f'({" · ".join(f"{ax} {n}" for ax, n in st["축"].items())})<br>'
        f'배치 — 매주 {E(t["요일"])} {E(t["시각"])}<br>'
        f'기준 정본은 이 문서가 아니라 <b>README.md</b> 와 '
        f'<b>AX_source/docs/AX확산/02_확산_워크플로우.md §7.0</b> 입니다'
        '</div></section>')

    # ── 1. 무엇을 푸는가 ────────────────────────────────────
    H.append('<h2>1. 무엇을 푸는 프로젝트인가</h2>')
    H.append('<p>사내 AX 확산에는 <b>매주 돌아오는 자리</b>가 있다 — T1 부서장회의 '
             '「이달의 사례」와 T2 정보채널. 그 자리를 채울 소재를 사람이 매주 찾으면 '
             '<b>찾는 일이 곧 병목</b>이 되고, 바쁜 주에는 자리가 빈다.</p>')
    H.append('<div class="box"><h4>이 프로젝트가 만드는 것</h4>'
             '<p>유튜브에서 <b>실무자가 자기 업무를 실제로 바꾼 과정</b>을 캐 와서, '
             '한 회차를 기획하고, 발표 덱과 사내 채널 만화 원고까지 <b>목요일 아침에 자동으로</b> 만들어 둔다. '
             '사람은 <b>고치고 게시하는 일</b>만 한다.</p></div>')
    H.append('<h3>⚠️ 이 폴더는 역할이 둘이고 축 정의가 서로 다르다</h3>')
    H.append('<table><thead><tr><th>역할</th><th>하는 일</th><th>축 정의</th></tr></thead><tbody>'
             '<tr><td><b>① 쇼츠 발굴·제작</b><br>(원래 목적)</td>'
             '<td>터진 쇼츠 소재를 데이터로 찾아 정해진 컨셉으로 영상 제작</td>'
             '<td>축A 분석 자동화 / 축B <b>생성물(이미지·영상·음악)</b></td></tr>'
             '<tr><td><b>② AX 확산 A급 자동화</b><br>(이 문서의 대상)</td>'
             '<td>T1·T2 소재를 캐고 기획·원고·산출물까지</td>'
             '<td>분석 / 생성 — 여기서 <b>「생성」은 업무 산출물·시스템</b>이지 엔터 콘텐츠가 아니다</td></tr>'
             '</tbody></table>')
    H.append('<div class="box warn"><p><b>섞으면 안 된다.</b> 같은 「생성」이라는 말이 '
             '두 역할에서 다른 것을 가리킨다. ②의 기준 정본은 이 폴더가 아니라 '
             '<code>AX_source/docs/AX확산/02_확산_워크플로우.md §7.0</code> 이다.</p></div>')
    H.append('<h3>축 정의 (②)</h3>'
             '<table><thead><tr><th>축</th><th>정의</th></tr></thead><tbody>'
             + "".join(f'<tr><td><b>{ax}</b></td><td>{B.AXIS_DEF[ax]}</td></tr>' for ax in C.AXES)
             + '</tbody></table>')

    # ── 2. 소재 수집 ────────────────────────────────────────
    H.append('<h2>2. 소재 수집 — 왜 검색이 아니라 채널인가</h2>')
    H.append('<p>2026-09-08 에 기준을 전면 개정했다. 계기는 <b>사용자가 지정한 레퍼런스 2건이 '
             '옛 기준에 3중으로 걸려 탈락한 것</b>이다 — 길이 600초 초과, 성과등급 미달, '
             '검색어가 툴 how-to 뿐. 원장 243건을 다시 재보니 <b>10분 초과 0건 · 60초 이하 149건(61%)</b> 으로, '
             '원하는 종류가 <b>구조적으로 한 건도 못 들어오는 상태</b>였다.</p>')
    H.append('<h3>검색어를 버리고 채널을 훑는 이유 — 실측 3가지</h3>'
             '<ol>'
             '<li><b>검색어로는 분석/생성이 안 갈린다.</b> 축별 검색어 8개를 나눠 돌렸더니 '
             '상위 22건 중 <b>11건이 같은 영상</b>이었다. 두 축은 검색이 아니라 <b>판정 단계</b>에서 갈라야 한다.</li>'
             '<li><b>레퍼런스 2건 모두 특정 채널의 연재물</b>이었다 — 한 채널 안에 분석과 생성이 한 쌍으로 있다.</li>'
             '<li><b>비용이 1/20 이다</b> — 검색어 1개 101 units vs 채널 1개 5~6 units.</li>'
             '</ol>')
    H.append(f'<h3>시드 채널 {len(C.SEED_CHANNELS)}개 <span class="small dim">'
             f'(정본은 AX확산 계획(docs/AX확산) §7.0 표. 분기 1회 재점검)</span></h3>'
             '<table><thead><tr><th>#</th><th>채널</th><th>넣은 근거</th></tr></thead><tbody>'
             + "".join(f'<tr><td class="n">{i}</td><td><b>{E(n)}</b></td><td>{E(w)}</td></tr>'
                       for i, (n, _, w) in enumerate(C.SEED_CHANNELS, 1))
             + '</tbody></table>')
    H.append('<div class="box warn"><p><b>성과지수(조회수÷구독자)를 게이트에서 뺐다.</b> '
             '분석 레퍼런스가 0.44배라 컷을 아무리 낮춰도 안 잡혔기 때문이다. '
             '대가는 「작은 채널이 터뜨린 것」이라는 선별 원리가 사라진 것 — '
             '<b>이제 품질은 시드 채널 선정이 결정한다.</b></p></div>')
    H.append('<h3>수집 게이트 <span class="small dim">(통과 못 하면 원장에 아예 안 들어간다)</span></h3>'
             '<table><thead><tr><th>항목</th><th>값</th><th>왜</th></tr></thead><tbody>'
             f'<tr><td>길이</td><td class="n">{C.MIN_SEC}~{C.MAX_SEC}초 '
             f'({C.MIN_SEC//60}~{C.MAX_SEC//60}분)</td>'
             '<td>그 아래는 사례가 아니라 툴 팁, 그 위는 세션에서 인용하기 어렵다</td></tr>'
             f'<tr><td>조회수</td><td class="n">{C.MIN_VIEWS:,} 이상</td>'
             '<td>절대 하한. 성과지수 대신 남은 유일한 수치 컷</td></tr>'
             f'<tr><td>제목 한글</td><td class="n">{C.MIN_HANGUL}자 이상</td>'
             '<td>영어권·공장 자동화 영상 차단</td></tr>'
             f'<tr><td>부정 소재</td><td class="n">금지어 {len(C.NEGATIVE)}개</td>'
             '<td>실패·오류·환각 등 — <b>수집 자체를 금지</b>한다</td></tr>'
             f'<tr><td>광고·낚시</td><td class="n">금지어 {len(C.PROMO)}개</td>'
             '<td>협찬·최저가·수익화 등</td></tr>'
             '<tr><td>구독자</td><td class="n">상한 없음</td>'
             '<td>오빠두엑셀(169만)을 넣으려고 v4.2 에서 해제</td></tr>'
             '</tbody></table>')

    # ── 3. 파이프라인 ───────────────────────────────────────
    H.append('<h2 class="pagebreak">3. 파이프라인 — 어디까지가 기계이고 어디부터 LLM인가</h2>')
    H.append('<div class="box plan"><p><b>채널을 훑어 자료를 모아 오는 데까지가 파이프라인이다.</b> '
             '무엇을 할 회차인지 정하고, 한 쌍을 고르고, 원고를 쓰는 것부터는 LLM 이 한다. '
             '<b>그리고 그 결과를 사람이 승인해야 산출물이 나온다.</b></p></div>')
    H.append('<h3>한 회차 = 이틀</h3>'
             '<table><thead><tr><th>언제</th><th>배치</th><th>하는 일</th></tr></thead><tbody>'
             f'<tr><td class="n"><b>수 {E(t["시각"])}</b></td>'
             '<td><code>run_plan.bat</code></td>'
             '<td>수집 → 회차 기획 → <b>기획서 PDF</b> → 추천 페이지 → 자체 점검</td></tr>'
             '<tr><td class="n">—</td><td><b>사람</b></td>'
             '<td>기획서를 읽고 회차 폴더의 <code>승인.bat</code> 을 누른다</td></tr>'
             f'<tr><td class="n"><b>목 {E(t["시각"])}</b></td>'
             '<td><code>run_weekly.bat</code></td>'
             '<td><b>승인됐을 때만</b> T1 덱 → T2 툰 → 기획서 갱신 → 추천 페이지 → 자체 점검</td></tr>'
             '</tbody></table>')
    H.append('<div class="box warn"><h4>회차 폴더는 날짜가 아니라 「그 주 수요일」이다</h4>'
             '<p><code>date.today()</code> 로 잡으면 <b>수요일 기획과 목요일 산출물이 다른 폴더로 '
             '갈리고</b>, 목요일 빌드가 기획을 못 찾아 <b>조용히 새로 기획해 버린다</b>. '
             '파일 이름도 회차일로 쓴다.</p>'
             '<p><b>승인도 회차 폴더에 매인다</b> — 다음 수요일이면 폴더가 바뀌므로 '
             '지난 승인은 따라오지 않는다. 회차마다 다시 승인한다.</p></div>')
    H.append('<div class="flow">'
             '<div class="st"><div class="no">기계 · STEP 1</div>'
             '<span class="t">수집 <code>tools/collect.py</code></span>'
             '<div class="d">시드 채널을 훑어 올해 업로드분을 받아 게이트를 통과한 것만 원장에 쌓는다. '
             '축 판정(분석/생성)도 여기서 한다. 회차당 약 40 units.<br>'
             '→ <code>out/pool/소재풀.csv</code> · <code>소재카탈로그.md</code></div></div>'
             '<div class="st"><div class="no">LLM · STEP 2</div>'
             '<span class="t">기획 <code>llm.plan_session()</code></span>'
             '<div class="d">게재 통과 <b>전량</b>을 읽고 「이번 회차는 무엇에 대한 회차인가」를 먼저 정한 뒤, '
             '그 기획에 맞는 분석 1 + 생성 1과 <b>제친 후보</b>를 낸다.<br>'
             '→ <code>out/&lt;날짜&gt;/llm/01_기획.json</code></div></div>'
             '<div class="st"><div class="no">기계 · STEP 3</div>'
             '<span class="t">자료 정독 <code>collect.fetch_details()</code></span>'
             '<div class="d">고른 두 건만 <b>설명 전문</b>을 다시 받는다. 원장의 설명은 수집 때 300자로 잘려 있어 '
             '원고 근거로 얕다. 1 unit.<br>→ <code>llm/00_자료전문.json</code></div></div>'
             '<div class="st"><div class="no">LLM · STEP 4~6</div>'
             '<span class="t">원고 <code>llm.write_t1()</code> · <code>write_t2()</code></span>'
             '<div class="d">기획과 전문을 근거로 T1 덱 원고 1회, T2 툰 원고 축별 1회씩.<br>'
             '→ <code>T1_대본.json</code> · <code>T2_대본.json</code> '
             '<b>(사람이 고치는 파일)</b></div></div>'
             '<div class="st"><div class="no">사람 · 승인</div>'
             '<span class="t">승인 <code>tools/approve.py</code> (회차 폴더의 <code>승인.bat</code>)</span>'
             '<div class="d">관리자가 기획서를 읽고 누른다. <b>없으면 목요일 배치가 아무것도 안 만든다</b> — '
             '실패가 아니라 대기다.<br>→ <code>out/&lt;회차&gt;/승인.json</code></div></div>'
             '<div class="st"><div class="no">기계 · STEP 7</div>'
             '<span class="t">구간 클립 <code>tools/clip.py</code></span>'
             '<div class="d">승인된 재생 구간만 <b>mp4 로 잘라 덱에 심는다</b>. '
             'file:// 에서 유튜브가 임베드를 거부(오류 153)하던 것을 이걸로 푼다 — '
             '인터넷 없는 회의실에서도 돈다.<br>→ <code>out/&lt;회차&gt;/clips/</code></div></div>'
             '<div class="st"><div class="no">기계 · STEP 8~10</div>'
             '<span class="t">렌더 <code>build_t1</code> · <code>build_page</code> · <code>build_brief</code></span>'
             '<div class="d">덱 HTML(폰트·썸네일 내장, playwright) · 추천 페이지 · 회차 기획서 PDF. <b>툰은 여기 없다</b> — GPT 가 따로 만든다(§4).</div></div>'
             '<div class="st"><div class="no">기계 · STEP 10</div>'
             '<span class="t">자체 점검 <code>tools/self_test.py</code></span>'
             '<div class="d">레퍼런스 2건이 각 축 상위에 있는지 · 축별 재고 · 부정 유입 0건 · 배치 콘솔 규약.</div></div>'
             '</div>')
    H.append('<div class="box warn"><h4>배치 순서를 바꾸면 안 되는 이유</h4>'
             '<p>추천 페이지가 <b>마지막</b>인 것은, 「회차별 보기」 칩이 <b>그 순간 폴더에 있는 '
             '파일만</b> 걸기 때문이다. 순서를 바꾸면 <b>파일은 멀쩡한데 그 회차 칩이 비어 있다.</b></p></div>')

    # ── 4. LLM 경계 ─────────────────────────────────────────
    H.append('<h2>4. LLM 이 들어간 자리와 그 경계</h2>')
    H.append('<p>호출은 로컬 <code>claude -p</code> 헤드리스다. 회차당 <b>LLM 4회 + YouTube 1 unit</b>. '
             '컨셉·회사 맥락은 코드가 아니라 <code>config/LLM_컨셉.md</code> 에 있고 '
             '프롬프트에 통째로 들어간다 — <b>그 파일을 고치면 넷이 다 같이 바뀐다.</b></p>')
    H.append('<h3>넘기지 않은 것 — 판을 지키는 세 층</h3>'
             '<table><thead><tr><th>층</th><th>무엇을 막나</th></tr></thead><tbody>'
             '<tr><td><b>닫힌 어휘</b></td><td>T1 덱의 도형·막 이름은 <b>목록 밖이면 기본값으로 내린다</b> — 이름이 틀리면 그 장이 빈다</td></tr>'
             '<tr><td><b>길이 자르기</b></td><td>T1 덱은 슬라이드 폭·줄 수가 정해져 있다 — 제목 40자 · 단계 이름 26자 · 설명 44자에서 자르고 <b>무엇을 잘랐는지 화면에 찍는다</b></td></tr>'
             '<tr><td><b>재생 구간</b></td><td>시작≥끝 · 영상 길이 밖 · 5분 초과 구간은 '
             '<b>버린다</b>. 찍어서 적은 구간을 실으면 <b>회의에서 엉뚱한 데가 재생되는데 '
             '파일은 멀쩡하다</b></td></tr>'
             '<tr><td><b>환각 차단</b></td><td>후보 목록에 없는 영상ID 를 부르면 기획을 통째로 무르고 '
             '<code>fit()</code> 1위로 되돌아간다 — 안 막으면 <b>엉뚱한 영상이 에러 없이</b> 실린다</td></tr>'
             '</tbody></table>')
    H.append('<div class="box"><h4>못 돌면 멈추지 않고 되돌아간다</h4>'
             '<p>claude 미설치 · 타임아웃 · JSON 회수 실패 · 환각 — 전부 <b>기계 초안</b>(챕터 자르기)으로 '
             '조용히 되돌아간다. 배치는 이것 때문에 멈추지 않는다. '
             '끄려면 <code>--no-llm</code>, 캐시를 버리고 다시 쓰려면 <code>--llm-refresh</code>.</p>'
             '<p class="small dim">호출은 <code>--strict-mcp-config</code> 로 커넥터를 안 띄우고, '
             '출력을 파이프가 아니라 <b>파일로</b> 받는다 — counsel_report 가 2026-07-01 에 '
             '손자 프로세스가 파이프를 물어 무한 대기한 선례가 있다.</p></div>')
    H.append('<div class="box warn"><h4>fit() 은 왜 선택에서 빠졌나</h4>'
             '<p>처음엔 <code>fit()</code> 상위 8건만 LLM 에게 줬다. 그건 기획이 아니라 '
             '<b>기계 점수가 좁혀 놓은 것 중 고르기</b>다 — 낱말 점수가 놓친 사례는 애초에 후보에 못 든다. '
             '전량으로 바꾸자 <b>생성축 선택이 실제로 바뀌었다</b>(2026-09-09 실측). '
             '지금 <code>fit()</code> 은 화면 표시와 self_test(수집 게이트 감시)로만 남는다.</p></div>')

    # ── 5. 산출물 ───────────────────────────────────────────
    H.append('<h2 class="pagebreak">5. 산출물과 사람이 고치는 자리</h2>')
    H.append('<table><thead><tr><th>#</th><th>산출물</th><th>파일</th><th>누가 쓰나</th></tr></thead><tbody>'
             '<tr><td class="n">①</td><td><b>소재추천</b></td><td><code>소재추천.html</code> (폴더 맨 위)</td>'
             '<td>만드는 사람 — 기획·후보를 훑는다</td></tr>'
             '<tr><td class="n">②</td><td><b>T1 부서장회의 덱</b></td>'
             '<td><code>out/&lt;날짜&gt;/T1_부서장회의_&lt;날짜&gt;.html</code></td>'
             '<td>발표자 — 13분 세션 + 질의응답 10분</td></tr>'
             '<tr><td class="n">③④</td><td><b>T2 정보채널 인스타툰</b></td>'
             '<td><code>T2_정보채널_&lt;축&gt;_&lt;날짜&gt;.png</code> + <code>_02</code>~ · 뷰어 <code>.html</code> · 12쪽 <code>.pdf</code></td>'
             '<td>사내 채널 게시물 — <b>2026-09-10 부터 GPT 가 그림까지 만든다</b>. 축마다 12장(표지 1 + 이야기 10 + 댓글 1)</td></tr>'
             '<tr><td class="n">⑤</td><td><b>회차 기획서</b></td>'
             '<td><code>out/&lt;날짜&gt;/기획서_&lt;날짜&gt;.pdf</code></td>'
             '<td><b>관리자 — 읽고 승인하는 자리</b></td></tr>'
             '<tr><td class="n">⑥</td><td><b>공개본 (GitHub Pages)</b></td>'
             '<td><code>axs/&lt;slug&gt;/</code> — 위 ①②③④⑤ 를 한 벌로. <code>tools/publish.py</code></td>'
             '<td>세션 참석자 — 링크 하나로 연다. <b>승인된 회차만</b> 올라간다</td></tr>'
             '<tr><td class="n">참고</td><td><b>GPT 비교판</b></td>'
             '<td><code>out/&lt;회차&gt;/test/</code></td>'
             '<td>모델 비교용 — <b>게시본이 아니고 페이지에도 안 걸린다</b></td></tr>'
             '</tbody></table>')
    H.append('<div class="box warn"><h4>전부 초안이다 — 사람이 고치는 것까지가 한 세트</h4>'
             '<p>LLM 은 <b>영상 제목·챕터·설명만</b> 보고 쓴다. 우리 팀 실제 사정은 모른다. '
             '고치는 자리는 <code>T1_대본.json</code> 과 <code>T2_대본.json</code> 두 파일이고, '
             '고치고 다시 돌리면 <b>고친 내용이 유지된다</b>(<code>--reset</code> 해야 초안 복귀).</p>'
             '<p><b>우리 데이터가 실명으로 새면 안 된다</b> — 센터명·매출액·학생수는 원고에 넣지 않고 '
             '「센터별 실적표」처럼 종류만 말한다. 촬영·캡처가 필요하면 더미 데이터로 같은 화면을 재현한다.</p>'
             '<p><b>⑥ 공개본은 인터넷에 올라간다</b> — GitHub Pages 는 비공개 발행이 안 된다. '
             '가림막은 <b>추측 불가 경로 + <code>noindex</code></b> 둘뿐이고 <b>PDF·이미지에는 메타를 못 넣는다.</b> '
             'T1 덱에는 <b>AX 확산 전술표 전문</b>이 들어 있다 — <b>URL 을 사내 밖으로 내보내지 않는 것</b>이 '
             '유일한 실제 통제다. 원고에 우리 데이터를 안 넣는 규칙이 여기서 두 배로 중요해진다.</p></div>')
    H.append('<h3>툰은 T1 덱과 같은 이야기를 한다 <span class="small dim">'
             '(2026-09-10)</span></h3>'
             '<p>같은 주에 세션에서 보고 채널에서 또 보는 사람이 <b>두 사례로 읽으면</b> '
             '확산이 아니다. 그런데 툰 원고가 실제로 T1 과 다른 이야기를 하고 있었다 — '
             '프롬프트가 T1 단계를 <b>근거로만</b> 주고, 그 아래 이야기 흐름 표는 따로 '
             '「그래서 해봤다 → 첫 난관 → 다시 잡았다」를 지시해서 <b>표가 이겼다</b>. '
             '지금은 T1 <b>다섯 단계가 본문 다섯 장에 하나씩</b> 들어간다.</p>'
             '<table><thead><tr><th>장</th><th>1</th><th>2</th><th>3</th><th>4</th>'
             '<th>5</th><th>6</th><th>7</th><th>8</th><th>9</th><th>10</th><th>11</th>'
             '<th>12</th></tr></thead><tbody><tr><td class="n">무엇</td>'
             '<td><b>표지</b></td><td>후킹</td><td>고생</td>'
             '<td><b>T1-1</b></td><td><b>T1-2</b></td><td>의심</td><td><b>T1-3</b></td>'
             '<td>인정</td><td><b>T1-4</b></td><td><b>T1-5</b></td><td>메시지</td>'
             '<td>댓글</td></tr></tbody></table>'
             '<p class="small dim">장마다 <code>단계</code>(0~5)를 적고, 빠지면 콘솔이 '
             '찍는다. 회차 기획서 T2 표의 <b>「T1 단계」 칸</b>에서 승인 전에 대조한다.</p>')
    H.append('<div class="box warn"><h4>「단계 5개 모두 실렸습니다」가 맞았다는 뜻은 아니다</h4>'
             '<p>세는 것은 <b>LLM 이 스스로 붙인 번호</b>다 — <b>번호만 맞고 문장은 다른 단계</b>인 '
             '경우를 못 잡는다. 두 번 다시 쓴 뒤에도 분석 4·6장(2↔3단계)과 생성 9장(5단계)이 '
             '그랬고, <code>T2_대본.json</code> 에서 세 줄을 고쳐 맞췄다. '
             '<b>대조는 사람이 하는 자리</b>이고, 고친 대본은 유지된다.</p></div>')
    H.append('<h3>T2 인스타툰 — GPT 로 갈아탔다 <span class="small dim">'
             '(2026-09-10)</span></h3>'
             '<p><b>툰은 이제 GPT 가 그림까지 만든다.</b> 그 전에는 이 폴더가 원고(LLM)와 '
             '그림(SVG 렌더러 + 캐릭터 PNG 합성)을 둘 다 들고 있었다 — 원고 프롬프트 154줄 · '
             '렌더러 1,204줄 · 배경 생성기 357줄 · 캐릭터 자산 8.9MB. 그림을 GPT 가 그리면 '
             '<b>전부 죽은 코드</b>라 <code>archive/20260910_t2/</code> 로 옮겼다.</p>'
             '<table><thead><tr><th>걷어낸 것</th><th>무엇이었나</th></tr></thead><tbody>'
             '<tr><td><code>llm.write_t2()</code></td><td>원고 프롬프트 — 판 규칙 · 12장 흐름표 · '
             '표지 규칙 · 구도/표정/단계 검문. <b>전부 우리 렌더러를 전제한 규칙</b>이었다</td></tr>'
             '<tr><td><code>build_t2.py</code></td><td>장면판 렌더러 + 대본 관리 + 낱장 PNG · 뷰어</td></tr>'
             '<tr><td><code>draw_bg.py</code> · <code>assets/배경</code></td>'
             '<td>구도 10종 배경 SVG (LLM 이 그리던 것)</td></tr>'
             '<tr><td>캐릭터 자산 · 슬라이서 3종</td><td>표정 9종 · 회색 곰 상사 · 배경 제거 도구</td></tr>'
             '<tr><td><code>gpt.py</code></td><td>codex 비교판 — <b>비교가 아니라 제작</b>이 되면서 역할이 끝났다. '
             '다만 <code>codex exec</code> 호출부(ChatGPT 로그인 · PATH 핀)는 새 도구의 출발점이다</td></tr>'
             '</tbody></table>'
             '<p class="small dim">⚠️ 새 프롬프트는 2026-09-10 에 받았다(사용자 제공 제작기준). '
             '아래가 지금 도는 체계다.</p>')
    H.append('<h3>인스타툰 — 지금은 이렇게 만든다 <span class="small dim">'
             '(2026-09-10 · 첫 회차 24장)</span></h3>'
             '<p><b>그림은 사람이 ChatGPT 창에서 굽는다.</b> codex 는 코딩 에이전트라 그림을 못 만들고 '
             '이 PC 엔 이미지 API 키가 없다. 그래서 파이프라인은 <b>붙일 것을 차려 놓고</b>, '
             '<b>받아 온 그림을 회차에 꽂는다.</b></p>'
             '<table><thead><tr><th>단계</th><th>누가</th><th>무엇</th></tr></thead><tbody>'
             '<tr><td>원고 12장</td><td>기계</td><td>회차 기획서 §4 에 실린 그 문장</td></tr>'
             '<tr><td>연출 3칸</td><td>기계</td><td><code>llm.write_toon_direction()</code> — '
             '화면문구·메모문구·장면설명. <b>그림 규칙이 아니라 컷 서술</b>이다</td></tr>'
             '<tr><td>장별 프롬프트 24개</td><td>기계</td><td><code>build_toon_prompt.py</code> — '
             '1장은 전문, 2장부터 8줄 블록. 첨부물도 한 폴더에 모아 준다</td></tr>'
             '<tr><td><b>그림 24장</b></td><td><b>사람</b></td><td>새 대화 · 첨부 · '
             '<b>한 장 굽고 확인 → 다음 장</b></td></tr>'
             '<tr><td>정리·검사·발행</td><td>기계</td><td><code>collect_toon.py</code> — 이름 규약 · '
             '1:1/1080px · 뷰어 HTML · 12쪽 PDF</td></tr>'
             '</tbody></table>'
             '<p class="small dim"><b>정본 자리</b> — 그림 프롬프트는 '
             '<code>config/인스타툰_마스터.md</code>(코드가 아니다) · 화풍은 '
             '<code>assets/인스타툰/레퍼런스_판/</code>(스크린샷 원본이 아니라 크롭본) · '
             '캐릭터와 품질 가이드는 그 옆 폴더. 회차마다 안 바뀐다.</p>')
    H.append('<div class="box warn"><h4>첫 회차에서 실제로 난 일 — 전부 «한 장씩»이라 한 장만 다시 뽑았다</h4>'
             '<ul>'
             '<li><b>4장에서 캐릭터가 사람으로 바뀌었다</b> — 대화가 길어지자 레퍼런스 인물을 주인공으로 '
             '오해했다. <b>승인한 1장을 기준판으로 다시 첨부</b>해 복구한다</li>'
             '<li><b>달력에 「2024」</b>가 박혔다(2026년 회차인데) → 마스터에 <b>날짜·연도 숫자 금지</b></li>'
             '<li><b>상사가 6장엔 안경 없고 8장엔 있었다</b> → <b>안경 쓴 회색 곰</b>으로 고정. '
             '첫 등장 판이 곧 기준이다</li>'
             '<li><b>생성축 2장에 분석축 원고</b>가 들어갔다 → 축을 바꿀 땐 <b>새 대화</b>에서 1장부터</li>'
             '<li>일부 장이 <b>1024px</b> 로 왔다 → <code>--upscale</code>(원본은 따로 보관). '
             '다시 뽑으면 내용이 또 흔들린다</li>'
             '</ul>'
             '<p class="small dim">⚠️ <b>두 축을 다른 도구로 만들면 화풍이 갈린다</b> — 첫 회차가 '
             '분석=ChatGPT · 생성=Gemini 였다. 한 회차는 한 도구로 통일한다.</p></div>')
    H.append('<h3>① 소재추천 페이지의 순서 <span class="small dim">(2026-09-10 재배치)</span></h3>'
             '<table><thead><tr><th>#</th><th>절</th><th>무엇</th></tr></thead><tbody>'
             '<tr><td class="n">1</td><td><b>머리 칩</b></td><td>로테이션 주차 · 후보/축별 건수 · 시드 채널 — 누르면 그 절로 간다</td></tr>'
             '<tr><td class="n">—</td><td><b>상단 메뉴</b></td><td><b>2026-09-10 삭제.</b> 「회차별 보기」 칩이 같은 파일을, 그것도 지난 회차까지 열어 <b>같은 링크를 두 번 그리는 자리</b>였다</td></tr>'
             '<tr><td class="n">2</td><td><b>회차별 보기</b></td><td>회차를 골라 그 회차의 <b>기획과 산출물 링크</b>를 본다</td></tr>'
             '<tr><td class="n">3</td><td><b>이번 주 한 쌍 · 대안</b></td><td>이번 회차 기획과 선정·제침 근거</td></tr>'
             '<tr><td class="n">4</td><td><b>시드 채널 · 4주 로테이션 · 게재 기준</b></td>'
             '<td>판을 정하는 값들 — 고치는 자리는 여기가 아니라 코드·§7.0 이다</td></tr>'
             '</tbody></table>')
    H.append('<div class="box"><h4>「회차별 보기」가 왜 맨 위인가</h4>'
             '<p>페이지는 <b>매주 덮어쓰인다.</b> 지난 회차를 다시 보는 자리가 이 절밖에 없는데, 이걸 페이지 맨 아래에 두면 <b>아무도 안 내려간다</b> — 회차 폴더를 직접 뒤지라고 했을 때 아무도 안 뒤진 것과 같은 종류의 실패다. 그래서 2026-09-10 에 머리 칩 바로 아래로 올렸다.</p>'
             '<p class="small dim">그 자리에 있던 「N주차 = 이달의 사례」 안내 줄은 <b>삭제</b>했다 — 머리 칩(로테이션)과 아래 4주 로테이션 표가 이미 같은 말을 두 번 하고 있었다. <code>slot_desc</code> 값 자체는 <code>session()</code> 이 계속 들고 있고 T1·T2 가 쓴다.</p></div>')
    H.append('<h3>4주 로테이션 — 유튜브가 채우는 건 절반뿐이다</h3>'
             '<table><thead><tr><th>주차</th><th>포맷</th><th>소재</th></tr></thead><tbody>'
             + "".join(f'<tr><td class="n">{k}주</td><td><b>{E(v[0])}</b></td>'
                       f'<td>{"🌐 유튜브" if v[1] else "🔒 사내 전용"} — {E(v[2])}</td></tr>'
                       for k, v in sorted(B.SLOTS.items()))
             + '</tbody></table>')
    H.append('<div class="box warn"><p><b>3·4주차 자리가 뚫리면 T1 은 「AI 뉴스 브리핑」이 되고 '
             '확산 기능이 사라진다.</b> 소재가 없으면 유튜브로 대체하는 게 아니라 '
             '3주차 포맷을 한 번 더 쓴다. 세 스크립트가 그 회차엔 스스로 건너뛴다 — 실패가 아니다.</p></div>')

    # ── 6. 운영 ─────────────────────────────────────────────
    H.append('<h2>6. 운영</h2>')
    H.append('<table><thead><tr><th>항목</th><th>값</th></tr></thead><tbody>'
             f'<tr><td>실행</td><td>매주 <b>수 {E(t["시각"])}</b> 기획 '
             f'(<code>AX_Source_Plan_Wed_0940</code>) · '
             f'<b>{E(t["요일"])} {E(t["시각"])}</b> 제작 '
             f'(<code>AX_Source_Weekly_0940</code>)</td></tr>'
             '<tr><td>제작 조건</td><td><b>승인된 회차만.</b> 승인이 없으면 '
             '아무것도 만들지 않고 끝난다 — 실패가 아니다</td></tr>'
             f'<tr><td>실행 명령</td><td><code>{E(t["명령"])}</code></td></tr>'
             f'<tr><td>작업 폴더</td><td><code>{E(t["작업폴더"])}</code></td></tr>'
             '<tr><td>회차 비용</td><td>YouTube 약 <b>41 units</b>(수집 40 + 자료 1) · '
             'LLM <b>4회</b> · 일 한도 10,000 units</td></tr>'
             '<tr><td>로그</td><td><code>out/logs/plan_&lt;날짜&gt;.log</code> · '
             '<code>weekly_&lt;날짜&gt;.log</code> (+ <code>console_*.out</code>)</td></tr>'
             '<tr><td>실패 시</td><td>수집·페이지 실패는 <b>중단 + 알림</b>, '
             'T1·T2 실패는 <b>경고만 하고 계속</b></td></tr>'
             '</tbody></table>')
    H.append('<div class="box warn"><h4>스케줄러가 배치를 직접 물지 않는다</h4>'
             '<p><code>wscript //B tools/run_hidden.vbs &lt;배치이름&gt;</code> 로 <b>창 없이</b> 돌리고 '
             '콘솔 출력을 파일로 돌린다. 러너 하나가 <b>배치 이름을 인자로 받아</b> 둘을 다 문다. 작업 디렉터리 경로 끝에 백슬래시를 넣으면 <b>0x8007010B 로 즉시 실패</b>한다.</p>'
             '<p><b>목요일 09:40 은 API 할당량 리셋(한국시간 16~17시) 전이다.</b> '
             '지금은 회차당 41 units 라 여유가 크지만, 보조 검색(1회 812 units)을 붙이면 위험이 되살아난다.</p></div>')

    # ── 7. 함정 ─────────────────────────────────────────────
    H.append('<h2>7. 밟은 함정 — 전부 「에러가 안 나는」 종류다</h2>')
    H.append('<p class="dim">이 목록이 이 문서에서 가장 값이 나가는 부분이다. '
             '아래는 모두 <b>정상 종료했는데 결과만 틀렸던</b> 일들이다.</p>')
    H.append('<table><thead><tr><th>무엇이</th><th>어떻게 드러났나</th><th>지금</th></tr></thead><tbody>'
             '<tr><td><b>배치 파일에 한글</b></td>'
             '<td>cp949 콘솔에서 cmd 가 멀티바이트 줄마다 오프셋이 밀려 <code>if not exist</code> 가 '
             '<code>xist</code> 로 실행되고 <b>한 단계가 조용히 건너뛰어졌다</b></td>'
             '<td>배치는 ASCII 전용 · 한글은 <code>say.py</code> · self_test 가 기계로 막는다</td></tr>'
             '<tr><td><b>덱을 파일로 열기</b></td>'
             '<td><code>file://</code> 에서 유튜브가 임베드를 거부해 <b>오류 153</b>만 뜬다</td>'
             '<td><code>열기.bat</code> 이 로컬 서버로 띄운다</td></tr>'
             '<tr><td><b>그림을 직접 그렸다</b> <span class="small dim">(폐기)</span></td>'
             '<td>말풍선이 조용히 잘리고, 배경이 「골강판」으로 보이고, 파일명 한 글자에 그림이 조용히 안 바뀌었다 — 전부 <b>스크린샷이라 에러가 없는</b> 종류였다</td>'
             '<td><b>그림을 GPT 에게 넘겼다</b>(2026-09-10) — 렌더러를 들고 있지 않으면 이 함정들이 통째로 사라진다</td></tr>'
             '<tr><td><b>설명 300자 절단</b></td>'
             '<td>수집 때 잘려 저장돼 <b>원고가 제목 수준을 못 넘었다</b> (원장 평균 297자 = 사실상 전부)</td>'
             '<td>고른 두 건만 전문을 다시 받는다 (실측 1,706자 · 774자)</td></tr>'
             '<tr><td><b>캐시를 이름으로 물림</b></td>'
             '<td>기획을 다시 돌려 한 쌍이 바뀌었는데 <b>T2 대사가 통째로 이전 사례였다</b>. '
             '<code>--reset</code> 은 대본만 되돌릴 뿐 캐시를 안 건드린다</td>'
             '<td>캐시를 <b>프롬프트 해시</b>로 물린다 (<code>&lt;tag&gt;.key</code>). '
             '자료 전문도 이번 쌍을 덮는지 확인한다</td></tr>'
             '<tr><td><b>생성축 기준이 없었다</b></td>'
             '<td>「기성 도구에 서식 등록」이 「시스템을 직접 만든 것」을 밀어냈다 — '
             '둘 다 「없던 산출물을 만들었다」에 맞아서 <b>정의만으론 안 갈렸다</b></td>'
             '<td>컨셉에 <b>1순위=직접 만든 것</b>을 명시</td></tr>'
             '<tr><td><b>회차 폴더를 오늘 날짜로</b></td>'
             '<td>수요일 기획과 목요일 산출물이 <b>다른 폴더로 갈려</b> 목요일 빌드가 기획을 '
             '못 찾고 <b>조용히 새로 기획한다</b></td>'
             '<td>폴더·파일명 모두 <b>그 주 수요일</b>로 (<code>round_day()</code>)</td></tr>'
             '<tr><td><b>self_test 가 배치 하나만</b></td>'
             '<td>배치가 둘이 되자 <b>새 배치는 무검사</b>인데 PASS 가 떴다</td>'
             '<td>둘 다 검사하고 검사명에 파일 이름을 붙인다</td></tr>'
             '<tr><td><b>넓은 컷에 반반 크기표</b></td>'
             '<td>1080px 폭에 작은 그림 하나가 뜨고 <b>가로가 텅 빘다</b></td>'
             '<td>넓은 컷 전용 표 + 소품 없으면 가운데로</td></tr>'
             '<tr><td><b>구간만 내려받기</b></td>'
             '<td>yt-dlp 가 m3u8 로 붙어 <b>13초짜리가 4분을 넘겨도 안 끝났다</b></td>'
             '<td>480p 전체(26MB·https)를 받아 <b>로컬에서 자르고 원본은 지운다</b></td></tr>'
             '<tr><td><b>3주차 잠금 해제의 대가</b></td>'
             '<td>「성공만 매주 보고하면 실적 보고회가 된다」를 막던 자리가 사라졌다. '
             'T2 세 번째 막이 그 일을 이어받았는데 <b>그 막마저 「결과물 안내」로 바뀌었다</b>'
             '(2026-09-09 오후)</td>'
             '<td><b>미해결.</b> 실패·한계를 말하는 자리를 어디에 둘지 정해야 한다</td></tr>'
             '<tr><td><b>메뉴 링크 폴더</b><br><span class="small dim">(메뉴는 그 뒤 삭제)</span></td>'
             '<td>파일 이름은 <b>회차일</b>인데 폴더는 <b>오늘</b>로 지어, '
             '<b>목요일 배치가 만든 페이지에서만</b> ②③④ 가 전부 「미생성」으로 떴다 — '
             '파일은 다 있는데 링크만 죽고 배치는 정상 종료한다</td>'
             '<td>경로를 따로 짓지 않고 <code>relpath(path, ROOT)</code> 로 그대로 쓴다 · '
             'self_test ⑧ 이 나간 페이지의 nav 를 검사</td></tr>'
             '<tr><td><b>배치 순서 뒤바뀜</b></td>'
             '<td>파일은 멀쩡한데 메뉴가 매주 <b>「미생성」</b>으로 뜬다</td>'
             '<td>collect → T1 → T2 → page → self_test 고정</td></tr>'
             '</tbody></table>')

    # ── 8. 다음 ─────────────────────────────────────────────
    H.append('<h2>8. 기준을 바꿀 때</h2>')
    H.append('<ol>'
             '<li><b>README.md 를 먼저 고친다</b> — 이 폴더의 정본이다. '
             '수집 기준은 <code>AX_source/docs/AX확산/02_확산_워크플로우.md §7.0</code> 이 위에 있다.</li>'
             '<li>코드를 맞춘다. 기획 방향만 바꾸는 것이면 <b>코드가 아니라 '
             '<code>config/LLM_컨셉.md</code></b> 다.</li>'
             '<li><code>python tools/self_test.py</code> 로 레퍼런스 2건이 아직 상위에 있는지 본다. '
             '<b>점수표를 고쳐서 통과시키는 게 목적이 아니다</b> — 밀려났으면 왜 밀렸는지를 먼저 본다.</li>'
             '<li>같은 날 재수집은 <code>out/scan_*.csv</code> 를 덮어쓴다. '
             '기준을 바꿔 다시 돌리기 전에 옮겨 둔다.</li>'
             '<li>이 문서를 다시 뽑는다 — <code>python tools/build_design_doc.py</code></li>'
             '</ol>')
    H.append('<p class="small dim">이 문서의 표·수치는 <b>코드와 데이터에서 직접 읽은 값</b>이다 '
             '(시드 채널·게이트·로테이션·소품/표정 가짓수·재고·스케줄). '
             '서술만 <code>tools/build_design_doc.py</code> 안에 있다.</p>')

    html = D.page("AX_source 시스템 기획서", "".join(H))
    return D.render(html, out_html, out_pdf, footer_left="AX_source 시스템 기획서")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--open", action="store_true")
    # 파일명이 날짜다. 옵션이 없으면 오늘로 **새 파일**이 생겨 이미 배포된 판이 옛 값으로 남는다 —
    # 나간 판을 고치는 것이면 그 날짜를 그대로 준다 (`--date 20260909`).
    ap.add_argument("--date", metavar="YYYYMMDD",
                    help="파일명 날짜를 지정해 그 이름 그대로 덮어쓴다 (기본: 오늘)")
    a = ap.parse_args()
    d = datetime.strptime(a.date, "%Y%m%d").date() if a.date else date.today()
    out = os.path.join(C.ROOT, "out")
    os.makedirs(out, exist_ok=True)
    stem = os.path.join(out, f"시스템_기획서_{d:%Y%m%d}")
    pdf = build(stem + ".html", stem + ".pdf")
    print(f"생성 {pdf}")
    if a.open:
        os.startfile(pdf) if hasattr(os, "startfile") else webbrowser.open(pdf)


if __name__ == "__main__":
    main()
