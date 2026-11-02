# -*- coding: utf-8 -*-
"""회차 기획서 — 그 주 기획·선정 근거·T1 원고·T2 원고를 한 문서(PDF)로. (2026-09-09 신설)

  python tools/build_brief.py            # 이번 회차
  python tools/build_brief.py --open

산출: out/<YYYYMMDD>/기획서_<YYYYMMDD>.pdf  (+ 같은 이름의 .html — 판이 깨졌을 때 볼 것)

## 왜 필요한가
기획과 원고가 **네 파일에 흩어져 있다** — `llm/01_기획.json` · `T1_대본.json` ·
`T2_대본.json` · 그리고 렌더된 덱/툰. 게시 전에 사람이 읽어야 하는데, JSON 네 개를
번갈아 여는 방식으로는 **아무도 다 안 읽는다.** 한 장짜리 검토 문서가 그 자리다.

## 무엇이 들어 있나 — 전부 **파생**이다
이 문서는 스스로 판단하지 않는다. 위 네 파일을 읽어 옮길 뿐이라 **원고를 고치면
다시 돌려서 새로 뽑는 것이지, 이 문서를 고치는 게 아니다.** 여기를 고치면 덱·툰과
조용히 갈린다.

⚠️ 3·4주차(사내 전용)에는 만들지 않는다 — 그 회차엔 기획할 유튜브 소재가 없다.
"""
import argparse, io, json, os, sys, webbrowser
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_page as B
import build_t1 as T1
import collect as C
import pdfdoc as D

E = D.esc

# T1 덱에서 회차마다 바뀌는 건 사례 두 장뿐이다. 나머지 넷은 고정 배경이라
# 기획서엔 「무엇이 실려 있는지」만 한 줄로 적는다 (build_t1.build() 순서와 같다).
FIXED_SLIDES = [
    (1, "표지", "날짜·주차·이번 회차 성격", "날짜·주차만 바뀜"),
    (2, "현황 지도", "지금 업무 자동화가 어디까지 왔나 — 관계 그림 + 공개 조사 수치 4개", "고정"),
    (3, "두 사례 요약", "무엇을 모아 왔고 무엇을 만들어 냈나 (썸네일 두 개)", "매주"),
    (6, "4주 로테이션", "네 주차를 놓고 오늘이 어디인지 — 「매주 도는 자리」임을 보인다", "주차만"),
    (7, "AX 확산 전략", "전술 7개 · 플라이휠 · 측정 3개 · DX 4시간 상한", "고정"),
]


def watch_line(deck, ax, vid):
    """세션에서 **보는 시간대**. 링크 위에 적는다 — 발표자가 제일 먼저 찾는 값이다.

    ⚠️ 유튜브 링크만 있으면 **어디부터 트는지 모른 채 영상을 처음부터 연다.**
       구간은 §3 원고 절에도 있지만, 한 쌍 카드에서 바로 보여야 한다(2026-09-09 요청).
    """
    play = ((deck or {}).get(ax) or {}).get("재생") or []
    if not play:
        return ('<div class="watch none">▶ 보는 시간대 <b>미지정</b> — '
                '영상이 처음부터 재생됩니다</div>')
    rows = []
    for c in play:
        a, b = T1.secs(c.get("시작")), T1.secs(c.get("끝"))
        dur = f' <span>({b - a}초)</span>' if (a is not None and b is not None and b > a) else ""
        lab = f' <span>{E(c.get("라벨"))}</span>' if c.get("라벨") else ""
        link = (f'https://www.youtube.com/watch?v={vid}&t={a}s' if a is not None
                else f'https://www.youtube.com/watch?v={vid}')
        rows.append(f'<a href="{link}"><b>{E(c.get("시작"))} ~ {E(c.get("끝"))}</b></a>'
                    f'{dur}{lab}')
    return '<div class="watch">▶ 보는 시간대 &nbsp;' + "<br>".join(rows) + '</div>'


def axis_block(ses, ax, cls, no, chosen, detail, deck=None):
    r = ses["picks"][ax][0]
    w = (chosen or {}).get(ax, {})
    d = (detail or {}).get(r["영상ID"], {})
    return (f'<div class="col {cls}">'
            f'<span class="tag {cls}">{no} {ax}</span>'
            f'<h4>{E(r["제목"])}</h4>'
            f'<div class="src">{E(r["채널"])} · {B.dur(r["_sec"])} · '
            f'조회 {B.human(r["_views"])} · 구독 {B.human(r["_subs"])} · {E(r["업로드"])}</div>'
            + watch_line(deck, ax, r["영상ID"])
            + f'<div class="src"><a href="{E(r["링크"])}">{E(r["링크"])}</a></div>'
            + (f'<p><b>왜 이걸 골랐나</b><br>{E(w["이유"])}</p>' if w.get("이유") else "")
            + (f'<p><b>우리 팀 적용</b><br>{E(w["우리팀"])}</p>' if w.get("우리팀") else "")
            + f'<p class="small dim">원고 근거 — 설명 '
              f'{"전문 %d자" % len(d["설명"]) if d.get("설명") else "300자(잘린 것)"}'
              f' · 챕터 {len(d.get("챕터") or r.get("챕터") or "")}자</p>'
            + '</div>')


def t1_case_table(deck, ax):
    v = deck.get(ax) or {}
    if not v:
        return ('<p class="small" style="color:#B8442E">▶ <b>원고는 승인 뒤에 만들어집니다</b> — '
                '승인.bat 을 누르면 목요일 배치의 <code>build_t1.py</code> 가 '
                '<code>T1_대본.json</code> 을 쓰고, 기획서도 그때 이 자리를 채워 다시 만듭니다. '
                '지금 보실 것은 <b>1~3장(기획·선정 근거)</b> 입니다.</p>')
    rows = "".join(
        f'<tr><td class="n">{i}</td><td><b>{E(s.get("이름"))}</b></td>'
        f'<td>{E(s.get("설명"))}</td>'
        f'<td class="n">{"판단" if str(s.get("묶음", 1)) == "1" else "실행"}</td></tr>'
        for i, s in enumerate(v.get("단계") or [], 1))
    play = v.get("재생") or []
    if play:
        pl = " · ".join(f'<b>{E(x.get("시작"))} ~ {E(x.get("끝"))}</b>'
                        + (f' ({E(x.get("라벨"))})' if x.get("라벨") else "") for x in play)
        play_html = f'<p class="small">▶ 세션에서 틀 구간 — {pl}</p>'
    else:
        play_html = ('<p class="small" style="color:#B8442E">▶ <b>재생 구간 없음</b> — '
                     '영상이 처음부터 재생됩니다. 챕터 근거가 없어 LLM 이 비워 뒀습니다. '
                     '<code>T1_대본.json</code> 의 <code>재생</code> 에 직접 적으세요.</p>')
    return (f'<h4>{E(v.get("제목"))}</h4>'
            f'<p class="dim">{E(v.get("무엇을"))}</p>'
            + play_html +
            f'<p class="small dim">도형 <code>{E(v.get("도형") or "세로")}</code>'
            + (f' · 중심 <code>{E(v["중심"])}</code>' if v.get("중심") else "")
            + f' · 단계 {len(v.get("단계") or [])}개</p>'
            + '<table><thead><tr><th>#</th><th>단계</th><th>설명</th><th>구간</th></tr></thead>'
            + f'<tbody>{rows}</tbody></table>')


def t2_table(sc):
    """장·컷을 한 표로. **컷 페이지는 컷마다 한 줄**이라 장 칸을 세로로 묶는다."""
    rows = ""
    for i, p in enumerate(sc.get("장") or [], 1):
        cuts = p.get("컷") or []
        if p.get("종류") == "컷" and cuts:
            for k, c in enumerate(cuts, 1):
                head = (f'<td class="n" rowspan="{len(cuts)}">{i}</td>'
                        f'<td rowspan="{len(cuts)}"><b>{E(p.get("막") or "해결")}</b><br>'
                        f'<span class="small dim">컷 {len(cuts)} · {E(p.get("배치"))}</span></td>'
                        f'<td rowspan="{len(cuts)}">{E(p.get("배지"))}</td>') if k == 1 else ""
                sfx = f' <b>{E(c.get("효과음"))}</b>' if c.get("효과음") else ""
                rows += (f'<tr>{head}<td class="n">{k}</td>'
                         f'<td>{E(c.get("나레이션", "")).replace(chr(10), "<br>")}</td>'
                         f'<td><b>{E(c.get("말", "")).replace(chr(10), "<br>")}</b>{sfx}</td>'
                         f'<td class="small">{E(c.get("소품"))}<br>'
                         f'{E(c.get("구도"))}·{E(c.get("표정"))}</td></tr>')
        else:
            # 필드 이름은 `할아버지` 지만 화면에는 **대본에 적힌 이름**을 쓴다 —
            # 「부장님」으로 나가는데 표만 「할아버지」면 읽는 사람이 둘로 센다
            who = (f'<br><b>+{E(p.get("할아버지이름") or "부장님")}</b>'
                   if p.get("할아버지") else "")
            rows += (f'<tr><td class="n">{i}</td>'
                     f'<td><b>{E(p.get("막") or p.get("종류"))}</b></td>'
                     f'<td>{E(p.get("근거") or "")}</td>'
                     f'<td class="n">{("T1-" + str(p["단계"])) if p.get("단계") else "—"}</td>'
                     f'<td><b>{E(p.get("제목", "")).replace(chr(10), "<br>")}</b></td>'
                     f'<td>{E(p.get("말", "")).replace(chr(10), "<br>")}</td>'
                     f'<td class="small">{E(p.get("소품") or "-")}<br>'
                     f'{E(p.get("구도"))}·{E(p.get("표정"))}{who}</td></tr>')
    return ('<table><thead><tr><th>장</th><th>막</th><th>근거</th><th>T1 단계</th>'
            '<th>제목(나레이션)</th><th>말풍선</th><th>그림</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>')


TYPE_FILE = "회차유형.json"


def round_type(out_d):
    """`out/<회차>/회차유형.json` 이 있으면 그 회차는 **사례 회차가 아니다**.

    2026-09-16 신설(사용자 지시) — 「체험」처럼 유튜브 사례 대신 **직접 해보는 회차**를
    그 회차 폴더에만 표시한다. 4주 로테이션 정의(`build_page.SLOTS`)는 건드리지 않는다 —
    상설 포맷으로 올리려면 로테이션 표(AX확산 계획(docs/AX확산) SSOT)부터 고쳐야 하기 때문이다.
    """
    p = os.path.join(out_d, TYPE_FILE)
    if not os.path.exists(p):
        return None
    return json.load(io.open(p, encoding="utf-8"))


def build_type(meta, ses, d, out_html, out_pdf, toon=None):
    """사례 없는 회차(체험 등)의 기획서. 사례 블록은 없지만 **툰 원고는 싣는다**.

    ⚠️ 2026-09-18: 원고 절이 없어 **공개 기획서에 원고가 빠져 있었다**(사용자 지적).
       체험 회차도 툰은 같은 채널에 올라가므로 승인하는 사람이 읽을 자리가 있어야 한다.
       대본이 없는 회차도 있으니 **있을 때만** 그린다(없으면 절을 아예 만들지 않는다).
    """
    cat = meta.get("카테고리") or "체험"
    H = []
    H.append(
        '<section class="cover">'
        '<div class="brand">AX 확산 · T1 부서장회의</div>'
        f'<h1>{ses["label"]}<br>세션 기획서</h1>'
        f'<div class="lead">{E(meta.get("제목") or cat + " 회차")}</div>'
        f'<div class="meta">'
        f'카테고리 <b>{E(cat)}</b> · {d:%Y년 %m월 %d일} 생성<br>'
        f'{E(meta.get("한줄") or "유튜브 사례 대신 직접 해보는 회차입니다.")}'
        '</div></section>')

    ap = B.approval()
    if ap:
        H.append('<div class="box plan"><h4>✔ 승인됨</h4>'
                 f'<p>{E(ap.get("승인시각"))} · {E(ap.get("승인자"))}</p></div>')
    else:
        H.append('<div class="box warn"><h4>아직 승인되지 않았습니다</h4>'
                 '<p>읽고 괜찮으면 회차 폴더의 <code>승인.bat</code> 을 더블클릭하세요.</p></div>')

    H.append(f'<h2>1. 이 회차를 {E(cat)}으로 하는 이유</h2>')
    H.append(f'<div class="box plan"><div class="quote">{E(meta.get("왜") or "")}</div></div>')

    if meta.get("진행"):
        H.append('<h2>2. 진행 순서</h2>')
        H.append('<table><thead><tr><th>#</th><th>무엇을</th><th>시간</th></tr></thead><tbody>'
                 + "".join(f'<tr><td class="n">{i}</td><td>{E(x.get("무엇"))}</td>'
                           f'<td class="n">{E(x.get("시간") or "")}</td></tr>'
                           for i, x in enumerate(meta["진행"], 1))
                 + '</tbody></table>')

    if meta.get("자료"):
        H.append('<h2>3. 쓰는 자료</h2>')
        H.append('<table><thead><tr><th>자료</th><th>자리</th><th>무엇</th></tr></thead><tbody>'
                 + "".join(f'<tr><td><b>{E(x.get("이름"))}</b></td>'
                           f'<td><code>{E(x.get("경로"))}</code></td>'
                           f'<td>{E(x.get("무엇") or "")}</td></tr>'
                           for x in meta["자료"])
                 + '</tbody></table>')

    if meta.get("준비물"):
        H.append('<h2>4. 준비물</h2><ul>'
                 + "".join(f'<li>{E(x)}</li>' for x in meta["준비물"]) + '</ul>')

    if meta.get("주의"):
        H.append('<h2>5. 주의</h2>'
                 + "".join(f'<div class="box warn"><p>{E(x)}</p></div>' for x in meta["주의"]))

    # ── 6. T2 원고 ──────────────────────────────────────────
    # 표는 사례 회차와 **같은 렌더러**(t2_table)를 쓴다 — 두 벌로 나누면 갈린다.
    # 「T1 단계」 칸은 체험 회차에 T1 덱이 없어 전부 「—」로 뜨는 것이 정상이다.
    # 편 목록은 대본이 정한다 — 체험 회차는 「체험」 한 편(2026-09-18).
    # ⚠️ `_읽어주세요` 같은 **문자열 키가 섞여 있다** — 장이 있는 dict 만 고른다.
    axes = [(k, v) for k, v in (toon or {}).items()
            if isinstance(v, dict) and (v.get("장") or [])]
    if any(sc.get("장") for _, sc in axes):
        H.append('<h2 class="pagebreak">6. T2 정보채널 인스타툰 원고</h2>')
        H.append('<p class="dim">이 회차는 유튜브 사례가 없어 <b>회차 자체를 소재로</b> 쓴다 — '
                 '설치·규칙 설정을 직접 해 본 이야기다. 전개는 사례 회차와 같다 '
                 '(<b>표지 1 + 이야기 10 + 댓글 1 = 12장</b> · 문제 → 작업 → 결과 세 막 · '
                 '6·8장에 상사 곰돌이). <b>축 키 「분석·생성」은 도구가 요구하는 파일 규약</b>이고, '
                 '실제 두 편의 구분은 <b>머리말</b>이다.</p>')
        H.append('<div class="box warn"><h4>이 회차에도 반드시 지킬 것 두 가지</h4>'
                 '<p><b>① 채용·구인·이직·인사 소재는 원고에 넣지 않는다</b> '
                 '(기준 정본 <code>config/LLM_컨셉.md</code> §2b).</p>'
                 '<p><b>② 마지막 장은 댓글 유도로 끝낸다</b> — 말풍선 한 줄 '
                 '「자세한 내용이 궁금하신가요? 댓글에 메일주소를 작성해 주세요」. '
                 '자료를 보내 준다는 건 채널의 약속이라 회차마다 말이 흔들리면 안 된다 '
                 '(정본 <code>config/인스타툰_마스터.md</code>).</p></div>')
        for ax, sc in axes:
            if not sc.get("장"):
                continue
            H.append(f'<h3>{E(ax)} 편 — {E(sc.get("제목") or "")}</h3>')
            H.append(f'<p class="small dim">{E(sc.get("머리말") or "")}'
                     + (f' · 게시판훅 「{E(sc.get("게시판훅"))}」' if sc.get("게시판훅") else '')
                     + '</p>')
            H.append(t2_table(sc))

    H.append('<p class="small dim">이 회차는 유튜브 사례를 쓰지 않는다 — '
             f'회차 폴더의 <code>{TYPE_FILE}</code> 이 그 표시다. '
             '사례 회차로 되돌리려면 그 파일을 지우고 기획서를 다시 만든다.</p>')

    html = D.page(f"{ses['label']} 세션 기획서 ({cat})", "".join(H))
    return D.render(html, out_html, out_pdf,
                    footer_left=f"AX 확산 · {ses['label']} {cat} 회차")


def build(ses, d, deck, toon, out_html, out_pdf):
    ch = ses.get("chosen") or {}
    detail = ses.get("detail") or {}
    ana, gen = ses["picks"]["분석"][0], ses["picks"]["생성"][0]
    H = []

    # ── 표지 ────────────────────────────────────────────────
    H.append(
        '<section class="cover">'
        f'<div class="brand">AX 확산 · T1 부서장회의 &nbsp;|&nbsp; T2 정보채널</div>'
        f'<h1>{ses["label"]}<br>세션 기획서</h1>'
        f'<div class="lead">{E(ch.get("기획") or "기획 없음 — 기계 초안으로 만들어진 회차입니다.")}</div>'
        f'<div class="meta">'
        f'로테이션 {ses["slot"]}주차 「{E(ses["slot_name"])}」 · {d:%Y년 %m월 %d일} 생성<br>'
        f'분석 — {E(ana["제목"][:44])}<br>'
        f'생성 — {E(gen["제목"][:44])}<br>'
        f'기획·원고 {"LLM 작성" if ch else "기계 초안(챕터 자르기)"} · '
        f'후보 {len(ses["rows"])}건에서 선정'
        f'</div></section>')

    # ⚠️ 「두 툰이 하려는 말」 절(§0)은 하루 만에 걷어냈다(2026-09-10).
    #    그 말은 **문서가 아니라 툰이 해야 한다** — 툰 1장이 표지로 묻고,
    #    마지막 장이 답한다. 기획서는 §4 원고 표 첫 줄에서 그걸 그대로 보여 준다.

    # ── 0. 승인 ─────────────────────────────────────────────
    # 이 문서가 존재하는 이유가 여기다 — 읽고 「만들어라」를 눌러 주는 자리.
    ap = B.approval()
    if ap:
        H.append('<div class="box plan"><h4>✔ 승인됨</h4>'
                 f'<p>{E(ap.get("승인시각"))} · {E(ap.get("승인자"))}'
                 + (f' · {E(ap.get("메모"))}' if ap.get("메모") else "")
                 + '<br>목요일 09:40 배치가 T1 덱과 T2 툰을 만듭니다.</p></div>')
    else:
        H.append('<div class="box warn"><h4>아직 승인되지 않았습니다 — 지금은 여기까지입니다</h4>'
                 '<p>이 기획서는 <b>수요일 09:40</b> 에 자동으로 만들어집니다. '
                 '읽고 괜찮으면 회차 폴더의 <code>승인.bat</code> 을 더블클릭하세요. '
                 '<b>승인이 없으면 목요일 배치가 T1·T2 를 만들지 않습니다.</b></p>'
                 '<p class="small dim">고칠 것이 있으면 먼저 고치고 승인하세요 — '
                 '기획 방향은 <code>config/LLM_컨셉.md</code>, 원고는 두 대본 파일입니다. '
                 '승인을 물리려면 <code>python tools/approve.py --취소</code>.</p></div>')

    # ── 1. 기획 ─────────────────────────────────────────────
    H.append('<h2>1. 이번 회차 기획</h2>')
    if ch.get("기획"):
        H.append(f'<div class="box plan"><div class="quote">{E(ch["기획"])}</div></div>')
        H.append(f'<p><b>두 사례가 서로 보완하는 것</b><br>{E(ch.get("한쌍이유"))}</p>')
    else:
        H.append('<div class="box warn"><h4>기획 없이 만들어진 회차입니다</h4>'
                 '<p>LLM 이 돌지 않아 <code>fit()</code> 점수 1위 두 건으로 채워졌습니다. '
                 '제목·단계가 유튜브 원문이라 <b>발표 전 전면 수정이 필요합니다.</b></p></div>')

    # ── 2. 한 쌍 ────────────────────────────────────────────
    H.append('<h2>2. 이번 주 한 쌍</h2>')
    H.append('<div class="duo">'
             + axis_block(ses, "분석", "ana", "①", ch, detail, deck)
             + axis_block(ses, "생성", "gen", "②", ch, detail, deck) + '</div>')
    if ch.get("제친후보"):
        H.append('<h3>마지막까지 놓고 고민했지만 제친 것</h3>'
                 '<p class="small dim">무엇을 버렸는지가 기획이 실제로 있었다는 증거다.</p>'
                 '<table><thead><tr><th>영상</th><th>왜 안 골랐나</th></tr></thead><tbody>'
                 + "".join(f'<tr><td>{E(x["제목"])}</td><td>{E(x["왜안골랐나"])}</td></tr>'
                           for x in ch["제친후보"])
                 + '</tbody></table>')

    # ── 3. T1 원고 ──────────────────────────────────────────
    H.append('<h2 class="pagebreak">3. T1 부서장회의 원고</h2>')
    H.append('<p class="dim">13분 사례 공유 + 10분 질의응답. 슬라이드 <b>일곱 장</b> 중 '
             '<b>바뀌는 건 사례 두 장</b>이고 나머지는 고정 배경이다.</p>')
    H.append('<table><thead><tr><th>장</th><th>무엇</th><th>내용</th><th>회차마다</th></tr></thead><tbody>'
             + "".join(f'<tr><td class="n">{n}</td><td><b>{E(t)}</b></td>'
                       f'<td>{E(c)}</td><td class="n">{E(k)}</td></tr>'
                       for n, t, c, k in FIXED_SLIDES[:3])
             + '<tr><td class="n">4</td><td><b>① 분석 사례</b></td>'
               '<td>썸네일 + 진행 과정 — 아래 원고</td><td class="n">매주</td></tr>'
               '<tr><td class="n">5</td><td><b>② 생성 사례</b></td>'
               '<td>썸네일 + 진행 과정 — 아래 원고</td><td class="n">매주</td></tr>'
             + "".join(f'<tr><td class="n">{n}</td><td><b>{E(t)}</b></td>'
                       f'<td>{E(c)}</td><td class="n">{E(k)}</td></tr>'
                       for n, t, c, k in FIXED_SLIDES[3:])
             + '</tbody></table>')
    H.append('<h3>4장 — ① 분석 사례</h3>' + t1_case_table(deck, "분석"))
    H.append('<h3>5장 — ② 생성 사례</h3>' + t1_case_table(deck, "생성"))

    # ── 4. T2 원고 ──────────────────────────────────────────
    # ⚠️ **툰은 2026-09-10 부터 GPT 가 만든다.** 대본이 없는 회차가 생기므로
    #    이 절은 **있을 때만 그린다** — 없는데 그대로 밀고 들어가면 빈 표가 실린다.
    if not toon:
        # ⚠️ 2026-09-18 사용자 지시로 문구를 바꿨다 — 전에는 「새 프롬프트를 받기 전까지 비어
        #    있습니다」였다. 그 말이 **원고를 미뤄도 되는 회차가 있다**는 신호로 읽혔다.
        #    원고는 회차마다 필수고, 없으면 그것이 **빠진 일**이라고 말해야 한다.
        H.append('<h2 class="pagebreak">4. T2 정보채널 인스타툰 원고</h2>'
                 '<div class="box warn"><h4>🔴 이번 회차 원고가 없습니다 — 반드시 만들어야 합니다</h4>'
                 '<p><b>원고는 회차마다 빠뜨릴 수 없습니다</b>(2026-09-18 지시). '
                 '배치가 만들지 않을 뿐이므로 <b>대화에서 써서 '
                 '<code>out/&lt;회차&gt;/T2_대본.json</code></b> 에 남깁니다 — '
                 '표지 1 + 이야기 10 + 댓글 1 = <b>12장</b>, 축은 <b>분석·생성 둘 다</b>.<br>'
                 '원고가 없으면 <b>게시판 글도 못 만들고</b>'
                 '(<code>build_board_post.py</code> 가 이 대본에서 냅니다) 그 주 사내 채널이 빕니다.<br>'
                 '<span class="small dim">그림은 GPT + 사람이 굽습니다 — '
                 '옛 렌더러는 <code>archive/20260910_t2/</code>. 규격 정본 '
                 '<code>config/인스타툰_마스터.md</code>.</span></p></div>')
    else:
        H.append('<h2 class="pagebreak">4. T2 정보채널 인스타툰 원고</h2>')
        H.append('<p class="dim">같은 한 쌍을 유삐 1인칭 캐러셀로 다시 푼다. 축마다 한 벌이고, '
                 '전개는 <b>① 문제상황 제시 → ② 어떤 작업을 하는지 → ③ 결과물로 무엇이 나오는지</b> '
                 '세 막이다. <b>표지 1 + 이야기 10 + 댓글 1 = 12장 한 벌</b>. '
                 '<b>1장은 표지</b>다 — 큰 글씨로 <b>묻고</b>(「이 일, 아직도 손으로 하세요?」), 아래 한 줄로 <b>무슨 이야기인지</b>를 말한다. 마지막 장이 그 질문에 답한다. '
                 '6·8장에 <b>할아버지 곰돌이(상사)</b>가 나와 의심하고 인정한다. '
                 '본문 다섯 장(4·5·7·9·10)은 <b>T1 덱의 다섯 단계</b>를 하나씩 받는다 — 아래 표의 '
                 '<b>「T1 단계」 칸</b>에서 대조한다.</p>')
        # ── 툰 원고 규격 (2026-09-10) ────────────────────────────
        # ⚠️ 이 둘은 **회차마다 같다.** 한때 파이프라인이 강제하게 만들었다가 걷어냈다 —
        #    프롬프트·검문·배치 게이트로 박아 두면 **왜 그런지가 코드 안에 숨는다.**
        #    승인하는 사람이 매주 읽는 자리는 여기다. 규격은 문서가 말하고, 사람이 대본에 넣는다.
        H.append('<div class="box warn"><h4>이 회차에도 반드시 지킬 것 두 가지</h4>'
                 '<p><b>① 채용·구인·이직·인사 소재는 원고에 넣지 않는다.</b> 영상에 나왔더라도 '
                 '<b>그 대목만 뺀다</b> — 소재를 통째로 버리는 게 아니다. 같은 영상의 '
                 '<b>입찰공고·모집요강·리뷰·뉴스 수집</b>으로 바꿔 든다. '
                 '사내 게시물에서 이걸 자동화한다고 말하면 <b>인사 신호로 읽힌다</b> — '
                 '「우리 회사가 사람을 뽑나·내보내나」. 급여·평가·징계 같은 인사 데이터, '
                 '특정 직원·팀을 지목하는 사례도 같다. (기준 정본 '
                 '<code>config/LLM_컨셉.md</code> §2b)</p>'
                 '<p><b>② 마지막 장은 댓글 유도로 끝낸다.</b> 문구는 회차마다 바꾸지 않는다 — '
                 '자료를 보내 준다는 건 채널의 약속이라 말이 흔들리면 안 된다.</p>'
                 '<table><thead><tr><th>자리</th><th>문구</th></tr></thead><tbody>'
                 '<tr><td>말풍선</td><td><b>자세한 내용이 궁금하신가요?<br>'
                 '댓글에 메일주소를 작성해 주세요</b></td></tr>'
                 '</tbody></table>'
                 '<p class="small dim">대본에서 마지막 장을 <code>"종류": "댓글"</code> 로 두고 '
                 '<code>말</code> 에 위 문구를 한 줄로 적는다. '
                 '<b>코드가 붙여 주지 않는다</b> — <code>--reset</code> 으로 초안을 다시 뽑았으면 '
                 '이 장이 빠져 있으니 다시 넣는다.</p></div>')
        H.append('<div class="box"><h4>③ 결과물 막이 이 툰의 목적이다</h4>'
                 '<p>「무엇이 손에 남는가」를 <b>물건 이름</b>으로 짚습니다 — 「엑셀 표 한 장」·'
                 '「매주 아침에 오는 목록」처럼. <b>「시간이 줄어요」 같은 효과 문구는 산출물이 아닙니다.</b> '
                 '①② 만 있으면 고생담으로 끝납니다.</p>'
                 '<p class="small dim">산출물은 <b>그 영상에 실제로 나온 것만</b> 씁니다. '
                 '근거를 못 대면 그 장은 ② 작업 막으로 내려가고 아래에 「③ 결과물 막 없음」으로 뜹니다.</p></div>')
        for ax in C.AXES:
            sc = (toon or {}).get(ax) or {}
            # ⚠️ 예전엔 `종류 == "컷"` 인 장만 셌다. 컷을 폐기하자 **어떤 회차에서도
            #    「결과물 막 없음」이 떴다** — 표에는 결과 막이 버젓이 있는데(2026-09-09 실측).
            #    막은 모든 장에 붙으므로 종류로 거르지 않는다.
            acts = [p.get("막") for p in (sc.get("장") or [])]
            ground = next((p.get("근거") for p in (sc.get("장") or [])
                           if p.get("막") == "결과" and p.get("근거")), "")
            if "결과" in acts:
                badge = f'<span style="color:#00794A">③ 결과물 막 있음 — 근거: {E(ground)}</span>'
            else:
                badge = ('<span style="color:#B8442E">⚠️ ③ 결과물 막 없음 — '
                         '영상에 산출물 근거가 없다는 뜻. <b>이대로 두면 고생담으로 끝난다</b></span>')
            H.append(f'<h3>{ax}축 — 「{E(sc.get("제목"))}」 · {len(sc.get("장") or [])}장</h3>'
                     f'<p class="small">{badge}</p>'
                     f'<p class="small dim">머리말 {E(sc.get("머리말"))} · '
                     f'꼬리말 {E(sc.get("꼬리말"))}</p>' + t2_table(sc))

    # ⚠️ **GPT 비교 절(4b)은 2026-09-10 에 걷어냈다.** 이 문서는 관리자가
    #    읽고 **승인을 누르는 자리**다 — 게시본이 아닌 모델 비교판이 같이 실리면
    #    어느 쪽을 승인하는 건지 헷갈린다. 비교는 `tools/gpt.py` 가 그대로 하고,
    #    산출물은 `out/<회차>/test/` 에만 남는다.

    # ── 5. 사람이 고치는 자리 ────────────────────────────────
    H.append('<h2>5. 게시 전 체크리스트</h2>')
    H.append('<div class="box warn"><h4>이 문서는 초안이다</h4>'
             '<p>LLM 은 <b>영상 제목·챕터·설명만</b> 보고 썼다 — 우리 팀 실제 사정은 모른다. '
             '아래를 확인하고 <b>대본 파일</b>을 고친 뒤 다시 돌리면 고친 내용이 유지된다'
             '(<code>--reset</code> 해야 초안으로 돌아간다).</p></div>')
    H.append('<ul class="chk">'
             '<li><b>단계가 영상에 실제로 있는가</b> — 그럴듯하지만 영상이 안 한 일이면 '
             '발표자가 그 자리에서 막힌다</li>'
             '<li><b>우리 데이터가 실명으로 새지 않았는가</b> — 센터명·매출액·학생수는 '
             '원고에 들어가면 안 된다 (「센터별 실적표」처럼 종류만)</li>'
             '<li><b>부서장이 아는 말인가</b> — API·크롤링·파이프라인 같은 말이 남아 있지 않은가</li>'
             '<li><b>13분에 들어가는가</b> — 단계가 5개를 넘으면 질의응답 10분이 깎인다</li>'
             '<li><b>T2 말풍선이 두 줄을 넘지 않는가</b> — 넘치면 그림에서 조용히 잘린다</li>'
             '<li><b>T1 재생 구간이 맞는가</b> — 위 3절에 실린 구간을 실제로 틀어 본다. '
             'LLM 이 챕터만 보고 고른 것이라 <b>엉뚱한 대목일 수 있다</b></li>'
             '<li><b>채용·구인·이직·인사 대목이 없는가</b> — 영상에 나왔어도 그 대목만 빼고 '
             '입찰공고·모집요강·리뷰·뉴스로 바꿔 든다. 사내에서는 <b>인사 신호로 읽힌다</b> '
             '(4절 규격 참조)</li>'
             '<li><b>툰 마지막이 댓글 유도 장인가</b> — 「자세한 내용이 궁금하신가요? '
             '댓글에 메일주소를 작성해 주세요」(말풍선 한 줄). <b>코드가 안 붙인다</b> — '
             '초안을 다시 뽑았으면 빠져 있다</li>'
             '<li><b>툰 다섯 장이 T1 단계와 맞는가</b> — 4절 표의 「T1 단계」 칸. '
             '번호만 맞고 문장이 다른 단계인 경우가 실제로 있었다</li>'
             '</ul>')
    H.append('<div class="box"><h4>다 확인했으면</h4>'
             '<p>회차 폴더의 <code>승인.bat</code> 을 더블클릭하면 승인됩니다. '
             '목요일 09:40 배치가 그때 T1·T2 를 만듭니다.</p></div>')
    H.append('<h3>고치는 파일</h3>'
             f'<table><thead><tr><th>무엇을</th><th>파일</th></tr></thead><tbody>'
             '<tr><td>T1 제목·무엇을·단계·도형·재생 구간</td><td><code>T1_대본.json</code></td></tr>'
             '<tr><td>T2 대사·설명·소품·구도·표정</td><td><code>T2_대본.json</code></td></tr>'
             '<tr><td>기획 방향 자체 (회사 맥락·선정 기준)</td>'
             '<td><code>config/LLM_컨셉.md</code> → <code>--llm-refresh</code></td></tr>'
             '</tbody></table>')
    H.append(f'<p class="small dim">이 기획서는 위 파일들에서 <b>파생</b>된다 — '
             f'여기를 고치면 덱·툰과 갈린다. 원고를 고쳤으면 '
             f'<code>python tools/build_brief.py</code> 를 다시 돌린다.<br>'
             f'프롬프트와 받은 원문은 <code>out/{d:%Y%m%d}/llm/</code> 에 남아 있다.</p>')

    html = D.page(f"{ses['label']} 세션 기획서", "".join(H))
    return D.render(html, out_html, out_pdf,
                    footer_left=f"AX 확산 · {ses['label']} 세션 기획서")


APPROVE_BAT = """@echo off
REM ============================================================
REM  Approve this round.  After this, Thursday's batch builds the
REM  T1 deck and the T2 toon.  Without it, nothing is built.
REM  ASCII ONLY - see README section 10 (cmd drifts on multi-byte lines).
REM ============================================================
setlocal
cd /d "%~dp0"
set "OLDCP="
for /f "tokens=2 delims=:" %%c in ('chcp') do for /f "tokens=1" %%d in ("%%c") do set "OLDCP=%%d"
if not "%OLDCP%"=="65001" chcp 65001 > nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
python "%~dp0..\\..\\tools\\approve.py" %*
echo.
pause
if defined OLDCP if not "%OLDCP%"=="65001" chcp %OLDCP% > nul
endlocal
"""


def write_approve_bat(out_d):
    """회차 폴더에 승인 버튼을 둔다 — 관리자가 폴더에서 바로 누를 수 있게.

    ⚠️ ASCII 전용 (§9-10). 한글은 approve.py 가 찍는다.
    """
    p = os.path.join(out_d, "승인.bat")
    io.open(p, "w", encoding="ascii", newline="\r\n").write(APPROVE_BAT)
    return p


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", type=int, default=None)
    ap.add_argument("--week", type=int, default=None)
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()
    import llm as L
    d = date.today()

    # ⚠️ **회차유형 검사가 session() 보다 먼저다.** 체험 회차는 사례를 안 쓰므로
    #    LLM 기획을 부를 이유가 없다 — 먼저 안 보면 호출이 한 번 나가고(돈·시간)
    #    체험 회차 폴더에 **쓰지도 않을 `llm/01_기획.json` 이 생긴다**(2026-09-16 실측:
    #    그 파일 때문에 페이지의 그 회차 상자가 사례 기획 문장을 띄웠다).
    meta = round_type(B.out_dir(d, False))
    L.enable((not a.no_llm) and not meta, False)

    ses = B.session(a.month, a.week)
    if not meta and not ses["from_youtube"]:
        print(f"  {ses['slot']}주차 「{ses['slot_name']}」 는 사내 전용 회차 — 기획서를 만들지 않습니다.")
        return
    if not meta and not all(ses["picks"].values()):
        print("  [건너뜀] 축 후보가 비어 기획서를 만들 수 없습니다.")
        return

    out_d = B.out_dir(d)

    # 사례 없는 회차(체험 등)는 여기서 갈라진다 — 축 후보·대본을 아예 안 본다.
    if meta:
        write_approve_bat(out_d)
        stem = os.path.join(out_d, f"기획서_{B.round_day(d):%Y%m%d}")
        # 툰 대본은 체험 회차에도 있을 수 있다 — 있으면 §6 원고 절에 싣는다(2026-09-18).
        tp0 = os.path.join(out_d, "T2_대본.json")
        toon0 = json.load(io.open(tp0, encoding="utf-8")) if os.path.exists(tp0) else {}
        pdf = build_type(meta, ses, d, stem + ".html", stem + ".pdf", toon0)
        print(f"생성 {pdf}")
        print(f"  {ses['label']} · 카테고리 {meta.get('카테고리')} "
              f"· 자료 {len(meta.get('자료') or [])}건")
        if a.open:
            os.startfile(pdf) if hasattr(os, "startfile") else webbrowser.open(pdf)
        return

    dp = os.path.join(out_d, T1.SCRIPT_NAME)
    # ⚠️ **T1 대본이 없어도 기획서는 나온다**(2026-09-16). 대본은 승인 뒤 목요일
    #    `build_t1.py` 가 만든다 — 여기서 막으면 **관리자가 승인 판단에 쓸 기획서가
    #    수요일에 아예 없다**(닭과 달걀). 09-16 회차가 실제로 그래서 빈손이었다.
    #    있으면 원고까지 싣고, 없으면 그 두 장만 「승인 뒤 채워진다」로 둔다.
    deck = json.load(io.open(dp, encoding="utf-8")) if os.path.exists(dp) else {}
    if not deck:
        print("  [알림] T1 대본이 아직 없습니다 — 기획·선정까지만 싣습니다(4·5장은 승인 뒤).")
    # ⚠️ **T2 대본은 없어도 기획서는 나온다**(2026-09-10). 여기서 막으면 **수요일 배치가
    #    기획서를 통째로 못 만든다** — 대본은 승인 뒤에 쓰기 때문이다(닭과 달걀).
    #    ⚠️ **그러나 「없어도 된다」는 뜻이 아니다**(2026-09-18 지시) — 원고는 회차마다 필수고,
    #    없으면 §4 가 **빈 절이 아니라 경고**로 나간다. 그것이 지금 유일한 그물이다.
    tp = os.path.join(out_d, "T2_대본.json")
    toon = json.load(io.open(tp, encoding="utf-8")) if os.path.exists(tp) else {}

    write_approve_bat(out_d)
    stem = os.path.join(out_d, f"기획서_{B.round_day(d):%Y%m%d}")
    pdf = build(ses, d, deck, toon, stem + ".html", stem + ".pdf")
    print(f"생성 {pdf}")
    print(f"  {ses['label']} · T1 단계 "
          + ("대본 없음(승인 뒤) · " if not deck else
             f"{len(deck.get('분석', {}).get('단계') or [])}+{len(deck.get('생성', {}).get('단계') or [])}개 · ")
          + (f"T2 {len((toon.get('분석') or {}).get('장') or [])}+"
             f"{len((toon.get('생성') or {}).get('장') or [])}장" if toon else "T2 대본 없음"))
    if a.open:
        os.startfile(pdf) if hasattr(os, "startfile") else webbrowser.open(pdf)


if __name__ == "__main__":
    main()
