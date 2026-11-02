# -*- coding: utf-8 -*-
"""시스템정리 HTML — AX_source 전체를 한 장으로. (2026-09-11 신설)

  python tools/sysdoc.py            # 만들고 바탕화면에도 복사
  python tools/sysdoc.py --open     # 만들고 브라우저로 연다
  python tools/sysdoc.py --check    # 낡았는지만 본다 (self_test 가 부르는 자리)

산출
  AX_source/AX_source_시스템정리_v1.0.html   ← **정본 하나뿐이다**

⚠️ 2026-09-11 까지는 바탕화면에 사본을 같이 뒀다가 **걷어냈다.** 사본은 재생성 대상이 아니라서
   원본만 바뀌고 사본은 그대로 남는다 — **어느 쪽이 최신인지 모르는 상태**가 제일 나쁘다.

## 왜 스크립트로 만드나 — 옮겨 적은 숫자는 조용히 틀린다
「시드 채널 6개」·「조회수 3만」·「수 09:40 기획 / 목 09:40 제작」을 손으로 적어 두면
코드가 바뀐 뒤에도 **문서는 에러 없이 옛 숫자를 계속 말한다.** 그래서 살아 있는 값만 읽는다.

  · 시드 채널·게이트 수치   collect.py 상수          · 4주 로테이션   build_page.SLOTS
  · 적합도 가산점           build_page.fit() 실측     · 전술 주기      build_t1.TACTICS
  · 현재 재고·기사용 제외   out/pool + 회차 폴더      · 스케줄         config/task_*.xml

## 낡으면 어떻게 아나 — 스탬프
문서 안에 **원천 파일들의 해시**를 박아 둔다. README·배치·핵심 스크립트가 바뀌면 해시가
달라지고, `self_test.py` 가 **FAIL** 을 낸다. 「문서도 같이 고쳐라」를 기계가 강제하는 자리다.
⚠️ 스탬프는 **바뀐 것을 알려줄 뿐 내용을 고쳐 주지는 않는다.** FAIL 이 뜨면 이걸 다시 돌리고,
   서술이 실제로 맞는지 사람이 한 번 읽는다.
"""
import argparse, hashlib, io, json, os, re, sys, webbrowser
from datetime import date, datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_page as B
import collect as C
import build_t1 as T1

VERSION = "v1.0"
NAME = f"AX_source_시스템정리_{VERSION}.html"   # 폴더 밖으로 꺼내 봐도 어느
                                                # 폴더 이야기인지 알아야 해서 접두어를 붙였다
OUT = os.path.join(C.ROOT, NAME)

# 이 목록이 바뀌면 문서를 다시 만들어야 한다 — 스탬프의 원천.
WATCH = [
    "README.md",
    "tools/collect.py", "tools/build_page.py", "tools/build_t1.py",
    "tools/llm.py", "tools/build_brief.py", "tools/build_toon_prompt.py",
    "tools/collect_toon.py", "tools/approve.py", "tools/sysdoc.py",
    "tools/find_channels.py", "tools/axis_llm.py",
    "tools/publish.py", "tools/build_script_t1.py",
    "config/인스타툰_마스터.md", "config/LLM_컨셉.md",
]


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def stamp():
    """원천 파일들의 내용 해시 한 줄. 없는 파일은 «-» 로 센다(삭제도 변화다)."""
    h = hashlib.sha256()
    for rel in WATCH:
        p = os.path.join(C.ROOT, rel.replace("/", os.sep))
        h.update(rel.encode("utf-8"))
        h.update(io.open(p, "rb").read() if os.path.exists(p) else b"-")
    return h.hexdigest()[:16]


def current_stamp_in_doc():
    if not os.path.exists(OUT):
        return None
    m = re.search(r'data-stamp="([0-9a-f]+)"', io.open(OUT, encoding="utf-8").read())
    return m.group(1) if m else None


# ── 살아 있는 값 ─────────────────────────────────────────────────────────
def fit_points():
    """fit() 을 **실제로 불러** 가산점을 잰다 — 표에 숫자를 옮겨 적지 않는다."""
    base = {"제목": "무제", "_sec": 0, "업로드": "2000-01-01"}
    def probe(title, sec=0, up="2000-01-01"):
        r = dict(base); r["제목"] = title; r["_sec"] = sec; r["업로드"] = up
        return B.fit(r)[0]
    zero = probe("무제")
    recent = date.today().replace(year=date.today().year - 1).isoformat()
    return [
        ("실물을 그 자리서 준다", "무료로 나눠드려요", probe("무료로 나눠드려요") - zero),
        ("직접 만든 과정", "직접 만들었습니다", probe("직접 만들") - zero),
        ("실명·현업", "대표·개발자·창업", probe("대표") - zero),
        ("우리 업무 어휘", "회사·업무·보고서·엑셀", probe("업무") - zero),
        ("10~45분", "구간 인용하기 좋은 길이", probe("무제", sec=1200) - zero),
        ("최근 1년", "업로드가 1년 이내", probe("무제", up=recent) - zero),
        ("도구 강의 어휘", "A to Z·활용법·총정리", probe("활용법") - zero),
    ]


def inventory():
    rows = list(__import__("csv").DictReader(io.open(C.POOL_CSV, encoding="utf-8-sig"))) \
        if os.path.exists(C.POOL_CSV) else []
    keep = C.catalog_rows(rows)
    used = B.used_ids()
    by = {ax: sum(1 for r in keep if r["축"] == ax and r["영상ID"] not in used) for ax in C.AXES}
    return len(rows), len(keep), by, len(used), sum(1 for r in rows if r["축"] == "미분류")


def rounds():
    base = os.path.join(C.ROOT, "out")
    out = []
    for n in sorted(os.listdir(base)) if os.path.isdir(base) else []:
        if len(n) == 8 and n.isdigit():
            d = os.path.join(base, n)
            out.append((n, os.path.exists(os.path.join(d, "승인.json")),
                        os.path.exists(os.path.join(d, f"T1_부서장회의_{n}.html")),
                        len([x for x in os.listdir(d) if x.startswith("T2_") and x.endswith(".png")])))
    return out


def task_info():
    out = []
    cfg = os.path.join(C.ROOT, "config")
    for f in sorted(os.listdir(cfg)) if os.path.isdir(cfg) else []:
        if not f.endswith(".xml"):
            continue
        t = io.open(os.path.join(cfg, f), encoding="utf-16", errors="replace").read()
        if "<?xml" not in t[:200]:
            t = io.open(os.path.join(cfg, f), encoding="utf-8", errors="replace").read()
        days = " ".join(re.findall(r"<(Monday|Tuesday|Wednesday|Thursday|Friday)\s*/>", t)) or "?"
        st = re.search(r"<StartBoundary>([^<]+)</StartBoundary>", t)
        arg = re.search(r"<Arguments>([^<]+)</Arguments>", t)
        out.append((f.replace(".xml", ""), days,
                    (st.group(1)[11:16] if st else "?"),
                    esc(arg.group(1)) if arg else "?"))
    return out


# ── 문서 ─────────────────────────────────────────────────────────────────
CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"맑은 고딕","Malgun Gothic","Segoe UI Emoji",sans-serif;background:#eef0f2;
     color:#16212b;font-size:14px;line-height:1.62;padding:28px 22px 60px}
.wrap{max-width:1180px;margin:0 auto}
.hd{border-bottom:3px solid #16212b;padding-bottom:10px;margin-bottom:8px;
    display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap}
h1{font-size:26px;letter-spacing:-.7px}
.hd .sub{font-size:12.5px;color:#4a5763;text-align:right;line-height:1.6}
.toc{background:#fff;border:1px solid #cfd6dc;border-radius:5px;padding:10px 14px;margin:14px 0 20px;
     font-size:13px}
.toc a{color:#1d4f7c;text-decoration:none;margin-right:14px;white-space:nowrap;display:inline-block}
.toc a:hover{text-decoration:underline}
h2{font-size:17px;margin:26px 0 10px;padding:7px 13px;background:#16212b;color:#fff;border-radius:4px}
h3{font-size:14.5px;margin:18px 0 7px;padding-bottom:4px;border-bottom:1.5px solid #16212b}
p{margin:7px 0}
.card{background:#fff;border:1px solid #cfd6dc;border-radius:5px;padding:12px 15px;margin:10px 0}
table{width:100%;border-collapse:collapse;font-size:13px;background:#fff;margin:8px 0}
th,td{border:1px solid #d9dfe4;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#e9edf0;font-weight:700;white-space:nowrap}
td.k{font-family:Consolas,monospace;white-space:nowrap;font-weight:700;width:1%}
td.n{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
code{font-family:Consolas,monospace;background:#eef1f3;padding:1px 5px;border-radius:3px;font-size:12.5px}
.warn{background:#fdf4f3;border-left:4px solid #c0392b;padding:8px 12px;margin:9px 0;border-radius:0 3px 3px 0}
.warn b{color:#a5301f}
.ok{background:#f2fbf7;border-left:4px solid #0a7d55;padding:8px 12px;margin:9px 0;border-radius:0 3px 3px 0}
.lane{border:1px solid #cfd6dc;border-radius:5px;overflow:hidden;margin:10px 0;background:#fff}
.lane>.t{padding:6px 13px;color:#fff;font-weight:700;font-size:13.5px}
.wed>.t{background:#1d4f7c}.human>.t{background:#a8531a}.thu>.t{background:#0a6b4a}.toon>.t{background:#6b3f86}
.lane>.b{padding:10px 13px}
.lane ol{margin:0 0 0 20px}.lane li{margin-bottom:4px}
.badge{display:inline-block;font-size:11px;font-weight:700;padding:1px 6px;border-radius:3px;
       background:#e5eaee;color:#3d4a56;margin-left:5px}
.badge.man{background:#fbead9;color:#a8531a}.badge.llm{background:#efe3f7;color:#6b3f86}
.ft{margin-top:32px;border-top:2px solid #16212b;padding-top:12px;font-size:12.5px;color:#4a5763}
@media print{body{background:#fff;padding:0}.toc{display:none}}
"""


def build():
    n_all, n_keep, by_ax, n_used, n_unk = inventory()
    rs = rounds()
    H = [f'<!doctype html><html lang="ko"><head><meta charset="utf-8">',
         f'<title>AX_source 시스템정리 {VERSION}</title><style>{CSS}</style></head>',
         f'<body data-stamp="{stamp()}"><div class="wrap">']

    H.append(f'''<div class="hd"><h1>AX_source — 시스템정리 <span style="color:#5a6874">{VERSION}</span></h1>
      <div class="sub">생성 {datetime.now():%Y-%m-%d %H:%M} · <b>이 문서는 자동 생성물</b><br>
      손으로 고치지 말고 <code>python tools/sysdoc.py</code> 를 다시 돌린다</div></div>''')

    H.append('<div class="toc">' + " ".join(
        f'<a href="#s{i}">{t}</a>' for i, t in enumerate([
            "1. 무엇을 하는 폴더인가", "2. 주간 흐름", "3. 소재를 어디서 캐나",
            "4. 무엇을 추천하나", "5. 회차 기획서", "6. 승인과 알림",
            "7. T1 부서장회의 덱", "8. T2 인스타툰", "9. 산출물", "10. 현재 상태",
            "11. 밟으면 죽는 자리", "12. 정본과 동기화"], 1)) + '</div>')

    # 1
    H.append('<h2 id="s1">1. 무엇을 하는 폴더인가 — 역할이 둘이다</h2>')
    H.append('''<div class="card"><p><b>① 유튜브 쇼츠 소재 발굴·제작</b> <span class="badge">원래 목적</span><br>
      축A 분석자동화 / 축B 생성물(이미지·영상·음악). <code>youtube_search.html</code> ·
      <code>tools/scan.py --axis A|B</code> → <code>out/scan_*.csv</code>.</p>
      <p style="margin-top:9px"><b>② AX확산 계획(docs/AX확산) A급 자동화 실행처</b> <span class="badge">현재 주력 — 이 문서 대부분</span><br>
      매주 한 회차를 돌려 <b>T1 부서장회의 덱</b>과 <b>T2 인스타툰</b>의 재료를 낸다.</p></div>''')
    H.append('''<div class="warn"><b>⚠️ 두 역할의 「축」이 서로 다른 것이다.</b>
      ①의 축B는 <b>이미지·영상·음악</b>이고, ②의 「생성」은 <b>업무 산출물·시스템</b>이다. 섞으면 안 된다.</div>''')

    # 2
    H.append('<h2 id="s2">2. 주간 흐름 — 한 회차가 이틀에 걸쳐 돈다</h2>')
    H.append('<p><b>회차 = 그 주 수요일.</b> 오늘 날짜로 폴더를 잡으면 수요일 기획과 목요일 산출물이 '
             '갈려서, 목요일 빌드가 기획을 못 찾고 <b>조용히 새로 기획해 버린다.</b></p>')
    H.append('''<div class="lane wed"><div class="t">■ 수 09:40 — 기획 · run_plan.bat</div><div class="b"><ol>
      <li><b>A1</b> <code>collect.py</code> — 시드 채널 수집 · 게이트(조회 5천 · 5~60분 · 최근 6개월) · 축 판정 · 공급 경보</li>
      <li><b>A1b</b> <code>axis_llm.py</code> <span class="badge llm">LLM 심사</span> — 낱말이 못 가르는 <b>접전분만</b>:
          ①업무 사례인가(<b>강의·수익화 제외</b>) ②분석/생성. 판정은 <b>박제</b>되어 다시 안 묻는다</li>
      <li><b>A1c</b> <code>refill.py</code> — <b>재고가 발동선 이하일 때만</b> 보충. 차 있으면 <b>수 초 만에 끝</b></li>
      <li><b>A2p</b> <code>build_brief.py</code> — <b>LLM 이 회차를 기획하고 한 쌍을 고른다</b> <span class="badge llm">LLM ①</span> → 기획서 PDF</li>
      <li><code>build_page.py</code> — 소재추천.html (<b>session() = 같은 쌍을 보게 하는 단일 지점</b>)</li>
      <li><code>self_test.py</code> → <code>notify.py approve</code> <b>슬랙 승인 요청</b></li></ol>
      <p style="font-size:12.5px;color:#4a5763"><code>run_plan.bat rebuild</code> 는 API 없이 카탈로그·기획서만 다시 만든다(알림도 안 보낸다).</p>
      </div></div>''')
    H.append('''<div class="lane human"><div class="t">■ 사람 — 승인 게이트</div><div class="b">
      <p>슬랙 알림을 받고 기획서를 읽은 뒤 회차 폴더의 <code>승인.bat</code> 더블클릭 → <code>승인.json</code></p>
      <p><b>미승인은 실패가 아니다.</b> ⚠️ <b>스케줄러는 정상으로 돈다</b> — 목요일 배치가 실행되고,
      맨 앞 승인 확인에서 걸려 <b>아무것도 만들지 않고 끝날 뿐</b>이다(로그에 <code>not_approved</code>).
      「스케줄러가 안 돌았다」가 아니라 <b>「돌았는데 만들 게 없었다」</b>가 맞다.</p>
      <p>승인 시한은 <b>목요일 09:40</b>이다(수요일에 꼭 해야 하는 게 아니다). 놓쳤으면 그 뒤에 승인하고
      <code>run_weekly.bat</code> 을 손으로 한 번 돌리면 된다 — 다음 주까지 기다릴 필요 없다.
      승인은 <b>그 회차에만</b> 유효해서 다음 수요일이면 따라오지 않는다.</p></div></div>''')
    H.append('''<div class="lane thu"><div class="t">■ 목 09:40 — 제작 · run_weekly.bat (승인됐을 때만)</div><div class="b"><ol>
      <li>승인 확인 — 없으면 여기서 종료</li>
      <li><code>build_t1.py</code> <span class="badge llm">LLM ②</span> → <b>T1 덱 7장</b></li>
      <li><code>build_brief.py</code> 기획서 갱신(승인 도장) → <code>build_page.py</code> <b>반드시 마지막</b></li>
      <li><code>self_test.py</code> → <code>publish.py</code> <b>GitHub Pages 발행</b> → <code>notify.py done</code></li></ol>
      <p style="font-size:12.5px;color:#4a5763"><b>T1 이 실패해도 배치는 계속 간다</b> — 그 주 추천 자체는 살아 있어야 하기 때문이다.</p>
      <p style="font-size:12.5px;color:#4a5763"><b>발행이 배치 안에 있는 이유</b> — 페이지는 회차마다 덮어쓰이는데,
      발행을 잊으면 <b>공개본만 조용히 낡는다</b>. 화면도 링크도 정상으로 보여서 눈으로는 못 알아챈다.
      승인 게이트 뒤에 있으므로 <b>승인된 회차만</b> 공개 URL 에 닿는다.</p>
      </div></div>''')

    ti = task_info()
    if ti:
        H.append('<h3>스케줄러 작업</h3><table><tr><th>작업</th><th>요일</th><th>시각</th><th>실행</th></tr>'
                 + "".join(f'<tr><td class="k">{esc(n)}</td><td>{esc(d)}</td><td>{esc(t)}</td>'
                           f'<td style="font-size:12px">{a}</td></tr>' for n, d, t, a in ti) + '</table>')

    # 3
    H.append('<h2 id="s3">3. 소재를 어디서 캐나 — 검색이 아니라 채널</h2>')
    H.append(f'''<table><tr><th>항목</th><th>값</th><th>왜</th></tr>
      <tr><td class="k">대상</td><td>시드 채널 <b>{len(C.SEED_CHANNELS)}개</b>의 업로드 재생목록</td><td>검색어로는 분석/생성이 안 갈린다(상위 22건 중 11건 중복)</td></tr>
      <tr><td class="k">기간</td><td><b>최근 6개월</b> (<code>collect.FRESH_DAYS</code>)</td><td>수집·재고·채널 실측이 <b>같은 창</b>을 쓴다. 6개월이 넘으면 <b>기술 격차</b>가 생긴다. 매주 같은 범위를 다시 훑고 영상ID로 누적 — 새 업로드만 신규가 된다</td></tr>
      <tr><td class="k">출처</td><td><b>시드 / 발굴</b></td><td>보충 루프가 캔 채널의 영상도 적립된다. 「시드 산출」과 「발굴이 떠받치는 것」을 갈라야 경보와 분기 채널 재점검이 선다</td></tr>
      <tr><td class="k">비용</td><td>채널당 5~6 units · 6채널 <b>약 22 units</b></td><td>검색어 1개(101 units)의 1/20</td></tr>
      <tr><td class="k">조회수</td><td class="n">{C.MIN_VIEWS:,} 이상</td><td rowspan="4">게이트를 못 넘으면 <b>원장에 아예 안 넣는다</b></td></tr>
      <tr><td class="k">길이</td><td class="n">{C.MIN_SEC:,} ~ {C.MAX_SEC:,}초 ({C.MIN_SEC//60}~{C.MAX_SEC//60}분)</td></tr>
      <tr><td class="k">제목 한글</td><td class="n">{C.MIN_HANGUL}자 이상</td></tr>
      <tr><td class="k">부정·광고</td><td class="n">금지어 {len(C.NEGATIVE) + len(C.PROMO)}개</td></tr>
      </table>''')
    H.append('<table><tr><th>#</th><th>시드 채널</th><th>넣은 근거</th></tr>' + "".join(
        f'<tr><td class="n">{i}</td><td class="k">{esc(a)}</td><td>{esc(r)}</td></tr>'
        for i, (a, _cid, r) in enumerate(C.SEED_CHANNELS, 1)) + '</table>')
    H.append('<div class="warn"><b>⚠️ 성과지수(조회수÷구독자)는 게이트가 아니다</b> — 표기만 남는다. '
             '레퍼런스 2건이 0.44배·1.9배라 어떤 배수 컷을 걸어도 원하는 소재가 안 들어온다. '
             '<b>품질을 결정하는 것은 시드 채널 선정이고, 분기 1회 재점검한다.</b></div>')
    H.append('<div class="warn"><b>⚠️ 신선도 경보(축별 <u>신규 적립</u> 3건 미만)는 자주 뜬다.</b> '
             '이미 올해치를 다 긁어서, <b>새로</b> 들어오는 건 그 사이 올라온 것뿐이다. '
             '경보는 대개 「채널이 낡았다」가 아니라 <b>주 1회 주기에 하한이 안 맞는다</b>는 뜻이다.<br>'
             '⚠️ <b>경보는 공급 신호일 뿐, 후보를 줄이지 않는다.</b> 매주 같은 범위를 다시 훑지만 '
             '지난 회차에 모은 것은 <b>원장에 그대로 남아 다음 회차에도 후보다</b>(영상ID 로 dedup 하고 '
             '조회수만 갱신한다). 후보에서 빠지는 건 <b>승인된 회차에서 실제로 쓴 것뿐</b>이다.</div>')

    # 4
    H.append('<h2 id="s4">4. 무엇을 추천하나 — 고르는 것은 점수표가 아니라 LLM</h2>')
    H.append('<p>게재 게이트를 통과한 <b>전량</b>을 축별로 나눠 LLM 에 넘긴다. '
             '<b><code>fit()</code> 상위 몇 건으로 좁혀서 주지 않는다</b> — 그러면 기획이 아니라 '
             '「기계 점수가 이미 좁혀 놓은 것 중 고르기」가 되고, 낱말 점수가 놓친 사례는 후보에 못 든다.</p>')
    H.append('<p>LLM 이 하는 일은 셋이다 — ① <b>이번 회차를 무엇에 대한 회차로 만들지</b> 한 줄로 정하고 '
             '② 그 기획에 맞는 <b>분석 1 + 생성 1</b>을 고르고 ③ <b>제친 후보 2건</b>과 이유를 적는다.</p>')
    H.append('<div class="warn"><b>⚠️ 목록에 없는 영상ID 를 내면 기획 전체를 무르고 <code>fit()</code> 1위로 되돌린다.</b> '
             '그냥 두면 에러 없이 엉뚱한 영상이 덱에 실린다.</div>')
    H.append('<h3>fit() — 선택에서 빠졌지만 세 군데서 산다</h3>'
             '<p>화면의 「왜 후보에 있나」 · 2·3순위 대안 · <code>self_test</code> 감시(레퍼런스 2건이 각 축 1~2위인가).</p>')
    H.append('<table><tr><th>가산 조건</th><th>예</th><th>점수</th></tr>' + "".join(
        f'<tr><td>{esc(n)}</td><td style="color:#4a5763">{esc(e)}</td>'
        f'<td class="n"><b>{v:+d}</b></td></tr>' for n, e, v in fit_points()) + '</table>')
    H.append('<h3>같은 사례를 두 번 쓰지 않는다</h3>'
             '<p><b>승인된 회차</b>에서 쓴 영상은 다음 회차 후보에서 뺀다(<code>build_page.used_ids()</code>). '
             '기획만 하고 승인을 못 받은 회차의 쌍은 세션에 나간 적이 없으므로 다시 뽑혀도 된다. '
             '원장에서 지우지는 않는다 — 무엇을 언제 썼는지는 남아야 한다.</p>')
    H.append('<div class="warn"><b>⚠️ 재고가 회차마다 축별 1건씩 줄어드는 쪽으로만 움직인다.</b> '
             '얕은 축이 먼저 마른다 — 시드 채널 보강이 그만큼 급하다.</div>')

    # 5
    H.append('<h3>A1b — LLM 심사 <span class="badge">2026-09-11 신설</span></h3>')
    H.append('<p><b>낱말 점수는 「사례」와 「도구 강의」를 못 가른다.</b> 2026-09-11 실측에서 '
             '접전 27건 중 <b>22건이 업무 사례가 아니었고</b>, 그 22건이 '
             '<b>분석축 13건 중 10건</b>을 차지하고 있었다 — <b>재고가 부풀려져 있었다</b>'
             '(실제 공급 월 1.17건이 아니라 <b>0.50건</b>).</p>')
    H.append("""<table><tr><th>무엇</th><th>어디에 적히나</th></tr>
      <tr><td>축 교정 (분석 ↔ 생성)</td><td class="k">out/pool/축지정.csv</td></tr>
      <tr><td><b>제외</b> (강의·수익화·광고·개념설명)</td><td class="k">out/pool/제외목록.csv</td></tr>
      <tr><td>되살린 것 — <b>다시는 제외 안 됨</b></td><td class="k">out/pool/심사복구.csv</td></tr></table>""")
    H.append('<div class="warn"><b>⚠️ 제외해도 원장에서 지우지 않는다.</b> 추천·기획에서만 빠지고 이력은 남는다. '
             '되살리려면 <code>python tools/axis_llm.py --restore &lt;영상ID&gt;</code> — '
             '되살린 건 <b>다시 제외되지 않는다</b>.<br>'
             '⚠️ <b>사람 판정이 이긴다</b> — 사유가 <code>LLM:</code> 으로 시작하지 않는 행은 안 건드린다.<br>'
             '⚠️ <b>판정 저장은 «병합»이어야 한다.</b> 2026-09-11 에 덮어쓰기로 짰다가 배치가 두 번 돌자 '
             '제외목록이 <b>37건 → 5건</b>으로 날아갔다 — 재심사 방지 때문에 복원도 안 됐고, '
             '그대로 뒀으면 <b>매주 강의가 후보로 되살아났다.</b></div>')

    H.append('<h3>A1c — 재고 보충 루프 <span class="badge">2026-09-11 신설</span></h3>')
    H.append('<p>매주 발굴하면 <b>사람 검토가 못 따라가고 배치도 길어진다.</b> 그래서 '
             '<b>재고가 발동선 아래로 떨어진 주에만</b> 돌고 목표선까지 채운다'
             '(히스테리시스 — 임계가 하나면 경계에서 매주 켜졌다 꺼졌다 한다).</p>')
    H.append("""<table><tr><th>라운드</th><th>무엇을 캐나</th></tr>
      <tr><td class="k">R1</td><td>후보 큐에서 아직 안 캔 채널</td></tr>
      <tr><td class="k">R2+</td><td><b>LLM 이 검색어를 만들고</b> → 영상 조회수 순 발굴 → 그 채널을 캔다</td></tr>
      <tr><td class="k">매 라운드 끝</td><td>심사 → 재고 재측정 → 목표 도달이면 종료</td></tr></table>""")
    H.append('<div class="warn"><b>⚠️ 발굴 채널을 시드에 «자동 편입하지 않는다».</b> '
             '혼잡스(조회 32만·게이트 9건 통과)처럼 <b>수익화 채널은 숫자로 못 거른다.</b> '
             '영상만 적립하고 <b>시드 편입은 분기 1회 사람이</b> 한다.<br>'
             '⚠️ <b>LLM 이 「검색어」가 아니라 「문장」을 쓴다.</b> 첫 실행에서 15개 쿼리가 '
             '<b>전부 채널 0개</b>였다(「엑셀 피벗테이블로 고객 문의 데이터 집계해서…」). '
             '→ <b>2~4단어</b> 규칙 + 코드로도 5단어·24자 초과를 버린다. '
             '0건이면 <b>날짜 제한을 풀고 한 번 더</b> 찾는다.<br>'
             '⚠️ <b>쿼리 성과를 <code>out/pool/쿼리성과.csv</code> 에 남긴다</b> — 다음 회차 '
             'LLM 이 이걸 보고 같은 실패를 피한다.</div>')

    # 5 — 회차 기획서
    H.append('<h2 id="s5">5. 회차 기획서 — 승인의 근거 문서</h2>')
    H.append('<p><b>관리자가 매주 읽는 것은 이 한 부뿐이다.</b> 수요일에 먼저 나오고, '
             '목요일에 <b>승인 도장과 확정 원고로 한 번 더</b> 찍힌다('
             '<code>build_brief.py</code> 가 수·목 양쪽에서 돈다). '
             'PDF 와 같은 이름의 HTML 이 함께 나온다.</p>')
    H.append('<table><tr><th>절</th><th>무엇이 실리나</th><th>왜 여기 있나</th></tr>'
             '<tr><td class="k">0. 승인</td><td>승인 상태 · 승인 시각·승인자, 또는 '
             '<b>「아직 승인되지 않았습니다」</b> 안내</td><td>문서를 열자마자 <b>지금 뭘 해야 하는지</b>가 보인다</td></tr>'
             '<tr><td class="k">1. 기획</td><td><b>이번 회차는 무엇에 대한 회차인가</b> 한 줄</td>'
             '<td>「AI 사례 두 개 소개」가 아니라 <b>부서장이 하나 가져갈 생각</b></td></tr>'
             '<tr><td class="k">2. 한 쌍</td><td>분석·생성 각 1건 — 제목·채널·조회수·길이 · '
             '<b>왜 이걸 골랐나</b> · <b>우리 팀 어디에 쓰나</b> · <b>재생 구간</b> · 제친 후보 2건</td>'
             '<td>고른 이유와 <b>버린 이유</b>가 같이 있어야 기획이 있었다는 증거가 된다</td></tr>'
             '<tr><td class="k">3. T1 원고</td><td>사례마다 제목 · 무엇을 · <b>진행 과정 단계</b> · 재생 구간</td>'
             '<td>덱에 그대로 실릴 문장 — <b>여기서 읽고 고친다</b></td></tr>'
             '<tr><td class="k">4. T2 원고</td><td>툰 12장의 제목·말풍선·막·<b>T1 단계</b> 대응표.'
             '<br><b>대본이 있을 때만 그린다</b> — 없으면 안내 문구</td>'
             '<td>툰 다섯 장이 T1 다섯 단계를 하나씩 받는다 — <b>그 대조를 여기서 한다</b></td></tr>'
             '<tr><td class="k">5. 체크리스트</td><td>게시 전 확인 9항목 + <b>고치는 파일 표</b></td>'
             '<td><b>기계가 안 막는 것들의 유일한 그물</b></td></tr></table>')
    H.append('<h3>§5 체크리스트가 실제로 묻는 것</h3>'
             '<table><tr><th>항목</th><th>왜</th></tr>'
             '<tr><td><b>단계가 영상에 실제로 있는가</b></td><td>그럴듯하지만 영상이 안 한 일이면 '
             '<b>발표자가 그 자리에서 막힌다</b></td></tr>'
             '<tr><td><b>우리 데이터가 실명으로 새지 않았는가</b></td><td>센터명·매출액·학생수는 원고에 '
             '들어가면 안 된다(「센터별 실적표」처럼 <b>종류만</b>)</td></tr>'
             '<tr><td><b>부서장이 아는 말인가</b></td><td>API·크롤링·파이프라인이 남아 있으면 안 된다</td></tr>'
             '<tr><td><b>13분에 들어가는가</b></td><td>단계가 5개를 넘으면 <b>질의응답 10분이 깎인다</b></td></tr>'
             '<tr><td><b>재생 구간이 맞는가</b></td><td>LLM 이 <b>챕터만 보고</b> 골랐다 — 실제로 틀어 본다</td></tr>'
             '<tr><td><b>채용·구인·이직·인사 대목이 없는가</b></td><td>영상에 나왔어도 뺀다 — '
             '사내에서는 <b>인사 신호로 읽힌다</b></td></tr>'
             '<tr><td><b>툰 마지막이 댓글 유도 장인가</b></td><td><b>코드가 안 붙인다</b> — '
             '초안을 다시 뽑았으면 빠져 있다</td></tr>'
             '<tr><td><b>툰 다섯 장이 T1 단계와 맞는가</b></td><td>번호만 맞고 <b>문장이 다른 단계</b>인 경우가 '
             '두 회차 연속 있었다</td></tr></table>')
    H.append('<div class="warn"><b>⚠️ 기획서는 초안이다.</b> LLM 은 <b>영상 제목·챕터·설명만</b> 보고 썼다 — '
             '우리 팀 실제 사정은 모른다. 고치는 자리는 문서가 아니라 <b>대본 파일</b>이고, '
             '고친 뒤 다시 돌리면 <b>고친 내용이 유지된다</b>(<code>--reset</code> 해야 초안 복귀).</div>')
    H.append('<div class="warn"><b>⚠️ 기획서가 곧 「추천」이다.</b> 「추천 → 기획서」 순서가 아니다 — '
             '<code>build_brief.py</code> 가 <code>session()</code> 을 불러 <b>기획하면서 한 쌍을 고르고</b> '
             '그 자리서 기획서를 낸다. 소재추천 페이지는 <b>그 결과를 받아 뒤에</b> 그려진다.</div>')

    H.append('<h2 id="s6">6. 승인과 알림 — 배치가 사람에게 닿는 유일한 길</h2>')
    H.append('''<div class="warn"><b>⚠️ 왜 슬랙이어야 했나.</b> <code>say.py</code> 가 「승인.bat 을 누르세요」를
      화면에 찍지만, 스케줄러가 <code>run_hidden.vbs</code> 로 <b>창 없이</b> 돌리며 stdout 을
      <code>out/logs/console_*.out</code> 로 흘리기 때문에 <b>그 문장을 아무도 못 본다.</b>
      승인이 없으면 목요일 배치는 조용히 끝나므로, 수요일을 놓치면 <b>그 주가 통째로 빈다.</b></div>''')
    H.append('''<table><tr><th>언제</th><th>명령</th><th>내용</th></tr>
      <tr><td>수 배치 끝</td><td class="k">notify.py approve</td><td>회차·기획 한 줄·고른 두 건(제목·채널·링크)·「우리 팀」·기획서 경로·승인 방법</td></tr>
      <tr><td>단계 실패</td><td class="k">notify.py fail</td><td>collect · build_brief · build_page 실패 + 종료코드</td></tr>
      <tr><td>목 배치 끝</td><td class="k">notify.py done</td><td>덱 완성 + 「툰은 아직 사람 몫」</td></tr></table>
      <p>자격은 <code>test/.env</code> 의 <code>SLACK_WEBHOOK_URL</code>.
      <b>AX 전용 채널로 옮기려면 웹훅을 새로 발급해 <code>AX_SLACK_WEBHOOK_URL</code> 에 넣으면 된다</b> — 코드는 안 고쳐도 된다.</p>
      <p style="font-size:12.5px;color:#4a5763">알림 실패는 배치를 죽이지 않는다(경고만). <code>--dry-run</code> 으로 본문만 볼 수 있다.</p>''')

    # 6
    # 7 — T1 덱
    H.append('<h2 id="s7">7. T1 부서장회의 덱 — 7장</h2>')
    H.append('<p>1280×720 무대 · 클릭과 ←→ 로 넘김 · 폰트 내장 · <b>HTML 한 파일</b>. '
             '월요일 30분 세션에서 <b>사례 공유 13분</b>에 쓴다.</p>')
    H.append('<table><tr><th>장</th><th>무엇</th><th>회차마다 바뀌나</th><th>고치는 자리</th></tr>'
             '<tr><td class="n">1</td><td>표지 — 회차·주차·이번 회차 한 줄</td><td>날짜·주차만</td>'
             '<td class="k">자동</td></tr>'
             '<tr><td class="n"><b>2</b></td><td><b>현황 지도</b> — 업무 자동화가 모이는 네 덩어리 + 공개 조사 수치</td>'
             '<td><b>고정</b></td><td class="k">build_t1.NET_HUBS</td></tr>'
             '<tr><td class="n">3</td><td>두 사례 요약 — 썸네일 둘을 나란히</td><td>매주</td>'
             '<td class="k">T1_대본.json</td></tr>'
             '<tr><td class="n">4</td><td><b>① 분석 사례</b> — 썸네일 + 진행 과정</td><td>매주</td>'
             '<td class="k">T1_대본.json</td></tr>'
             '<tr><td class="n">5</td><td><b>② 생성 사례</b> — 썸네일 + 진행 과정</td><td>매주</td>'
             '<td class="k">T1_대본.json</td></tr>'
             '<tr><td class="n"><b>6</b></td><td><b>4주 로테이션</b> — 오늘이 몇 주차인지</td>'
             '<td><b>고정</b>(표시만 이동)</td><td class="k">build_page.SLOTS</td></tr>'
             '<tr><td class="n"><b>7</b></td><td><b>AX 확산 전략</b> — 전술 7개를 한 줄씩(하는 일 + 얻는 것 + 주기)</td>'
             '<td><b>고정</b></td><td class="k">build_t1.TACTICS</td></tr></table>')
    H.append('<div class="warn"><b>⚠️ 고정 3장은 대본이 아니다.</b> 2·6·7쪽은 '
             '<code>T1_대본.json</code> 을 아무리 고쳐도 안 바뀐다 — 코드 상수다. '
             '이걸 모르면 「고쳤는데 반영이 안 된다」로 한참 헤맨다.<br>'
             '⚠️ <b>7쪽은 <code>docs/AX확산</code> 전술표의 수기 사본</b>이라 자동 동기화가 없다. '
             '계획서에서 주기를 고치고 상수를 안 고치면 <b>부서장이 옛 주기를 듣고 간다.</b></div>')
    H.append('<h3>사례 장이 담는 것 — <code>T1_대본.json</code> 한 축의 구조</h3>'
             '<table><tr><th>키</th><th>무엇</th></tr>'
             '<tr><td class="k">제목</td><td>그 사례를 <b>우리 업무 말로</b> 부른 이름</td></tr>'
             '<tr><td class="k">무엇을</td><td>한 줄 설명 — 무엇을 주면 무엇이 나오나</td></tr>'
             '<tr><td class="k">단계</td><td><b>진행 과정</b>(보통 5개). 툰 본문 다섯 장이 이걸 하나씩 받는다</td></tr>'
             '<tr><td class="k">재생</td><td>세션에서 <b>틀 유튜브 구간</b> — 시작·끝·라벨·출처</td></tr>'
             '<tr><td class="k">도형</td><td>진행 과정 그림 — <b>「지도」로 고정</b>했다(LLM 이 못 고르게)</td></tr>'
             '<tr><td class="k">중심</td><td>지도 한가운데 놓을 것의 이름</td></tr></table>')
    H.append('<div class="warn"><b>⚠️ 영상은 mp4 가 아니라 「유튜브 시작점 링크」로 튼다.</b> '
             '사례 장마다 <b>「▶ 10:17 부터 유튜브에서 열기」</b> 가 붙고 새 탭에서 그 지점부터 재생된다 — '
             '<code>file://</code> 에서도 산다. 구간을 480p 로 받아 자르는 방식은 <b>화질이 두 번 깎여</b> '
             '하루 만에 폐기했다(<code>clip.py</code> 는 배치에서 빠졌고 덱은 <code>파일</code> 필드를 무시한다).<br>'
             '⚠️ <b>재생 구간 우선순위는 「이번 회차 지정 &gt; 지난 회차 지정 &gt; LLM 제안」</b>이다. '
             '이 순서가 없으면 <code>--reset</code> 할 때마다 <b>손으로 고친 구간이 지난 회차 값으로 되돌아간다.</b><br>'
             '⚠️ <b>구간이 정해지면 T1 단계·T2 원고가 그 구간에 맞춰진다</b> — 세션에서 트는 건 그 대목뿐인데 '
             '원고가 딴 데를 설명하면 <b>화면과 말이 어긋난다.</b></div>')
    H.append('<div class="warn"><b>⚠️ 이 덱은 초안이지 발표본이 아니다.</b> '
             '유튜브 제목·설명이 그대로 실린 자리가 있다. 그대로 띄우면 그 주 세션이 '
             '<b>「남의 채널 소개」</b>가 된다. <b>사람이 우리 업무 말로 바꾸는 것까지가 한 세트다.</b><br>'
             '⚠️ <b>4주차에는 이 덱을 만들지 않는다</b> — 사내 소재 주간이다.</div>')
    H.append('<p style="font-size:12.5px;color:#4a5763">덱을 로컬 서버로 열려면 회차 폴더의 '
             '<code>열기.bat</code>(<code>serve_deck.py</code>) — <code>file://</code> 로 열면 '
             '유튜브 임베드가 오류 153 을 낸다.</p>')

    H.append('<h2 id="s8">8. T2 인스타툰 — 어디까지가 기계인가</h2>')
    H.append('''<div class="lane toon"><div class="t">■ 배치 밖 · 반자동 (2026-09-10 GPT 이관)</div><div class="b">
      <table><tr><th>단계</th><th>누가</th><th>산출</th></tr>
      <tr><td>원고·연출·장별 프롬프트</td><td>기계 <code>build_toon_prompt.py</code> <span class="badge llm">LLM ③</span></td>
          <td class="k">toon/&lt;축&gt;/01~12.txt · 첨부물/</td></tr>
      <tr><td><b>그림 12장 × 2축 = 24장</b></td><td><b>사람 × ChatGPT</b> <span class="badge man">수작업</span></td>
          <td class="k">toon/&lt;축&gt;/받은/*.png</td></tr>
      <tr><td>이름 규약 · 1:1·1080px 검사 · 뷰어 · PDF</td><td>기계 <code>collect_toon.py</code></td>
          <td class="k">T2_정보채널_&lt;축&gt;_&lt;회차&gt;.png / .html / .pdf</td></tr>
      <tr><td>사내 채널 게시</td><td><b>사람</b> <span class="badge man">A3</span></td><td>—</td></tr></table>
      <p><b>경계는 <code>toon/&lt;축&gt;/받은/</code> 이다.</b> <code>toon/생성</code> 은 「생성 단계」가 아니라
      <b>생성축 폴더</b>다(옆의 <code>toon/분석</code> 과 한 쌍).</p></div></div>''')
    H.append('<div class="warn"><b>⚠️ 기계가 안 막는 것 둘 — 승인 전 체크리스트가 유일한 그물이다.</b> '
             '① 마지막 <b>댓글 유도 장</b>(초안엔 없다) ② 원고에 <b>채용·인사 대목</b>이 없는지.<br>'
             '<b>툰 세 번째 막은 「주의사항 안내」로 고정</b> — 3주차 잠금을 푼 대가를 메우는 장치라, 비어 가면 잠금을 되돌린다.<br>'
             '<code>collect_toon.py</code> 는 회차 폴더 PNG 를 <b>덮어쓴다</b> — 시험은 빈 회차나 복사본에서.</div>')

    # 7
    H.append('<h2 id="s9">9. 산출물 — out/&lt;회차&gt;/</h2>')
    H.append('''<table><tr><th>파일</th><th>무엇</th></tr>
      <tr><td class="k">기획서_&lt;회차&gt;.pdf</td><td><b>관리자가 읽고 승인하는 자리</b> (수요일에 먼저 나온다)</td></tr>
      <tr><td class="k">T1_부서장회의_….html</td><td>덱 <b>7장</b> · 고정 3장(2쪽 현황 지도 · 6쪽 4주 로테이션 · 7쪽 전술표)</td></tr>
      <tr><td class="k">T2_정보채널_&lt;축&gt;_….png</td><td><b>게시물</b> 12장 × 2축 / <code>.html</code>=뷰어(게시 금지) / <code>.pdf</code>=보관</td></tr>
      <tr><td class="k">T1_대본.json</td><td><b>사람이 고치는 자리</b> — 고치고 다시 돌리면 유지된다(<code>--reset</code> 해야 초안 복귀)</td></tr>
      <tr><td class="k">llm/</td><td>원고 캐시 — <b>프롬프트 해시</b>로 문다</td></tr>
      <tr><td class="k">승인.json · 승인.bat</td><td>승인 기록 / 사람이 더블클릭하는 파일(<b>여기만 <code>pause</code> 허용</b>)</td></tr>
      <tr><td class="k">열기.bat</td><td>덱을 로컬 서버로 연다(유튜브 오류 153 회피)</td></tr></table>''')
    H.append('<div class="warn"><b>⚠️ 고정 장 2·6·7쪽은 <code>T1_대본.json</code> 이 아니다.</b> '
             '<code>build_t1.py</code> 의 <code>NET_HUBS</code>·<code>TACTICS</code> 상수다 — '
             '대본을 아무리 고쳐도 안 바뀐다.</div>')

    # 8
    H.append('<h2 id="s10">10. 현재 상태</h2>')
    H.append(f'''<table><tr><th>항목</th><th>값</th></tr>
      <tr><td>소재 원장</td><td class="n">{n_all}건 (게재 가능 {n_keep} · 미분류 {n_unk})</td></tr>
      <tr><td>축별 남은 후보</td><td class="n">{" · ".join(f"{ax} {v}" for ax, v in by_ax.items())}</td></tr>
      <tr><td>기사용 제외</td><td class="n">{n_used}건</td></tr>
      <tr><td>회차 수</td><td class="n">{len(rs)}개</td></tr></table>''')
    if rs:
        H.append('<table><tr><th>회차</th><th>승인</th><th>T1 덱</th><th>T2 PNG</th></tr>' + "".join(
            f'<tr><td class="k">{n}</td><td>{"✅" if a else "—"}</td>'
            f'<td>{"✅" if t else "—"}</td><td class="n">{p or "—"}</td></tr>' for n, a, t, p in rs) + '</table>')
    try:
        import refill as RF
        st = RF.stock()
        H.append(f"""<h3>재고 수위 — 마르면 스스로 채운다</h3>
      <table><tr><th>축</th><th>사례 재고</th><th>상태</th></tr>""" + "".join(
            f'<tr><td class="k">{ax}</td><td class="n">{n}</td><td>'
            + ('🔴 <b>발동선 이하</b> — 보충이 돈다' if n <= RF.TRIGGER
               else ('🟡 복구 중' if n < RF.RECOVER else '🟢 충분'))
            + '</td></tr>' for ax, n in st.items())
            + f'</table><p style="font-size:12.5px;color:#4a5763">목표 <b>{RF.TARGET}</b>건(3개월분) · '
              f'발동 <b>{RF.TRIGGER}</b>건 이하 → 복구 <b>{RF.RECOVER}</b>건 · '
              f'상한 {RF.MAX_ROUNDS}라운드 · {RF.MAX_SECONDS//60}분 · 잔여 할당량 {int(RF.QUOTA_SHARE*100)}%</p>')
    except Exception as e:
        H.append(f'<p>재고 수위를 못 읽었습니다: {esc(e)}</p>')

    lo = min(by_ax.values()) if by_ax else 0
    if lo < 3:
        H.append(f'<div class="warn"><b>⚠️ 축 하나의 남은 후보가 {lo}건이다 — 그 축의 세션이 반쪽이 된다.</b> '
                 f'시드 채널부터 보강한다.</div>')
    else:
        H.append('<div class="ok">두 축 모두 재고가 살아 있다.</div>')

    # 9
    H.append('<h2 id="s11">11. 밟으면 조용히 죽는 자리</h2>')
    H.append('''<table><tr><th>무엇</th><th>왜</th></tr>
      <tr><td>스케줄러가 <code>.bat</code> 을 직접 물지 않는다</td><td><code>run_hidden.vbs</code> 경유 — 창 숨김 + <b>콘솔 출력 리다이렉트</b></td></tr>
      <tr><td><b>진짜 방어막은 창 숨김이 아니라 리다이렉트</b></td><td>이 PC 는 QuickEdit 가 전역이라 콘솔이 뜨면 <b>클릭 한 번에 배치가 멈춘다</b></td></tr>
      <tr><td>배치에 <code>pause</code>·<code>timeout</code> 금지</td><td>숨긴 콘솔도 stdin 은 살아 있어 무한대기가 된다</td></tr>
      <tr><td><b>.bat 은 ASCII 전용</b></td><td>한글 안내는 전부 <code>tools/say.py</code>. <code>self_test</code> 가 감시한다</td></tr>
      <tr><td>작업 디렉터리 끝 백슬래시 금지</td><td><code>0x8007010B</code> 로 즉시 실패</td></tr>
      <tr><td><b>배치에 경로를 써넣을 때 <code>\\n</code>·<code>\\a</code>·<code>\\b</code></b></td>
          <td>2026-09-11 에 <code>tools\\notify.py</code> 의 <code>\\n</code> 이 줄바꿈으로 바뀌어
              <code>'otify.py' is not recognized</code> 가 났다. 고친 뒤 <code>run_plan.bat rebuild</code> 로 확인한다</td></tr>
      <tr><td>할당량 리셋 <b>16~17시</b></td><td>수 09:40 은 리셋 전 — 전날 저녁 수동 검색이 많으면 <code>quotaExceeded</code></td></tr>
      <tr><td><b>발행 경로 slug 을 바꾸면 안 된다</b></td>
          <td><code>config/publish.json</code> 에 고정. 바꾸면 이미 나눠 준 링크가 전부 죽고,
              <b>옛 경로는 원격에 그대로 남아 계속 서비스된다</b>(발행기는 지우지 않는다)</td></tr>
      <tr><td><b>T2 는 뷰어 HTML 만 올리면 빈칸</b></td>
          <td>뷰어는 2.6KB 껍데기고 실물은 슬라이드 이미지다. <code>publish.py</code> 가
              PNG 를 1080 JPEG 로 바꿔 함께 올리고 <code>src</code> 도 같이 고친다
              (원본 2048 PNG 는 로컬에 남아 인스타 게시에 쓴다)</td></tr>
      <tr><td><b>발행본은 public 이다</b></td>
          <td>Pages 는 비공개 발행이 안 된다. 가림막은 추측 불가 경로 + <code>noindex</code> 둘뿐이고
              <b>PDF·JPG 에는 메타를 못 넣는다</b> — URL 이 밖으로 나가면 누구나 본다</td></tr>
      </table>''')

    # 10
    H.append('<h2 id="s12">12. 정본과 동기화</h2>')
    H.append('''<table><tr><th>무엇</th><th>정본</th></tr>
      <tr><td>시드 채널 · 수집 게이트</td><td class="k">AX_source/docs/AX확산/02_확산_워크플로우.md §7.0</td></tr>
      <tr><td>전술 · 주기</td><td class="k">AX_source/docs/AX확산/00_AX확산_계획.md → build_t1.TACTICS</td></tr>
      <tr><td>4주 로테이션 슬롯</td><td class="k">build_page.SLOTS</td></tr>
      <tr><td>그림 프롬프트</td><td class="k">config/인스타툰_마스터.md</td></tr>
      <tr><td><b>판정 기준</b>(사례인가·축·재현성)</td><td class="k">config/LLM_컨셉.md 「판정 기준」 절 — <b>심사와 기획이 같은 문장을 읽는다</b></td></tr>
      <tr><td>LLM 컨셉 · 소재 금지</td><td class="k">config/LLM_컨셉.md</td></tr>
      <tr><td>이 폴더 전체</td><td class="k">AX_source/README.md</td></tr></table>''')
    H.append('<div class="warn"><b>⚠️ 기준 문서(<code>docs/AX확산/</code>)와 코드 사본은 짝이다 — 한쪽만 고치면 에러가 안 나서 모른다.</b> '
             '2026-09-11 점검에서 6종이 어긋나 있었다(덱 장수 · 배치 요일 · T2 제작 주체 · 3주차 슬롯 · '
             '사내 전용 자리 수 · 문서 버전). <b>기준은 docs/AX확산 을 먼저 고치고 코드를 맞춘다.</b> '
             '(옛 <code>test/AX_Adoption</code> 폴더는 2026-10-12 에 여기로 흡수·삭제)</div>')
    H.append(f'''<h3>이 문서가 낡으면 기계가 잡는다</h3>
      <p>아래 <b>{len(WATCH)}개 원천 파일</b>의 해시를 문서에 박아 둔다. 하나라도 바뀌면
      <code>self_test.py</code> 가 <b>FAIL</b> 을 내고, 그때 <code>python tools/sysdoc.py</code> 를 다시 돌린다.</p>
      <p style="font-size:12px;color:#4a5763">{" · ".join(f"<code>{esc(w)}</code>" for w in WATCH)}</p>
      <div class="warn"><b>⚠️ 스탬프는 「바뀌었다」만 알려준다.</b> 숫자는 다시 만들면 맞지만
      <b>서술이 실제로 맞는지는 사람이 읽어야 한다.</b></div>''')

    H.append(f'<div class="ft">AX_source 시스템정리 {VERSION} · 스탬프 <code>{stamp()}</code> · '
             f'재생성 <code>python tools/sysdoc.py</code> · 정본 <code>AX_source/README.md</code></div>')
    H.append('</div></body></html>')
    return "\n".join(H)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--open", action="store_true")
    p.add_argument("--check", action="store_true", help="낡았는지만 본다 (rc=1 이면 재생성 필요)")
    a = p.parse_args()

    if a.check:
        cur, want = current_stamp_in_doc(), stamp()
        if cur is None:
            print(f"  FAIL {NAME} 이 없다 - python tools/sysdoc.py")
            sys.exit(1)
        if cur != want:
            print(f"  FAIL {NAME} 이 낡았다 ({cur} != {want}) - python tools/sysdoc.py")
            sys.exit(1)
        print(f"  OK   {NAME} 최신 (스탬프 {cur})")
        return

    html = build()
    io.open(OUT, "w", encoding="utf-8").write(html)
    print(f"생성 {OUT}")
    print(f"  스탬프 {stamp()}")
    if a.open:
        webbrowser.open("file:///" + OUT.replace(os.sep, "/"))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
