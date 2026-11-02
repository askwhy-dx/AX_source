# -*- coding: utf-8 -*-
"""T1 발표 멘트 — 덱 1~6쪽을 발표자가 읽을 말로 옮긴다 (2026-09-15 신설).

  python tools/build_script_t1.py                    # 이번 회차
  python tools/build_script_t1.py --round 20260909   # 지난 회차
  python tools/build_script_t1.py --reset            # 사람이 고친 T1_멘트.json 을 버리고 다시 쓴다
  python tools/build_script_t1.py --open

산출: out/<회차>/T1_발표멘트_<회차>.html   (발표자용 · 공개 발행 대상 아님)
      out/<회차>/T1_멘트.json               (생각열기 문장 — 사람이 고치는 자리)

무엇이 어디서 오나
------------------
- **사례 장(3~5쪽)** 은 `T1_대본.json` 을 그대로 읽는다 — 제목·무엇을·단계·재생 구간.
  덱과 같은 원천이라 덱과 말이 어긋나지 않는다.
- **생각열기(표지 도입 · 사례 앞 한 줄 · 마무리 장면)** 만 LLM 이 쓴다. 회차마다 사례가
  바뀌므로 「오늘 아침 팀원 모니터」 장면도 그 사례에 맞아야 한다.
  LLM 이 못 돌면 **축 정의(모아 온다 / 만들어 낸다)에 맞춘 기본 문장**으로 떨어진다.
- **2쪽 현황 · 6쪽 로테이션** 은 이 파일의 고정 멘트다.

⚠️ **발표는 6쪽까지다**(2026-09-15 사용자 결정). 7쪽 전략표는 멘트에 안 넣는다.
   그래서 7쪽에만 있던 **T6 클리닉 안내를 마무리 멘트가 말로 이어받는다.**
⚠️ **`T1_멘트.json` 은 영상ID 쌍으로 문다.** 기획을 다시 돌려 쌍이 바뀌었는데 옛 멘트를
   재사용하면 **다른 사례의 장면을 말하게 된다** — 에러는 안 난다(T2 원고 캐시 사고와 같은 모양).
⚠️ **2쪽 멘트는 `build_t1.NET_STATS` 수치에 맞춰 쓴 문장이다.** 수치가 바뀌면 고정 멘트를
   버리고 화면 문구를 그대로 읽는 멘트로 떨어지며 확인 항목에 경고를 띄운다.
"""
import argparse, html, io, json, os, re, sys, webbrowser
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_page as B
import build_t1 as T
import collect as C
import llm as L

SCRIPT_NAME = "T1_멘트.json"
TAG = "05_발표멘트"
E = html.escape

# 쪽, 제목, 초 — 합이 13분. 7쪽은 발표하지 않는다.
PLAN = [(1, "표지 + 생각열기 도입", 90), (2, "업무 자동화 현황", 90),
        (3, "이번 주 두 사례", 60), (4, "① 분석 사례", 210),
        (5, "② 생성 사례", 210), (6, "매주 도는 방식 + 마무리", 120)]
CLIP_SEC = 120          # 사례 영상은 2분 안팎에서 끊는다 (영상 전후 멘트 90초)

STATS_SAID = ["88%", "62%", "25%", "53 : 24"]   # 아래 STATS_TALK 가 전제한 수치
STATS_TALK = [
    "조직 열 곳 중 아홉 곳, <b>88%</b>는 이미 AI 를 한 군데 이상 씁니다. 그런데 전사로 넓힌 곳은 3분의 1 정도입니다.",
    "AI 에이전트를 시험해 보는 곳은 <b>62%</b>인데, 실제로 한 업무라도 정착시킨 곳은 <b>23%</b>에 그칩니다.",
    "그러다 보니 근무시간의 <b>25%</b>는 여전히 손으로 하는 반복 작업입니다.",
    "국내 도입률도 서비스업 53%, 제조업 24%로 차이가 큽니다. 다만 업종이 아니라 <b>어떤 업무를 자동화했느냐</b>가 차이를 만듭니다.",
]

# LLM 이 못 돌았을 때 — 축 정의에만 기대는 문장 (사례 고유 내용은 대본에서 온다)
FALLBACK = {
    "도입": {
        "장면": ["누군가는 사이트 몇 군데를 돌면서 복사해서 엑셀에 붙여넣고 있습니다.",
                 "누군가는 팀원들한테 받은 진행상황을 한 장으로 합치고 있고요."],
        "질문": "그 일을 하는 동안 사람이 실제로 판단한 순간은 몇 번이었을까요?",
        "바꿔끼우기": ["월요일 아침 9시에 출근하면 그 표가 이미 메일에 와 있습니다.",
                       "합쳐야 할 기록은 벌써 제자리에 들어가 있고요."],
        "잇기질문": "우리 팀에서 이 표는 누가 만들고 있지?",
    },
    "분석": {"영상전": "우리 일 중에 여러 사이트를 돌면서 옮겨 적는 일이 꽤 있습니다. 이걸 대신 해 주는 사례입니다.",
             "떠올릴질문": "우리 팀에서 매주 사이트 돌면서 옮겨 적는 일이 뭐지?"},
    "생성": {"영상전": "기성 도구를 쓰다 보면 우리 항목이 안 맞는 경우가 있습니다. 그럴 때 우리 화면을 직접 만든 사례입니다.",
             "떠올릴질문": "우리 팀이 엑셀로 손 취합하는 현황이 뭐지?"},
    "마무리": {"발표장면": "제가 매주 두 시간 걸리던 표인데요, 이제는 월요일 아침에 메일로 와 있습니다.",
               "고를것": "떠오른 그 표 하나, 그 사람 한 명"},
}
MAXLEN = 90


def _s(v, default):
    t = re.sub(r"\s+", " ", str(v or "")).strip()
    if not t:
        return default
    return t if len(t) <= MAXLEN else t[:MAXLEN].rstrip(" ,.") + "…"


def clamp(data):
    """LLM 이 준 JSON 을 FALLBACK 모양으로 맞춘다. 빠진 칸은 기본 문장으로 채운다."""
    out = {}
    for sec, fb in FALLBACK.items():
        got = (data or {}).get(sec) or {}
        out[sec] = {}
        for k, dv in fb.items():
            if isinstance(dv, list):
                v = got.get(k) if isinstance(got.get(k), list) else []
                out[sec][k] = [_s(v[i] if i < len(v) else "", dv[i]) for i in range(len(dv))]
            else:
                out[sec][k] = _s(got.get(k), dv)
    return out


def prompt_for(deck, plan):
    cases = []
    for ax in C.AXES:
        sc = deck.get(ax, {})
        why = (plan or {}).get(ax, {})
        steps = " / ".join(s.get("이름", "") for s in sc.get("단계", []))
        play = "; ".join(f"{p.get('시작')}~{p.get('끝')} {p.get('라벨', '')}" for p in sc.get("재생", []))
        cases.append(f"""### {ax}축
- 덱 제목: {sc.get('제목', '')}
- 무엇을: {sc.get('무엇을', '')}
- 단계: {steps}
- 세션에서 트는 구간: {play or '(없음)'}
- 우리 팀 적용(기획): {why.get('우리팀', '(없음)')}""")
    return f"""너는 사내 AX 확산 담당자가 부서장회의에서 읽을 발표 멘트의 「생각열기」 문장만 쓴다.
청중은 부서장이다. 13분 동안 외부 사례 두 개(분석 1 + 생성 1)를 보고, 끝에 자기 팀 일 하나를 떠올려야 한다.

## 이번 회차 기획
{(plan or {}).get('기획', '(없음)')}

## 두 사례
{chr(10).join(cases)}

## 쓸 것 (JSON 하나만 출력)
{{
  "도입": {{
    "장면": ["오늘 아침 팀원 모니터에서 벌어지는 분석축 사례 이전의 손일 장면 한 문장", "생성축 사례 이전의 손일 장면 한 문장"],
    "질문": "그 일에서 사람이 실제로 판단한 순간을 묻는, 대답을 받지 않는 질문 한 문장",
    "바꿔끼우기": ["분석축 사례가 적용된 뒤 월요일 아침 장면 한 문장", "생성축 사례가 적용된 뒤 장면 한 문장"],
    "잇기질문": "청중이 발표 내내 품고 있을 질문. 「우리 팀에서 ~는 누가 ~고 있지?」 꼴"
  }},
  "분석": {{"영상전": "영상 틀기 전 두 문장 이내 도입", "떠올릴질문": "「우리 팀에서 ~가 뭐지?」 꼴"}},
  "생성": {{"영상전": "영상 틀기 전 두 문장 이내 도입", "떠올릴질문": "「우리 팀에서 ~가 뭐지?」 꼴"}},
  "마무리": {{
    "발표장면": "4주 뒤 우리 팀 담당자가 이 자리에서 자기 자동화를 소개하며 하는 한 마디 (따옴표 없이)",
    "고를것": "오늘 부서장이 정해 갈 것을 「~ 하나, ~ 한 명」 꼴로"
  }}
}}

## 규칙
- 발표자가 소리 내어 읽는 존댓말 구어체. 문장마다 {MAXLEN}자 이내.
- 장면은 **물건 이름**으로 쓴다(엑셀 표, 메일, 회의 녹음). 「효율이 오른다」 같은 효과 문구 금지.
- 사례에 없는 기능, 지어낸 수치 금지. 「두 시간」 같은 시간은 예시 말투로만.
- 채용공고·이직·구인 소재 금지(사내에서 인사 신호로 읽힌다).
- 이모지·줄표 금지.
"""


def load_script(out_d, deck, plan, reset):
    """(멘트 dict, 출처). 출처 = 사람/LLM/기본."""
    pair = [deck.get(ax, {}).get("영상ID", "") for ax in C.AXES]
    sp = os.path.join(out_d, SCRIPT_NAME)
    if os.path.exists(sp) and not reset:
        try:
            have = json.load(io.open(sp, encoding="utf-8"))
            if have.get("영상ID") == pair:
                return clamp(have), have.get("_출처", "사람")
            print("  T1_멘트.json 이 다른 사례 쌍을 말하고 있어 다시 씁니다 "
                  f"({have.get('영상ID')} → {pair})")
        except Exception as e:
            print(f"  T1_멘트.json 을 못 읽어 다시 씁니다: {e}")
    data = L.ask(prompt_for(deck, plan), os.path.join(out_d, "llm"), TAG) if L.available() else None
    src = "LLM" if data else "기본"
    body = clamp(data)
    io.open(sp, "w", encoding="utf-8").write(json.dumps(dict(
        _읽어주세요="발표 멘트의 생각열기 문장입니다. 고치고 build_script_t1.py 를 다시 돌리면 유지됩니다 "
                   "(--reset 하면 다시 씁니다). 영상ID 쌍이 바뀌면 자동으로 다시 씁니다.",
        _출처=src, 영상ID=pair, **body), ensure_ascii=False, indent=2))
    return body, src


def deck_title(out_d, rnd):
    """덱에 실제로 찍힌 회차 이름(「10월 첫번째」, 옛 덱은 「9월 2주차」)을 읽는다.
    없으면 회차 날짜로 다시 짓는다. 로테이션 슬롯은 이름이 아니라 회차 날짜에서 낸다."""
    p = os.path.join(out_d, f"T1_부서장회의_{rnd}.html")
    head = io.open(p, encoding="utf-8").read(4000)
    m = re.search(r"\d+월 (?:\S+번째|\d+주차)", head)
    return m.group(0) if m else B.round_label(datetime.strptime(rnd, "%Y%m%d").date())


def mmss(sec):
    return f"{sec // 60}:{sec % 60:02d}"


def row_info(vid):
    try:
        all_rows = B.load_rows()[0]
    except SystemExit:
        return ""
    r = next((x for x in all_rows if x.get("영상ID") == vid), None)
    if not r:
        return ""
    s = int(r.get("길이초") or 0)
    return f"{r.get('채널', '')} · {s // 60}분 {s % 60}초"


# ── 렌더 ────────────────────────────────────────────────────────────────
CSS = """
:root{--ink:#1E2B33;--soft:#5D6B72;--line:#DEE2DA;--green:#00794A;--hl:#FFF3A8;--ana:#2F6FB0;--gen:#7A4E96;--warn:#B5461F}
*{box-sizing:border-box}body{margin:0;background:#FAFAF6;color:var(--ink);
font-family:'Apple SD Gothic Neo','Malgun Gothic',sans-serif;font-size:16px;line-height:1.75;word-break:keep-all}
.wrap{max-width:860px;margin:0 auto;padding:40px 20px 80px}
h1{font-size:26px;margin:0 0 6px}.meta{color:var(--soft);font-size:14px;margin-bottom:24px}
h2{font-size:20px;margin:40px 0 8px;padding-top:18px;border-top:2px solid var(--ink)}
h2 .t{float:right;font-size:14px;color:var(--soft);font-weight:500}
h3{font-size:16px;margin:22px 0 6px;color:var(--green)}
.say{background:#fff;border-left:4px solid var(--green);padding:12px 18px;margin:8px 0;border-radius:0 8px 8px 0}
.say p{margin:4px 0}.say b{background:var(--hl)}
.cue{color:var(--soft);font-style:italic;margin:6px 0}
table{border-collapse:collapse;width:100%;font-size:14px;margin:10px 0}
th,td{border:1px solid var(--line);padding:6px 10px;text-align:left;vertical-align:top}th{background:#F0F1EC}
.badge{display:inline-block;font-size:12px;padding:1px 8px;border-radius:10px;background:#E6F2EC;color:var(--green);margin-left:6px}
.badge.w{background:#FBE9E2;color:var(--warn)}
.ana{color:var(--ana)}.gen{color:var(--gen)}
@media print{body{background:#fff}.wrap{padding:0}h2{break-before:auto}.say{break-inside:avoid}}
"""


def say(*lines):
    return '<div class="say">' + "".join(f"<p>{ln}</p>" for ln in lines) + "</div>"


def cue(t):
    return f'<div class="cue">({E(t)})</div>'


def case_block(no, ax, sc, sm, info):
    cls = "ana" if ax == "분석" else "gen"
    plays = sc.get("재생") or []
    H = [f'<h2><span class="{cls}">{no}</span>쪽. {"① 분석" if ax == "분석" else "② 생성"}: '
         f'{E(sc.get("중심", ""))}<span class="t">3분 30초</span></h2>']
    H.append("<h3>영상 전 (30초)</h3>")
    if plays:
        p = plays[0]
        H.append(say(E(sm[ax]["영상전"]),
                     f'<b>{E(p.get("시작", ""))}</b>부터 틉니다. {E(p.get("라벨", ""))} 장면입니다.'))
        a, b = T.secs(p.get("시작")), T.secs(p.get("끝"))
        span = (b - a) if (a is not None and b is not None and b > a) else 0
        note = f"재생 {E(p.get('시작'))}~{E(p.get('끝'))}"
        if span:
            note += f" ({mmss(span)})"
            if span > CLIP_SEC + 30:
                note += f" · 13분에 맞추려면 {mmss(a + CLIP_SEC)} 안팎에서 끊는다"
        if p.get("출처") == "LLM":
            note += " · LLM 이 고른 구간이라 미리 틀어 확인한다"
        H.append(cue(note))
    else:
        H.append(say(E(sm[ax]["영상전"])))
        H.append(cue("재생 구간이 없다 — 영상 처음부터 재생된다. 대본에 구간을 적어 두면 좋다"))
    H.append("<h3>영상 재생 (약 2분)</h3>")
    H.append("<h3>영상 후 (1분)</h3>")
    steps = sc.get("단계") or []
    lines = [f"흐름은 {len(steps)}단계입니다."] if steps else []
    for i, s in enumerate(steps, 1):
        lines.append(f'{i}. <b>{E(s.get("이름", ""))}</b>. {E(s.get("설명", ""))}.')
    lines.append(f'떠올려 볼 질문은 이겁니다. <b>「{E(sm[ax]["떠올릴질문"])}」</b>')
    H.append(say(*lines))
    return "".join(H)


def build(out_d, rnd, deck, sm, src, label):
    slot = ((B.week_of(datetime.strptime(rnd, "%Y%m%d").date()) - 1) % 4) + 1
    ana, gen = deck["분석"], deck["생성"]
    warns = []
    H = ["<!doctype html><html lang='ko'><head><meta charset='utf-8'>",
         "<meta name='viewport' content='width=device-width,initial-scale=1'>",
         f"<title>T1 발표 멘트 · {label}</title><style>{CSS}</style></head><body><div class='wrap'>"]
    badge = {"사람": "", "LLM": '<span class="badge">생각열기 LLM 초안</span>',
             "기본": '<span class="badge w">LLM 없이 기본 문장</span>'}.get(src, "")
    H.append(f"<h1>T1 부서장회의 발표 멘트{badge}</h1>")
    H.append(f"<div class='meta'>{label} · 회차 {rnd} · 덱 1~6쪽 발표 (7쪽 전략표는 넘기지 않음) · "
             f"생성 {datetime.now():%Y-%m-%d %H:%M}</div>")

    # 시간표
    H.append("<table><tr><th>쪽</th><th>내용</th><th>시간</th></tr>")
    H += [f"<tr><td>{n}</td><td>{E(t)}</td><td>{mmss(s)}</td></tr>" for n, t, s in PLAN]
    H.append(f"<tr><th></th><th>합계</th><th>{mmss(sum(s for *_, s in PLAN))}</th></tr></table>")

    d = sm["도입"]
    H.append('<h2>1쪽. 표지 + 생각열기 도입<span class="t">1분 30초</span></h2>')
    H.append("<h3>① 장면 떠올리기</h3>")
    H.append(say("본론 전에 잠깐 떠올려 보시겠어요?", "오늘 아침, 팀원들 모니터를 한번 생각해 보세요.",
                 E(d["장면"][0]), E(d["장면"][1])))
    H.append("<h3>② 질문 던지기</h3>")
    H.append(say(E(d["질문"])))
    H.append(cue("2~3초 멈춤. 대답을 받지 않는다"))
    H.append("<h3>③ 상상 바꿔 끼우기</h3>")
    H.append(say("이번엔 장면을 바꿔 보겠습니다.", E(d["바꿔끼우기"][0]), E(d["바꿔끼우기"][1]),
                 "팀원은 그 일을 <b>하는 사람</b>이 아니라 <b>보고 판단하는 사람</b>이 됩니다."))
    H.append("<h3>④ 표지 문구로 잇기</h3>")
    H.append(say("오늘 보여 드릴 두 사례가 딱 이 두 장면입니다.",
                 "<b>데이터를 모아 오고, 그걸로 만들어 냅니다.</b>",
                 f'보시면서 하나만 떠올려 주세요. <b>「{E(d["잇기질문"])}」</b>',
                 "끝날 때 그 답을 여쭤보겠습니다."))

    H.append('<h2>2쪽. 업무 자동화 현황<span class="t">1분 30초</span></h2>')
    if [s[0] for s in T.NET_STATS] == STATS_SAID:
        talk = STATS_TALK
    else:
        talk = [f"<b>{E(n)}</b>. {re.sub(r'<[^>]+>', '', t)}" for n, t in T.NET_STATS]
        warns.append("2쪽 수치(build_t1.NET_STATS)가 멘트 작성 때와 달라 화면 문구를 그대로 읽는 멘트로 바꿨다. "
                     "build_script_t1.py 의 STATS_TALK 를 새 수치로 다시 쓴다")
    H.append(say("먼저 바깥 상황부터 짧게 보겠습니다.", *talk,
                 "그래서 도입했느냐는 이제 의미가 없는 질문입니다. 중요한 건 <b>무엇을 자동화했느냐</b>입니다.",
                 "AI를 쓰는 곳은 네 덩어리입니다. <b>모아 온다, 만들어 낸다, 알아서 돈다, 물어보면 답한다.</b>",
                 "오늘 볼 두 사례는 이 중 왼쪽 두 개입니다."))

    H.append('<h2>3쪽. 이번 주 두 사례<span class="t">1분</span></h2>')
    ia, ig = row_info(ana.get("영상ID")), row_info(gen.get("영상ID"))
    # 대본 문장은 「~한다」 꼴이라 소리 내어 읽으면 어색하다 — 제목만 말하고 설명은 화면 참고로 둔다
    H.append(say(f'첫 번째는 <b>분석</b> 사례입니다. 「{E(ana.get("제목", ""))}」',
                 f'두 번째는 <b>생성</b> 사례입니다. 「{E(gen.get("제목", ""))}」',
                 "원본 영상은 길어서, 오늘은 핵심 구간만 잘라서 보여 드리겠습니다."))
    H.append(cue(f'화면 설명: 분석 {ana.get("무엇을", "")} / 생성 {gen.get("무엇을", "")}'))
    if ia or ig:
        H.append(cue(f"원본: 분석 {ia or '확인 필요'} / 생성 {ig or '확인 필요'}"))

    H.append(case_block(4, "분석", ana, sm, ia))
    H.append(case_block(5, "생성", gen, sm, ig))

    m = sm["마무리"]
    H.append('<h2>6쪽. 이 자리는 매주 돕니다 + 마무리<span class="t">2분</span></h2>')
    H.append("<h3>본문 (40초)</h3>")
    H.append(say(f"이 자리는 4주에 한 바퀴 돕니다. 오늘이 <b>{slot}주차</b>입니다.",
                 "세 주는 오늘처럼 바깥 사례를 보고 우리 걸로 바꿔 봅니다.",
                 "그리고 <b>네 번째 주에는 이 자리에 우리 회사 팀이 섭니다.</b> 자기 팀 자동화를 10분 동안 직접 발표합니다."))
    H.append(cue(f"화면의 {slot}주차 칸: {T.ROT_LINE.get(slot, ('', ''))[0]}"))
    H.append("<h3>① 처음 질문 다시 부르기</h3>")
    H.append(say("시작할 때 질문 하나를 드렸습니다.", f'<b>「{E(d["잇기질문"])}」</b>',
                 "아마 이름 한두 개는 떠오르셨을 겁니다."))
    H.append("<h3>② 4주 뒤 장면 상상하기</h3>")
    H.append(say("그 사람을 4주 뒤로 보내 보겠습니다.",
                 "4주차 이 자리 화면에 <b>우리 팀 이름</b>이 떠 있고, 그 사람이 앞에 서 있습니다.",
                 f'「{E(m["발표장면"])}」',
                 "그리고 다른 부서장님들이 <b>「그거 우리 팀에도 되나요?」</b> 하고 묻고 있습니다."))
    H.append(cue("2~3초 멈춤"))
    H.append("<h3>③ 오늘 할 일 하나로 좁히기</h3>")
    H.append(say("그 장면은 오늘 하나만 고르면 시작됩니다.", f'<b>{E(m["고를것"])}</b>만 정해 주세요.',
                 "정해진 분은 AX 클리닉으로 보내 주시면 됩니다. 예약 없이 와서 「이거 되나요?」 하고 물으면 옆에 앉아 같이 만듭니다."))
    H.append("<h3>④ 닫는 한 문장</h3>")
    H.append(say("오늘은 남이 만든 걸 봤습니다. <b>4주 뒤에는 우리 팀 걸 보겠습니다.</b>",
                 "질문 받겠습니다. 방금 떠올린 그것부터 말씀해 주셔도 좋습니다."))

    # 확인할 점
    for ax, sc in (("분석", ana), ("생성", gen)):
        if not sc.get("재생"):
            warns.append(f"{ax} 사례에 재생 구간이 없다 (T1_대본.json 「재생」)")
    if src == "기본":
        warns.append("LLM 이 못 돌아 생각열기가 기본 문장이다 — 이번 사례에 맞게 T1_멘트.json 을 고친다")
    warns.append("클리닉 안내는 7쪽에만 있어 화면에 안 나온다 — 운영 요일·장소를 말로 덧붙일지 정한다")
    H.append("<h2>발표 전에 확인</h2><ul>" + "".join(f"<li>{E(w)}</li>" for w in warns) + "</ul>")
    H.append(cue(f"고치는 자리: 사례 내용은 T1_대본.json, 생각열기 문장은 {SCRIPT_NAME}"))
    H.append("</div></body></html>")
    return "\n".join(H)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", help="YYYYMMDD (기본: 이번 회차 수요일)")
    ap.add_argument("--reset", action="store_true", help="T1_멘트.json 을 버리고 다시 쓴다")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--llm-refresh", action="store_true")
    ap.add_argument("--open", action="store_true")
    a = ap.parse_args()
    L.enable(not a.no_llm, a.llm_refresh)

    rnd = a.round or f"{B.round_day():%Y%m%d}"
    out_d = os.path.join(C.ROOT, "out", rnd)
    deck_p = os.path.join(out_d, T.SCRIPT_NAME)
    if not os.path.exists(os.path.join(out_d, f"T1_부서장회의_{rnd}.html")) or not os.path.exists(deck_p):
        # 3·4주차(사내 전용)·미승인 주에는 덱이 없다 — 실패가 아니다
        print(f"  회차 {rnd} 에 T1 덱이 없어 발표 멘트를 만들지 않습니다.")
        return
    deck = json.load(io.open(deck_p, encoding="utf-8"))
    if not all(deck.get(ax) for ax in C.AXES):
        print(f"  T1_대본.json 에 두 축이 다 없어 발표 멘트를 만들지 않습니다.")
        return
    plan = None
    pp = os.path.join(out_d, "llm", "01_기획.json")
    if os.path.exists(pp):
        try:
            plan = json.load(io.open(pp, encoding="utf-8"))
        except Exception:
            plan = None

    label = deck_title(out_d, rnd)
    sm, src = load_script(out_d, deck, plan, a.reset)
    out = os.path.join(out_d, f"T1_발표멘트_{rnd}.html")
    io.open(out, "w", encoding="utf-8").write(build(out_d, rnd, deck, sm, src, label))
    print(f"생성 {out}  (생각열기: {src})")
    if a.open:
        webbrowser.open("file:///" + out.replace(os.sep, "/"))


if __name__ == "__main__":
    main()
