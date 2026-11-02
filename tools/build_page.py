# -*- coding: utf-8 -*-
"""
AX 소재 추천 페이지 생성기 v2 — 소재풀을 주차별 추천 HTML 한 장으로 만든다.

  python tools/build_page.py                    # 이번 주
  python tools/build_page.py --week 2 --month 9 # 9월 2주차
  python tools/build_page.py --open             # 만들고 브라우저로 연다

산출: 소재추천.html  (폴더 맨 위 · 외부 CDN 의존 0 · 더블클릭으로 열린다)

T1 4주 로테이션 (AX확산 계획(docs/AX확산) v4.2)
  1주 이달의 사례  → **분석 1건 + 생성 1건**   🌐 유튜브
  2주 이달의 사례  → **분석 1건 + 생성 1건**   🌐 유튜브 (+ T5 ②층 레시피 등록)
  3주 삽질·주의    → 🔒 사내 전용 (클리닉·제작 중 실패) — 부정 소재는 수집하지 않는다
  4주 우리 회사 자동화 사례 발표 → 🔒 사내 전용

⚠️ 유튜브가 채우는 건 1~2주차뿐이다. 3·4주차는 이 페이지가 낼 것이 없다.

이 파일이 회차의 **중심**이다 — 다른 도구가 다 여기를 거친다.
  · `session()`   그 회차 한 벌(기획·한 쌍·자료 전문). T1·T2·기획서가 같은 쌍을 보게 하는 단일 지점.
  · `round_day()` 회차 = **그 주 수요일**. 한 회차가 수(기획)·목(제작) 이틀에 걸치기 때문이다.
  · `approval()`  승인 기록. 목요일 배치가 이걸 보고 T1·T2 를 만들지 정한다.
"""
import argparse, csv, io, json, os, re, sys, webbrowser
from datetime import date, datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect as C
import llm as L

# 보는 사람이 매주 더블클릭하는 파일이라 out/pool 안이 아니라 **폴더 맨 위**에 둔다.
OUT = os.path.join(C.ROOT, "소재추천.html")

# 슬롯 = (이름, 유튜브가 채우나, 설명)
#
# ⚠️ **3주차 「삽질·주의」는 2026-09-09 에 폐기됐다** (AX확산 계획(docs/AX확산) v4.4).
#    1·2·3주차가 모두 「이달의 사례」이고 유튜브가 채운다. 사내 전용은 4주차 하나뿐이다.
#    삽질·주의가 하던 일 — 「성공만 보고하면 실적 보고회가 된다」를 막는 장치 — 는
#    **T2 툰의 세 번째 막(주의사항 안내)** 으로 옮겼다. 그 막이 비어 가면 이 결정을 되돌린다.
SLOTS = {
    1: ("이달의 사례", True,
        "분석 1건 + 생성 1건 — 「우리 팀 걸로 하면?」 즉석 가능/불가 판정"),
    2: ("이달의 사례", True,
        "분석 1건 + 생성 1건 — 「우리 팀은 뭐에 쓸까」 각자 1개씩 + T5 ②층 레시피 등록"),
    3: ("이달의 사례", True,
        "분석 1건 + 생성 1건 — 툰 세 번째 막에서 「이건 이렇게 깨진다」까지"),
    # 2026-09-16 사용자 지시로 4주차도 유튜브로 열렸다. 「우리 회사 자동화 사례 발표」는
    # 고정 슬롯이 아니라 **준비된 달의 4주차를 대체하는 회차**다(정의 SSOT =
    # AX_source/docs/AX확산/00_AX확산_계획.md 4주 로테이션 표). 대체하는 달에는 그 주
    # 배치 산출물을 쓰지 않고 다음 회차로 넘긴다 — 배치는 그대로 돈다.
    4: ("이달의 사례", True,
        "분석 1건 + 생성 1건 — 「우리 팀 걸로 하면?」 즉석 가능/불가 판정"),
}

AXIS_DEF = {
    "분석": "있는 데이터에서 <b>몰랐던 관계를 찾았다</b> · 흩어진 데이터를 <b>모아서 정리했다</b>",
    "생성": "없던 <b>산출물·시스템을 자동으로 만들었다</b>",
}

# ── 세션 적합도 ──────────────────────────────────────────────────────
# 조회수만으로 줄 세우면 **도구 강의**가 위로 온다 — 「A to Z」·「활용법 12가지」·
# 「이 영상 하나로 끝내드려요」. 실제로 v1 추천 3건이 전부 그런 종류였고,
# 그래서 「마음에 안 든다」는 말이 나왔다.
#
# 세션에 필요한 건 강의가 아니라 **가져가서 그대로 해볼 수 있는 사례**다.
# 기준은 사용자가 준 레퍼런스 2건이다 — 둘 다 ①실물을 무료로 준다 ②한 사람이
# 자기 업무를 실제로 바꾼 과정을 처음부터 끝까지 보여준다.
#   · 분석 「알아서 웹 데이터 긁어오는 AI 에이전트 **무료로 나눠드려요**」
#   · 생성 「토스 PO 출신 **대표**가 사내 ERP를 **직접 만들고** 거듭난 방법」
# ⚠️ 이 두 건이 각 축 1~2위에 오는지가 이 점수표의 합격 조건이다 (self_test 참조).
GIVEAWAY = ("무료로 나눠", "나눠드려", "공개합니다", "오픈소스", "무료로 배포", "배포합니다",
            "드립니다", "템플릿 드", "제공)")
FIRSTHAND = ("직접 만들", "직접 해", "만들었습니다", "만들어보", "해봤습니다", "써봤습니다",
             "전환기", "구축", "도입", "거듭난", "바꿔버린", "바꾼", "제작기", "돌려보")
REALNAME = ("대표", "님)", "개발자", "창업", "회사가", "팀이")
WORKWORD = ("회사", "사내", "업무", "보고서", "회의", "엑셀", "직장인", "결재", "문서",
            "데이터", "PPT", "슬라이드", "매출", "고객", "공고")
# 도구 강의 어휘 — 세션 소재로 쓰려면 사람이 구간을 골라야 하므로 감점한다
LECTURE = ("A to Z", "하나로 끝", "끝내드려요", "총정리", "활용법", "사용법", "핵심 기능",
           "가이드", "기초", "입문", "정복", "완벽", "업데이트", "가지", "알려드립니다",
           "설명해드려요", "강의")


def fit(r):
    """(점수, 이유 목록) — 왜 이걸 골랐는지 카드에 그대로 적는다."""
    t = r["제목"]
    sc, why = 0, []
    if any(w in t for w in GIVEAWAY):
        sc += 3; why.append("<b>실물을 그 자리서 준다</b> — 무료 공개·배포·템플릿")
    if any(w in t for w in FIRSTHAND):
        sc += 3; why.append("<b>직접 만든 과정</b>을 보여준다 — 기능 소개가 아니다")
    if any(w in t for w in REALNAME):
        sc += 2; why.append("<b>실명·현업 사례</b> — 「누가 했나」가 있다")
    if any(w in t for w in WORKWORD):
        sc += 2; why.append("<b>우리 업무 어휘</b>가 제목에 있다")
    if 600 <= r["_sec"] <= 2700:
        sc += 1; why.append("10~45분 — 세션에서 <b>구간 인용</b>하기 좋다")
    if r["업로드"] >= date.today().replace(year=date.today().year - 1).isoformat():
        sc += 1
    if any(w in t for w in LECTURE):
        sc -= 3; why.append("⚠️ <b>도구 강의 어휘</b> — 사례로 쓰려면 구간을 골라야 한다")
    return sc, why


def load_rows():
    if not os.path.exists(C.POOL_CSV):
        sys.exit("소재풀.csv 가 없습니다. 먼저 `python tools/collect.py` 를 도세요.")
    rows = list(csv.DictReader(io.open(C.POOL_CSV, encoding="utf-8-sig")))
    keep = C.catalog_rows(rows)
    for r in keep:
        r["_views"] = int(r["조회수"] or 0)
        r["_subs"] = int(r["구독자"] or 0)
        r["_sec"] = int(r["길이초"] or 0)
        r["_fit"], r["_why"] = fit(r)
    return rows, keep, len(C.load_exclude())


def pick(rows, axis, n=3):
    c = [r for r in rows if r["축"] == axis]
    c.sort(key=lambda r: (-r["_fit"], -r["_views"]))
    return c[:n]


# ── 회차 ────────────────────────────────────────────────────────────────
# ⚠️ **한 회차가 이틀에 걸쳐 돈다** (2026-09-09~).
#      수요일 09:40  수집 → 기획 → 기획서 PDF   (관리자가 읽는다)
#      목요일 09:40  승인됐으면 → T1 덱 · T2 툰
#    폴더를 `date.today()` 로 잡으면 **수요일 기획과 목요일 산출물이 다른 폴더로 갈린다** —
#    목요일 빌드가 기획을 못 찾아 조용히 새로 기획해 버린다. 그래서 폴더는 날짜가 아니라
#    **그 주 수요일**로 잡는다. 수·목·금·토·일·월·화가 같은 회차를 가리킨다.
ROUND_WEEKDAY = 2          # 0=월 … 2=수


def round_day(d=None):
    """그 날짜가 속한 회차의 기준일(그 주 수요일).

    ⚠️ **환경변수 `AX_ROUND_DAY=YYYYMMDD` 가 있으면 그 회차로 고정된다**(2026-09-16 신설).
       다음 주 회차를 미리 만들 때 쓴다 — 도구마다 `--date` 를 붙이는 대신 여기 한 자리만
       본다(`build_brief`·`build_t1`·`build_page`·`publish` 가 전부 이 함수를 거친다).
       평소에는 비워 둔다. 켜 놓고 잊으면 **다음 주 배치가 지난 회차 폴더에 쓴다.**
    """
    pin = os.environ.get("AX_ROUND_DAY", "").strip()
    if pin:
        return date(int(pin[:4]), int(pin[4:6]), int(pin[6:8]))
    d = d or date.today()
    return d - timedelta(days=(d.weekday() - ROUND_WEEKDAY) % 7)


def out_dir(d=None, make=True):
    """회차 산출물 폴더 out/<그 주 수요일>. 기획·T1·T2·기획서가 다 여기 쌓인다."""
    p = os.path.join(C.ROOT, "out", f"{round_day(d):%Y%m%d}")
    if make: os.makedirs(p, exist_ok=True)
    return p


# ── 승인 ────────────────────────────────────────────────────────────────
def approval_path(d=None):
    return os.path.join(out_dir(d, False), "승인.json")


def approval(d=None):
    """승인 기록 또는 None. 목요일 배치가 이걸 보고 T1·T2 를 만들지 정한다."""
    p = approval_path(d)
    if not os.path.exists(p):
        return None
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return None      # 깨진 파일은 승인으로 치지 않는다 — 애매하면 안 만든다


def used_ids(d=None):
    """**지난 회차에서 실제로 쓴 영상ID** → {영상ID: 회차} (이번 회차는 뺀다).

    「확정」의 기준은 **승인**이다 — `승인.json` 이 있는 회차의 `llm/01_기획.json` 에
    실린 한 쌍만 센다. 기획만 하고 승인을 안 받은 회차는 그 쌍이 세션에 나간 적이
    없으므로 **다시 뽑혀도 된다.**

    ⚠️ 이번 회차 폴더는 반드시 제외한다. 안 그러면 승인 뒤 목요일에 배치를 다시 돌릴 때
       **자기가 고른 쌍을 자기가 빼고** 다른 사례로 갈아치운다 — 덱과 기획서가 어긋난다.
    """
    cur = f"{round_day(d):%Y%m%d}"
    base = os.path.join(C.ROOT, "out")
    out = {}
    if not os.path.isdir(base):
        return out
    for name in sorted(os.listdir(base)):
        if not (len(name) == 8 and name.isdigit()) or name == cur:
            continue
        rd = os.path.join(base, name)
        if not os.path.exists(os.path.join(rd, "승인.json")):
            continue                      # 승인 안 난 회차 = 세션에 안 나갔다
        p = os.path.join(rd, "llm", "01_기획.json")
        if not os.path.exists(p):
            continue
        try:
            plan = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        for ax in C.AXES:
            vid = str(((plan.get(ax) or {}).get("영상ID") or "")).strip()
            if vid:
                out.setdefault(vid, name)
    return out


def t1_path(d=None):
    # ⚠️ 파일명도 **회차일**로 쓴다. today() 로 쓰면 목요일 산출물만 이름이 하루 밀려
    #    같은 폴더 안에서 기획서·덱·툰의 날짜가 서로 다르게 찍힌다.
    r = round_day(d)
    return os.path.join(out_dir(d, False), f"T1_부서장회의_{r:%Y%m%d}.html")


def t2_path(d=None, ax="분석"):
    """T2 는 축마다 한 장이다 — 분석 만드는 법 / 생성 만드는 법 (2026-09-08~).

    ⚠️ 예전에는 두 축을 한 장에 섞었다. 파일명이 바뀌었으므로 옛 회차 폴더에는
       `T2_정보채널_<날짜>.png` 가 남아 있다 — 칩은 새 이름만 찾는다.
       2026-09-08 v2 부터 축마다 **캐러셀 8장**이고, 이 경로가 그 **1장(표지)**이다.
       2장부터는 같은 이름에 `_02` ~ 가 붙는다 — 칩은 뷰어를 연다.
    """
    r = round_day(d)
    return os.path.join(out_dir(d, False), f"T2_정보채널_{ax}_{r:%Y%m%d}.png")


def llm_dir(d=None):
    return os.path.join(out_dir(d), "llm")


def detail_path(d=None):
    """고른 두 건의 **설명 전문**. 원장의 설명은 300자로 잘려 있어 원고 근거로 얕다."""
    return os.path.join(llm_dir(d), "00_자료전문.json")


def load_detail(picks, d=None):
    """한 쌍의 설명 전문을 받아 캐시한다. 실패하면 빈 dict (원고는 잘린 설명으로 간다).

    ⚠️ **캐시가 이번 쌍을 덮는지 확인하고 쓴다.** `--llm-refresh` 로 기획을 다시 돌리면
       한 쌍이 바뀌는데(실제로 바뀐다), 파일 이름은 그대로라 그냥 읽으면 **지난 쌍의
       설명으로 이번 원고를 쓴다** — 에러 없이 엉뚱한 근거가 실린다.
    """
    vids = [picks[ax][0]["영상ID"] for ax in C.AXES if picks.get(ax)]
    p = detail_path(d)
    if os.path.exists(p):
        try:
            got = json.load(io.open(p, encoding="utf-8"))
            if all(v in got for v in vids):
                return got
            print("  [자료] 캐시가 이번 쌍과 다릅니다 — 다시 받습니다")
        except Exception:
            pass
    got = C.fetch_details(vids)
    if got:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        io.open(p, "w", encoding="utf-8").write(json.dumps(got, ensure_ascii=False, indent=2))
        print(f"  [자료] 설명 전문 {len(got)}건 재취득 (1 unit) — {os.path.basename(p)}")
    return got


def past_rounds(limit=12):
    """`out/` 를 훑어 회차 목록을 만든다. 최신순 [(회차일, 기획 dict or None, 링크 dict)].

    ⚠️ **LLM 도입(2026-09-09) 전 회차에는 기획 기록이 없다** — `out/20260908` 이 그렇다.
       기획을 못 읽어도 목록에서 빼지 않는다. 산출물은 남아 있어서 링크는 살아 있고,
       빼 버리면 「그 주는 아무것도 안 했나」로 읽힌다.
    """
    root = os.path.join(C.ROOT, "out")
    out = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root), reverse=True):
        if not (len(name) == 8 and name.isdigit()):
            continue
        try:
            d = date(int(name[:4]), int(name[4:6]), int(name[6:]))
        except ValueError:
            continue
        plan = None
        pp = os.path.join(root, name, "llm", "01_기획.json")
        if os.path.exists(pp):
            try:
                plan = json.load(io.open(pp, encoding="utf-8"))
            except Exception:
                plan = None
        # 사례 없는 회차(체험 등)는 기획 대신 회차유형을 싣는다 — 없으면 화면이
        # 「기획 기록이 없는 회차」로 읽혀 **아무것도 안 한 주**처럼 보인다(2026-09-16).
        tp = os.path.join(root, name, "회차유형.json")
        if os.path.exists(tp):
            try:
                t = json.load(io.open(tp, encoding="utf-8"))
                plan = {"기획": t.get("제목") or t.get("한줄") or "",
                        "카테고리": t.get("카테고리") or "체험",
                        "한줄": t.get("한줄") or "",
                        "링크": [x for x in (t.get("링크") or []) if x.get("url")]}
            except Exception:
                pass
        # ⚠️ 경로를 `t1_path(d)` 로 만들면 **round_day() 가 한 번 더 걸려** 엉뚱한 폴더를 본다.
        #    여기서 d 는 이미 회차 폴더 이름이다. 옛 회차(20260908)는 그 보정 때문에
        #    존재하지 않는 out/20260902 를 보고 「산출물 없음」이 됐다 — 폴더에서 직접 짓는다.
        folder = os.path.join(root, name)
        # ⚠️ 편 이름을 박아 두지 않는다 — **체험 회차는 툰이 「체험」 한 편**이다(2026-09-18).
        #    박아 두면 그 회차 툰 칩이 **조용히 안 걸린다**(화면은 멀쩡하고 칩만 없다).
        cand = {"기획서": f"기획서_{name}.pdf",
                "T1발표": f"T1_부서장회의_{name}.html"}
        import glob as _g
        for v in sorted(_g.glob(os.path.join(folder, f"T2_정보채널_*_{name}.html"))
                        or _g.glob(os.path.join(folder, f"T2_정보채널_*_{name}.png"))):
            cand["T2" + os.path.basename(v)[len("T2_정보채널_"):-len(f"_{name}.html")]] = \
                os.path.basename(v)
        links = {}
        for key, fn in cand.items():
            path = os.path.join(folder, fn)
            if key.startswith("T2") and not os.path.exists(path):
                path = path[:-5] + ".png"      # 뷰어가 없는 옛 회차는 표지 PNG 로
            if os.path.exists(path):
                links[key] = os.path.relpath(path, C.ROOT).replace(chr(92), "/")
        out.append((d, plan, links))
        if len(out) >= limit:
            break
    return out


def brief_path(d=None):
    r = round_day(d)
    return os.path.join(out_dir(d, False), f"기획서_{r:%Y%m%d}.pdf")


def approved_plan(d=None):
    """이 회차가 **승인됐고** 기획 JSON 이 있으면 그 dict, 아니면 None.

    승인은 「이 한 쌍으로 만들어라」는 확정이다 — 그 뒤로 후보 목록이 바뀌었다고
    기획을 다시 돌리면 확정이 조용히 무효가 된다(session() 주석 참조).
    """
    if not approval(d):
        return None
    p = os.path.join(out_dir(d, False), "llm", "01_기획.json")
    if not os.path.exists(p):
        return None
    try:
        v = json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return None
    return v if all((v.get(ax) or {}).get("영상ID") for ax in C.AXES) else None


def _row_from_ledger(all_rows, vid):
    """게재 후보에서 빠진 확정 영상을 원장에서 꺼내 화면용 필드를 채운다."""
    r = next((x for x in all_rows if x.get("영상ID") == vid), None)
    if r is None:
        return None
    r = dict(r)
    r["_views"] = int(r.get("조회수") or 0)
    r["_subs"] = int(r.get("구독자") or 0)
    r["_sec"] = int(r.get("길이초") or 0)
    r["_fit"], r["_why"] = fit(r)
    return r


def session(month=None, week=None):
    """이번 회차 한 벌 — (월, 주차, 슬롯, 슬롯이름, 유튜브가채우나, 설명, 후보, 축별 픽, 선정근거).

    ⚠️ **T1·T2·추천페이지가 같은 쌍을 보게 하는 단일 지점이다.** 각자 고르면
    덱에 실린 사례와 툰의 사례가 조용히 달라진다 — 에러는 안 난다.

    2026-09-09 부터 한 쌍을 **LLM 이 기획한다.** 채널을 훑어 자료를 모아 오는 데까지가
    파이프라인이고, **무엇을 할 회차인지 정하고 한 쌍을 고르는 것부터는 LLM 이 한다.**

    ⚠️ **fit() 은 선택에서 빠졌다.** 처음엔 fit() 상위 8건만 넘겼는데, 그러면 기획이
       아니라 「기계 점수가 좁혀 놓은 것 중 고르기」다 — 낱말 점수가 놓친 사례는 애초에
       후보에 못 든다. 지금은 게재 게이트를 통과한 **전량**을 넘긴다.
       fit() 은 화면 표시(왜 후보에 있나)와 self_test(수집 게이트 감시)로만 남는다.
       성과지수를 v4.2 에서 게이트에서 뺀 것과 같은 판단이다.

    LLM 이 못 돌거나(미설치·타임아웃) 목록에 없는 ID 를 부르면 **fit() 1위로 되돌아간다** —
    chosen 이 None 인 것이 그 표시다.
    """
    # 회차의 월·주차는 **회차 기준일(그 주 수요일)** 에서 낸다. 평소엔 오늘과 같고,
    # AX_ROUND_DAY 로 다음 주 회차를 미리 만들 때만 갈린다.
    today = round_day()
    month = month or today.month
    week = week or week_of(today)
    slot = ((week - 1) % 4) + 1
    slot_name, from_youtube, slot_desc = SLOTS[slot]
    all_rows, rows, n_ex = load_rows()

    # ── 이미 쓴 사례는 다시 안 고른다 (2026-09-11) ───────────────────────
    # 같은 영상을 두 회차에 트는 것은 부서장 입장에서 「또 그 얘기」다.
    # 원장에서 지우지 않고 **후보에서만** 뺀다 — 무엇을 언제 썼는지는 남아야 한다.
    used = used_ids()
    rows = [r for r in rows if r["영상ID"] not in used]
    n_used = len(used)

    picks = {ax: pick(rows, ax, 3) for ax in C.AXES}      # fit() 순 — 되돌아갈 자리

    chosen, detail = None, {}
    # ⚠️ **승인된 회차는 다시 기획하지 않는다** (2026-09-16 사용자 지시).
    #    회차를 미리 만들어 승인까지 끝내 두면(9월 4주차), 그 주 수요일 배치가 `collect.py` 로
    #    후보를 갱신한 순간 프롬프트 해시가 달라져 `llm.ask()` 가 **재기획해 확정 JSON 을
    #    덮어쓰고**, 목요일 `build_t1.load_deck()` 이 **바뀐 축 대본을 초안으로 되돌린다** —
    #    에러 없이 다른 한 쌍이 된다. 그래서 승인 + 기획 JSON 이 있으면 **그 파일이 곧 기획**이다.
    #    다시 기획하고 싶으면 `approve.py --취소` 로 승인을 먼저 물린다.
    pinned = approved_plan()
    if from_youtube and all(picks.values()) and (pinned or L.available()):
        pool = {ax: [r for r in rows if r["축"] == ax] for ax in C.AXES}   # 전량(기사용 제외)
        if pinned:
            # 캐시 JSON 은 LLM **원문**이라 `plan_session()` 이 붙이던 제친후보 `제목` 이 없다 —
            # 그대로 넘기면 기획서가 KeyError 로 죽는다(2026-09-16 재현). 같은 모양으로 맞춘다.
            by_id = {r.get("영상ID"): r for r in all_rows}
            chosen = dict(pinned)
            chosen["제친후보"] = [
                {"영상ID": x["영상ID"], "제목": (by_id[x["영상ID"]].get("제목") or "")[:46],
                 "왜안골랐나": x.get("왜안골랐나") or ""}
                for x in (pinned.get("제친후보") or [])
                if x.get("영상ID") in by_id]
            print("  [기획] 승인된 회차 — 확정 기획을 그대로 씁니다 (llm/01_기획.json · 재기획 안 함)")
        else:
            chosen = L.plan_session(pool, round_label(today), llm_dir())
        if chosen:
            for ax in C.AXES:
                vid = chosen[ax]["영상ID"]
                # 확정 사례가 그 사이 게재 창(6개월)을 벗어나 후보에서 빠질 수 있다 —
                # 그래도 확정은 확정이다. 원장 전체에서 찾아 붙인다.
                top = (next((r for r in pool[ax] if r["영상ID"] == vid), None)
                       or _row_from_ledger(all_rows, vid))
                if top is None:
                    print(f"  [기획] ⚠️ {ax} 확정 영상 {vid} 가 원장에도 없다 — fit() 1위로 되돌린다")
                    continue
                rest = [r for r in picks[ax] if r["영상ID"] != vid][:2]
                picks[ax] = [top] + rest
    if from_youtube and all(picks.values()):
        detail = load_detail(picks)

    return dict(month=month, week=week, label=round_label(today), slot=slot, slot_name=slot_name,
                from_youtube=from_youtube, slot_desc=slot_desc,
                all_rows=all_rows, rows=rows, n_ex=n_ex,
                used=used, n_used=n_used,
                picks=picks, chosen=chosen, detail=detail)


def week_of(d):
    """그 달 며칠이 속한 주차 (1일이 낀 주를 1주차로 센다). 로테이션 슬롯 계산 전용."""
    return (d.day + date(d.year, d.month, 1).weekday() - 1) // 7 + 1


ORD = ["", "첫", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉", "열"]


def ordinal(n):
    """1 → 「첫번째」, 7 → 「일곱번째」, 11 → 「11번째」(watch.js 가 숫자꼴도 읽는다)."""
    return f"{ORD[n]}번째" if 0 < n < len(ORD) else f"{n}번째"


NAMES = os.path.join(C.ROOT, "config", "회차이름.json")


def round_label(d):
    """회차 이름 「N월 M번째」 (2026-09-23 사용자 지시 · 「N월 M주차」 폐기).

    회차 폴더 날짜 = 게시하는 수요일(콘텐츠는 그 전 주에 만든다). N = 그 월,
    M = 같은 월의 앞선 회차 폴더 수 + 1 (특별편 포함 누적).
    ⚠️ **게시 순서가 폴더 날짜와 다르면 `config/회차이름.json` 이 이긴다** — 9월에 체험(09-30 폴더)을
       사례 한 쌍(09-23 폴더)보다 먼저 올려 세번째·네번째가 뒤집혔다. 계산으로는 알 수 없는 사람의 결정이다.
    ⚠️ 수요일 폴더만 센다 — `out/20260908`(화 · 시범 회차)을 세면 9월이 하나씩 밀린다.
    """
    try:
        names = json.load(io.open(NAMES, encoding="utf-8"))
    except Exception:
        names = {}
    if f"{d:%Y%m%d}" in names:
        return names[f"{d:%Y%m%d}"]
    if d.weekday() != ROUND_WEEKDAY:
        return f"{d.month}월 시범 회차"
    root = os.path.join(C.ROOT, "out")
    n = 1
    for name in (os.listdir(root) if os.path.isdir(root) else []):
        if not (len(name) == 8 and name.isdigit()):
            continue
        try:
            x = date(int(name[:4]), int(name[4:6]), int(name[6:]))
        except ValueError:
            continue
        if x < d and x.weekday() == ROUND_WEEKDAY and (x.year, x.month) == (d.year, d.month):
            n += 1
    return f"{d.month}월 {ordinal(n)}"


def esc(t):
    return (t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def human(n):
    if n >= 100_000_000: return f"{n/100_000_000:.1f}억"
    if n >= 10_000: return f"{n/10_000:.1f}만"
    return f"{n:,}"


def dur(sec):
    return f"{sec//60}분 {sec%60:02d}초" if sec >= 60 else f"{sec}초"


CSS = """
:root{
  --bg:#f7f7f5; --card:#fff; --ink:#1a1a18; --dim:#6b6b66; --line:#e3e3de;
  --accent:#3d5a80; --accent-soft:#eaf0f7;
  --ana:#3d5a80; --ana-soft:#eaf0f7; --gen:#6b4f7a; --gen-soft:#f2ecf6;
  --lock:#8a6d3b; --lock-bg:#fdf6e3; --warn:#b8442e;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#16171a; --card:#1e1f23; --ink:#e8e8e4; --dim:#9a9a94; --line:#31333a;
  --accent:#8ab0d9; --accent-soft:#22303f;
  --ana:#8ab0d9; --ana-soft:#22303f; --gen:#c3a2d6; --gen-soft:#2e2637;
  --lock:#d4b062; --lock-bg:#2a2418; --warn:#e08a72;
}}
:root[data-theme="dark"]{
  --bg:#16171a; --card:#1e1f23; --ink:#e8e8e4; --dim:#9a9a94; --line:#31333a;
  --accent:#8ab0d9; --accent-soft:#22303f;
  --ana:#8ab0d9; --ana-soft:#22303f; --gen:#c3a2d6; --gen-soft:#2e2637;
  --lock:#d4b062; --lock-bg:#2a2418; --warn:#e08a72;
}
*{box-sizing:border-box}
/* 회차 필터 */
.rsel{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 12px}
.rbtn{font:inherit;font-size:13px;background:var(--card);color:var(--dim);cursor:pointer;
  border:1.5px solid var(--line);border-radius:999px;padding:7px 14px;display:flex;
  align-items:center;gap:7px}
.rbtn span{font-size:11px;opacity:.65}
.rbtn:hover{border-color:var(--accent);color:var(--ink)}
.rbtn.on{background:var(--accent-soft);border-color:var(--accent);color:var(--accent);font-weight:700}
.rline{font-size:14px;line-height:1.6;margin:6px 0}
.rlinks{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--ink);font:15px/1.65 "Pretendard","Malgun Gothic",
  -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;margin:0;padding:28px 20px 80px}
.wrap{max-width:1100px;margin:0 auto}
h1{font-size:26px;margin:0 0 4px;letter-spacing:-.4px}
h2{font-size:19px;margin:38px 0 12px;letter-spacing:-.3px;
   padding-bottom:7px;border-bottom:2px solid var(--line);scroll-margin-top:14px}
h2:target{border-bottom-color:var(--accent)}
.sub{color:var(--dim);font-size:13px;margin-bottom:22px}
.meta{display:flex;flex-wrap:wrap;gap:8px;margin:16px 0 26px}
.chip{background:var(--card);border:1px solid var(--line);border-radius:999px;
  padding:5px 13px;font-size:12.5px;color:var(--dim)}
.chip b{color:var(--ink)}
/* 칩은 해당 절로 가는 링크다 — 눌러서 갈 수 있다는 걸 색·커서로 알린다 */
a.chip{text-decoration:none;cursor:pointer;transition:border-color .12s,color .12s}
a.chip:hover,a.chip:focus-visible{border-color:var(--accent);color:var(--accent);
  outline:none}
a.chip:hover b,a.chip:focus-visible b{color:var(--accent)}
a.chip::after{content:" ↓";font-size:10.5px;opacity:.55}
.note{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--accent);
  border-radius:6px;padding:12px 15px;margin:14px 0;font-size:13.5px;color:var(--dim)}
.note b,.note strong{color:var(--ink)}
.warn{border-left-color:var(--warn)}
.lock{background:var(--lock-bg);border-left-color:var(--lock)}
.pair{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:16px 0}
@media (max-width:820px){.pair{grid-template-columns:1fr}}
.pick{background:var(--card);border:1px solid var(--line);border-radius:9px;
  padding:19px;position:relative;scroll-margin-top:16px}
/* 머리 칩으로 내려온 카드 — 어디로 왔는지 보이게 한 번 짚어 준다.
   ⚠️ 표시가 없으면 판이 비슷해서 **어느 카드로 온 건지 모른다**(카드 넷이 같은 모양이다) */
.pick:target{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-soft)}
.pick.ana{border-top:3px solid var(--ana)} .pick.gen{border-top:3px solid var(--gen)}
.pick.alt{opacity:.92;padding:15px 17px}
.tag{display:inline-block;font-size:11.5px;font-weight:700;letter-spacing:.3px;
  padding:3px 10px;border-radius:999px;margin-bottom:9px}
.tag.ana{background:var(--ana-soft);color:var(--ana)}
.tag.gen{background:var(--gen-soft);color:var(--gen)}
.pick h4{margin:4px 0 8px;font-size:16.5px;line-height:1.45;letter-spacing:-.2px}
.pick.alt h4{font-size:14.5px}
.pick h4 a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line)}
.pick h4 a:hover{border-bottom-color:var(--accent);color:var(--accent)}
.facts{display:flex;flex-wrap:wrap;gap:6px;margin:9px 0}
.f{font-size:12px;padding:3px 9px;border-radius:4px;background:var(--accent-soft);color:var(--dim)}
.f b{color:var(--ink)}
.why{font-size:13px;color:var(--dim);margin-top:10px;padding-top:9px;border-top:1px dashed var(--line)}
.why b{color:var(--ink)}
.why ul{margin:6px 0 0;padding-left:17px} .why li{margin:2px 0}
table{width:100%;border-collapse:collapse;font-size:13px;background:var(--card);
  border:1px solid var(--line);border-radius:8px;overflow:hidden}
th{background:var(--accent-soft);text-align:left;padding:9px 11px;font-size:12px;
  color:var(--dim);font-weight:600;white-space:nowrap}
td{padding:8px 11px;border-top:1px solid var(--line);vertical-align:top}
td a{color:var(--ink);text-decoration:none}
td a:hover{color:var(--accent);text-decoration:underline}
.num{text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums}
.scroll{overflow-x:auto;-webkit-overflow-scrolling:touch}
/* ⚠️ 「후보 전체」 표의 탭·검색창 CSS 는 2026-09-10 에 지웠다 — 표 자체를 화면에서 뺀 지
   오래고(2026-09-09), 스타일만 남아 있으면 다음 사람이 그 표가 아직 있는 줄 안다.
   되살릴 땐 `table(rows)` 한 줄과 함께 CSS 도 같이 되살린다. */
.foot{margin-top:46px;padding-top:16px;border-top:1px solid var(--line);
  color:var(--dim);font-size:12.5px;line-height:1.8}
code{background:var(--accent-soft);padding:1px 5px;border-radius:3px;font-size:12.5px}
/* 2026-10-28 사용자: 맨 위 교육 진행 버튼 + 4단계 카드(기획 → 사례 → 교육 → 게시글), 처음엔 접힘 */
.topbtn{display:flex;align-items:center;justify-content:space-between;gap:12px;
  background:var(--accent);color:#fff;text-decoration:none;border-radius:12px;
  padding:15px 20px;margin:18px 0 22px;font-weight:700;font-size:16px}
.topbtn span{font-weight:400;font-size:13px;opacity:.9}
.topbtn:hover,.topbtn:focus-visible{filter:brightness(1.08);outline:none}
details.cat{background:var(--card);border:1px solid var(--line);border-radius:12px}
details.cat[open]{border-color:var(--accent)}
details.cat>summary{list-style:none;cursor:pointer;padding:16px 18px;display:flex;
  align-items:center;gap:12px}
details.cat>summary::-webkit-details-marker{display:none}
details.cat>summary::after{content:"▾";margin-left:auto;color:var(--dim);transition:transform .15s}
details.cat[open]>summary::after{transform:rotate(180deg)}
details.cat[open]>summary{border-bottom:1px solid var(--line)}
.cat .no{width:30px;height:30px;border-radius:50%;background:var(--accent);color:#fff;
  display:grid;place-items:center;font-size:14px;font-weight:700;flex:none}
.cat .ct{font-size:17px;font-weight:700}
.cat summary small{color:var(--dim);font-size:13px}
.cbody{padding:4px 18px 20px}
.cbody h2{margin-top:26px}
.arrow{text-align:center;color:var(--dim);font-size:16px;line-height:1;margin:6px 0}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:14px 0}
@media (max-width:820px){.grid2{grid-template-columns:1fr}}
.item{border:1px solid var(--line);border-radius:9px;padding:14px 16px;background:var(--bg)}
.item-top{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px}
.item h4{margin:2px 0 6px;font-size:15.5px;line-height:1.45}
.item h4 a{color:var(--ink);text-decoration:none;border-bottom:1px solid var(--line)}
.item h4 a:hover{color:var(--accent);border-bottom-color:var(--accent)}
.item p{margin:0;font-size:13px;color:var(--dim)}
.lvtag{font-size:11.5px;font-weight:700;padding:3px 10px;border-radius:999px;
  background:var(--accent-soft);color:var(--accent)}
.state{font-size:11.5px;color:var(--dim)}
.state.ok{color:var(--accent);font-weight:700}
.golink{display:inline-block;margin-top:10px;font-size:12.5px;color:var(--accent);
  text-decoration:none;border:1px solid var(--line);border-radius:999px;padding:4px 12px}
.golink:hover{border-color:var(--accent)}
.pbody{margin-top:8px;font-size:13px}
.pbody summary{cursor:pointer;color:var(--accent)}
.ptext{margin-top:8px;color:var(--dim);line-height:1.7}
"""

JS = """
/* 회차 필터 — 버튼과 상자를 data-r 로 짝짓는다.
   2026-10-28: 사례가 ② 카드로 따로 서서, 특별편 회차를 골라도 사례 절을 숨기지 않는다
   (옛 setCaseOnly 삭제 · 「회차 바로 아래 붙어 보여 그 회차 것으로 읽힌다」 문제가 카드 분리로 사라졌다). */
document.querySelectorAll('.rbtn').forEach(function(b){
  b.addEventListener('click', function(){
    var r = this.dataset.r;
    document.querySelectorAll('.rbtn').forEach(function(x){ x.classList.toggle('on', x === b); });
    document.querySelectorAll('.rbox').forEach(function(x){ x.hidden = x.dataset.r !== r; });
  });
});
"""


def nocase_of(plan):
    """회차유형.json 이 있는 회차 = 특별편(2026-09-23 사용자 지시: 교육·체험은 로테이션 밖 특별편)."""
    return bool((plan or {}).get("카테고리"))


# 회차 칩 표시 이름. 키(T2교육 등)는 위 `startswith("T2")` 판정에 쓰이니 화면 글자만 바꾼다.
CHIP_NAME = {"T2교육": "교육-인스타툰"}   # 2026-10-06 사용자


def rounds_section(today):
    """회차 필터 — 지난 회차를 골라 **그 회차의 기획과 산출물**을 본다 (2026-09-09 신설).

    ⚠️ 페이지는 매주 **덮어쓰인다.** 지난 회차를 다시 보려면 이 절밖에 없다 —
       회차 폴더를 직접 뒤지는 것이 원래 방법이었는데, 아무도 안 뒤졌다.
    """
    rounds = past_rounds()
    if not rounds:
        return ""
    try:
        btn_names = json.load(io.open(os.path.join(C.ROOT, "config", "회차버튼이름.json"), encoding="utf-8"))
    except Exception:
        btn_names = {}
    h = ['<h2 id="rounds">회차별 보기</h2>',
         '<div class="sub">지난 회차의 기획과 산출물. 페이지는 매주 덮어쓰이므로 '
         '여기가 <b>지난 회차를 다시 보는 유일한 자리</b>다.</div>',
         '<div class="rsel">']
    for i, (d, plan, links) in enumerate(rounds):
        lab = btn_names.get(f"{d:%Y%m%d}") or (round_label(d) + (' · 특별편' if nocase_of(plan) else ''))
        cur = " on" if d == round_day(today) else ""
        nocase = ' data-nocase="1"' if nocase_of(plan) else ""
        h.append(f'<button class="rbtn{cur}" data-r="{d:%Y%m%d}"{nocase}>{lab}'
                 f'<span>{d:%m-%d}</span></button>')
    h.append("</div>")

    for i, (d, plan, links) in enumerate(rounds):
        show = "" if d == round_day(today) else ' hidden'
        h.append(f'<div class="rbox" data-r="{d:%Y%m%d}"{show}>')
        if plan and plan.get("기획"):
            lab = plan.get("카테고리")
            h.append(f'<div class="note"><b>{"특별편 · " + esc(lab) if lab else "기획"}</b><br>'
                     f'{esc(plan["기획"])}'
                     + (f'<br><span class="small dim">{esc(plan.get("한줄"))}</span>'
                        if lab and plan.get("한줄") else "")
                     + '</div>')
            for ax in C.AXES:
                v = plan.get(ax) or {}
                if v.get("이유"):
                    h.append(f'<div class="rline"><b>{ax}</b> — {esc(v["이유"])}</div>')
        else:
            h.append('<div class="note"><b>기획 기록이 없는 회차입니다.</b> '
                     'LLM 기획을 도입(2026-09-09)하기 전이라 '
                     '<code>llm/01_기획.json</code> 이 없습니다 — 산출물만 남아 있습니다.</div>')
        # 사례 없는 회차(체험 등)는 **자료 하나로 충분하다**(2026-09-16 사용자 지시).
        # 기획서 칩·안내문까지 얹으면 정작 눌러야 할 자료가 그 안에 묻힌다 —
        # 그래서 회차유형의 `링크` **만** 남기고 산출물 칩은 버린다.
        # 사례 회차와 섞일 걱정은 아래 절 제목이 「N월 M주차 한 쌍」이라 사라졌다.
        if plan and plan.get("카테고리"):
            # 체험 회차도 **기획서는 남긴다** — T2 인스타툰 제작이 그 문서에서 나온다
            # (2026-09-16 3차 지시). 사례 회차의 T1·T2 칩만 자리에 없다.
            # ⚠️ **T2 칩도 남긴다**(2026-09-18) — 09-16 에 이 조건을 만들 때는 체험 회차에
            #    툰이 없었다. 지금은 체험 회차도 툰을 한 편 내므로, 버리면 **구워 놓은 툰을
            #    페이지에서 열 자리가 없다.**
            keep = {k: v for k, v in links.items()
                    if k == "기획서" or k.startswith("T2")}
            keep.update({x.get("이름") or "자료": x.get("url")
                         for x in (plan.get("링크") or []) if x.get("url")})
            links = keep
        if links:
            h.append('<div class="rlinks">' + " ".join(
                f'<a class="chip" href="{v}" target="_blank" rel="noopener">{CHIP_NAME.get(k, k)}</a>'
                for k, v in links.items()) + "</div>")
        else:
            h.append('<div class="rline dim">산출물이 없습니다 — '
                     '승인 전이거나 사내 전용 회차입니다.</div>')
        h.append("</div>")
    return "".join(h)


def card(r, cls, label, alt=False, anchor=""):
    """후보 카드 한 장. `anchor` 를 주면 머리 칩이 **이 카드로 바로** 내려온다.

    ⚠️ 앵커 id 는 **ASCII 로 짓는다**(`pick-ana`·`pick-gen`). 한글 id 도 브라우저는 받지만
       href 에서 퍼센트 인코딩돼 링크가 사람 눈에 안 읽히고, 복사해 붙일 때 깨진다.
    """
    why = "".join(f"<li>{w}</li>" for w in r["_why"]) or "<li>기계가 짚은 이유 없음 — 사람이 판단한다</li>"
    return f"""
    <div class="pick {cls}{' alt' if alt else ''}"{f' id="{anchor}"' if anchor else ''}>
      <span class="tag {cls}">{label}</span>
      <h4><a href="{r['링크']}" target="_blank" rel="noopener">{esc(r['제목'])}</a></h4>
      <div class="facts">
        <span class="f">조회 <b>{human(r['_views'])}</b></span>
        <span class="f">구독 <b>{human(r['_subs'])}</b></span>
        <span class="f">길이 <b>{dur(r['_sec'])}</b></span>
        <span class="f">{r['업로드']}</span>
        <span class="f">{esc(r['채널'])}</span>
        <span class="f">지수 {r['성과지수'] or '—'}</span>
      </div>
      <div class="why"><b>왜 이걸 골랐나</b><ul>{why}</ul></div>
    </div>"""


def table(rows):
    tabs = ['<div class="tabs">',
            '<button class="tab" data-ax="*" aria-selected="true">전체 %d</button>' % len(rows)]
    for ax in C.AXES:
        n = sum(1 for r in rows if r["축"] == ax)
        tabs.append('<button class="tab" data-ax="%s">%s %d</button>' % (ax, ax, n))
    tabs.append("</div>")

    h = ['<div class="scroll"><table><thead><tr>'
         '<th>축</th><th class="num">적합</th><th class="num">조회수</th>'
         '<th class="num">구독자</th><th class="num">길이</th><th>업로드</th>'
         '<th>제목</th><th>채널</th></tr></thead><tbody>']
    for r in sorted(rows, key=lambda r: (r["축"], -r["_fit"], -r["_views"])):
        find = (r["제목"] + " " + r["채널"]).lower()
        h.append(
            f'<tr data-ax="{r["축"]}" data-find="{esc(find)}">'
            f'<td>{r["축"]}</td>'
            f'<td class="num">{r["_fit"]}</td>'
            f'<td class="num">{human(r["_views"])}</td>'
            f'<td class="num">{human(r["_subs"])}</td>'
            f'<td class="num">{r["_sec"]//60}분</td>'
            f'<td>{r["업로드"]}</td>'
            f'<td><a href="{r["링크"]}" target="_blank" rel="noopener">{esc(r["제목"])}</a></td>'
            f'<td>{esc(r["채널"])}</td></tr>')
    h.append("</tbody></table></div>")
    return "\n".join(tabs) + "\n" + "\n".join(h)


def load_seed():
    """시드채널.csv (수집이 채운 실제 채널명·구독자) → 없으면 collect.SEED_CHANNELS 로 대체."""
    if os.path.exists(C.SEED_CSV):
        return list(csv.DictReader(io.open(C.SEED_CSV, encoding="utf-8-sig")))
    return [{"채널ID": cid, "별칭": nm, "채널명": nm, "구독자": "", "역할": why,
             "최근확인일": ""} for nm, cid, why in C.SEED_CHANNELS]


def seed_table(all_rows, rows):
    """시드 채널 절 — 「6개」라는 숫자만 있고 그게 어디인지 볼 자리가 없었다.

    품질은 시드 채널 선정이 결정한다(성과지수 게이트를 버렸으므로). 그래서
    **채널별로 이번 회차에 무엇을 몇 건 대 줬는지**를 같이 세운다 —
    게재 0건인 채널이 그 자리에서 드러나야 분기 재점검이 근거를 갖는다.
    """
    seeds = load_seed()
    h = ['<h2 id="seed">시드 채널</h2>',
         '<div class="note"><b>수집은 검색어가 아니라 이 채널들에서만 한다.</b> '
         '성과지수 게이트를 버렸으므로 <b>품질은 이 표가 결정한다</b> — 분기 1회 재점검. '
         '<b>기준 정본은 <code>AX_source/docs/AX확산/02_확산_워크플로우.md §7.0</code></b>이고 '
         '여기는 사본이다. 채널을 갈아끼우려면 그쪽을 먼저 고친다.</div>',
         '<div class="scroll"><table><thead><tr><th>채널</th><th class="num">구독자</th>'
         '<th class="num">원장</th><th class="num">게재</th><th class="num">분석</th>'
         '<th class="num">생성</th><th>넣은 근거</th></tr></thead><tbody>']
    for s in seeds:
        cid = s.get("채널ID", "")
        n_all = sum(1 for r in all_rows if r.get("채널ID") == cid)
        mine = [r for r in rows if r.get("채널ID") == cid]
        n_ax = {ax: sum(1 for r in mine if r["축"] == ax) for ax in C.AXES}
        subs = int(s.get("구독자") or 0)
        name = esc(s.get("채널명") or s.get("별칭", ""))
        url = f"https://www.youtube.com/channel/{cid}"
        warn = ' style="color:var(--warn)"' if not mine else ""
        h.append(
            f'<tr><td><a href="{url}" target="_blank" rel="noopener">{name}</a></td>'
            f'<td class="num">{human(subs) if subs else "—"}</td>'
            f'<td class="num">{n_all}</td>'
            f'<td class="num"{warn}><b>{len(mine)}</b></td>'
            + "".join(f'<td class="num">{n_ax[ax]}</td>' for ax in C.AXES)
            + f'<td>{esc(s.get("역할", ""))}</td></tr>')
    h.append("</tbody></table></div>")

    thin = [ax for ax in C.AXES if sum(1 for r in rows if r["축"] == ax) < 20]
    if thin:
        h.append('<div class="note warn"><b>⚠️ ' + " · ".join(thin) +
                 '축 재고가 얕다.</b> 그 축을 꾸준히 내는 채널이 사실상 한 곳뿐이면 '
                 '<b>그 채널이 쉬는 주에 세션이 반쪽</b>이 된다. '
                 '보강은 위 표에 채널을 더하는 게 아니라 <b>§7.0 표를 먼저 고치는 것</b>부터다.</div>')
    return "\n".join(h)


def _cfg(name):
    try:
        return json.load(io.open(os.path.join(C.ROOT, "config", name), encoding="utf-8"))
    except Exception:
        return {}


def cat_open(n, key, title, desc):
    """4단계 카드 머리 (2026-10-28 사용자). 처음엔 접혀 있다 — `open` 을 붙이지 않는다."""
    return (f'<details class="cat" id="cat-{key}"><summary><span class="no">{n}</span>'
            f'<span class="ct">{title}</span><small>{desc}</small></summary><div class="cbody">')


CAT_CLOSE = '</div></details>'
ARROW = '<div class="arrow" aria-hidden="true">↓</div>'


def edu_section():
    """③ 교육 — `config/교육목록.json` (계획된 과정 이름 · 링크 · 교육내용). 링크가 비면 「준비 중」."""
    h = ['<div class="sub" style="margin:12px 0 0">계획된 교육 과정입니다. starter → basic → advance → master 순서로 이어지며, 각 과정은 1step · 2step 으로 나뉩니다.</div>',
         '<div class="grid2">']
    for e in _cfg("교육목록.json").get("목록", []):
        url = e.get("링크") or ""
        name = esc(e.get("이름", ""))
        h.append('<div class="item"><div class="item-top">'
                 f'<span class="lvtag">{esc(e.get("과정", ""))} · {esc(e.get("구분", ""))}</span>'
                 f'<span class="state{" ok" if url else ""}">{esc(e.get("컨셉", ""))}'
                 f'{"" if url else " · 준비 중"}</span></div>'
                 + (f'<h4><a href="{url}" target="_blank" rel="noopener">{name}</a></h4>' if url
                    else f'<h4>{name}</h4>')
                 + f'<p>{esc(e.get("내용", ""))}</p>'
                 + (f'<a class="golink" href="{url}" target="_blank" rel="noopener">가이드 열기 ↗</a>' if url else "")
                 + '</div>')
    h.append('</div>')
    return "".join(h)


def use_section():
    """⑤ 활용 — `config/교육목록.json` 「활용」 (직무별 활용 자료, 2026-10-28 사용자).

    ⚠️ claude.ai 아티팩트는 비공개다 — 공유받은 사람만 열린다(진행표와 같다).
    """
    h = ['<div class="sub" style="margin:12px 0 0">직무별 Claude Code 활용 자료입니다. '
         '공유받은 계정에서만 열립니다.</div>', '<div class="grid2">']
    for e in _cfg("교육목록.json").get("활용", []):
        url = e.get("링크") or ""
        name = esc(e.get("이름", ""))
        h.append('<div class="item"><div class="item-top">'
                 f'<span class="lvtag">{esc(e.get("대상", ""))}</span>'
                 f'<span class="state{" ok" if url else ""}">{"공유 자료" if url else "준비 중"}</span></div>'
                 + (f'<h4><a href="{url}" target="_blank" rel="noopener">{name}</a></h4>' if url
                    else f'<h4>{name}</h4>')
                 + f'<p>{esc(e.get("내용", ""))}</p>'
                 + (f'<a class="golink" href="{url}" target="_blank" rel="noopener">자료 열기 ↗</a>' if url else "")
                 + '</div>')
    h.append('</div>')
    return "".join(h)


def posts_section():
    """④ 게시글 — 회차 폴더의 `게시판글_YYYYMMDD.txt` + `config/게시글번호.json`(그룹웨어 글 번호).

    번호가 없으면 「게시 전」. 그룹웨어 주소라 사내 로그인해야 열린다.
    """
    nums = _cfg("게시글번호.json")
    fmt = nums.get("주소형식", "")
    btn = _cfg("회차버튼이름.json")
    root = os.path.join(C.ROOT, "out")
    items = []
    for name in sorted(os.listdir(root), reverse=True) if os.path.isdir(root) else []:
        fp = os.path.join(root, name, f"게시판글_{name}.txt")
        if not (len(name) == 8 and name.isdigit() and os.path.exists(fp)):
            continue
        txt = io.open(fp, encoding="utf-8").read()
        title = txt.split("[제목]", 1)[-1].split("[본문]", 1)[0].strip()
        body = txt.split("[본문]", 1)[-1].strip() if "[본문]" in txt else ""
        d = date(int(name[:4]), int(name[4:6]), int(name[6:]))
        lab = btn.get(name) or round_label(d)
        art = nums.get(name)
        url = fmt.replace("{artNo}", art) if (art and fmt) else ""
        items.append('<div class="item"><div class="item-top">'
                     f'<span class="lvtag">{esc(lab)}</span>'
                     f'<span class="state{" ok" if url else ""}">{"게시됨" if url else "게시 전"} · {d:%m-%d}</span></div>'
                     + (f'<h4><a href="{url}" target="_blank" rel="noopener">{esc(title)}</a></h4>' if url
                        else f'<h4>{esc(title)}</h4>')
                     + (f'<details class="pbody"><summary>본문 보기</summary><div class="ptext">'
                        f'{esc(body).replace(chr(10), "<br>")}</div></details>' if body else "")
                     + (f'<a class="golink" href="{url}" target="_blank" rel="noopener">게시판에서 열기 ↗</a>' if url else "")
                     + '</div>')
    if not items:
        return '<div class="note">아직 만든 게시글이 없습니다.</div>'
    return ('<div class="sub" style="margin:12px 0 0">사내 게시판 「AI자동화 공유」에 올린 글입니다. '
            '게시판 링크는 사내 그룹웨어 로그인 후 열립니다.</div>'
            '<div class="grid2">' + "".join(items) + '</div>')


def main():
    a_p = argparse.ArgumentParser()
    a_p.add_argument("--month", type=int, default=date.today().month)
    a_p.add_argument("--week", type=int, default=None)
    a_p.add_argument("--open", action="store_true")
    a_p.add_argument("--no-llm", action="store_true", help="LLM 없이 fit() 점수로만 고른다")
    a_p.add_argument("--llm-refresh", action="store_true", help="LLM 캐시를 버리고 다시 쓴다")
    a = a_p.parse_args()
    L.enable(not a.no_llm, a.llm_refresh)

    # ⚠️ 예전엔 여기서 picks 를 **따로 계산했다.** LLM 이 고르기 시작한 뒤로는 그러면
    #    페이지의 「이번 주 한 쌍」과 T1·T2 의 사례가 갈린다 — session() 하나만 본다.
    ses = session(a.month, a.week)
    # 월·주차는 **session() 이 정한 값**을 쓴다 — a.month 기본값은 「오늘」이라
    # AX_ROUND_DAY 로 다음 주 회차를 만들 때 달이 갈릴 수 있다.
    month, week, slot = ses["month"], ses["week"], ses["slot"]
    slot_name, from_youtube, slot_desc = ses["slot_name"], ses["from_youtube"], ses["slot_desc"]
    all_rows, rows, n_ex = ses["all_rows"], ses["rows"], ses["n_ex"]
    picks, chosen = ses["picks"], ses["chosen"]
    ran = f"{datetime.now():%Y-%m-%d %H:%M}"

    H = ['<!doctype html>', '<html lang="ko"><head>', '<meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width,initial-scale=1">',
         '<meta name="color-scheme" content="light dark">',
         "<title>AX 확산 한눈에 · AX</title>",
         f"<style>{CSS}</style>", '</head><body>', '<div class="wrap">']
    # ⚠️ **상단 메뉴(①②③④)는 2026-09-10 에 걷어냈다.** 「회차별 보기」의 칩
    #    (기획서·T1발표·T2분석·T2생성)이 같은 파일을 열고, **지난 회차까지** 연다 —
    #    메뉴는 이번 회차만 열면서 같은 링크를 한 번 더 그렸다. 되살릴 일 없다.
    # 제목 = 「AX 확산 한눈에」 고정 (2026-10-28 사용자). 회차 이름은 ① 기획 카드에 있다.
    #    파일 이름 `소재추천.html` 은 그대로 — 바꾸면 나눠 준 링크가 죽는다.
    H.append("<h1>AX 확산 한눈에</h1>")
    H.append('<div class="sub">교육 · 사례 · 게시글 · 활용 자료를 한곳에 모았습니다</div>')
    # ⚠️ 후보·축별 건수는 **여기** 있다. 칩이 절 이름으로 바뀌면서(2026-09-10) 숫자가 갈 자리가
    #    없어졌는데, 그렇다고 지우면 「이번 주 재고가 얼마인지」를 볼 데가 사라진다.
    # 소재풀 건수 줄은 ② 사례 카드 안으로 옮겼다 (2026-10-28) — 운영자 정보라 제목 아래에 두지 않는다.
    pool_line = (f'<div class="sub" style="margin:12px 0 0">AX_source 소재풀 → T1 부서장회의 세션 · T2 정보채널'
             f'&nbsp;·&nbsp; 후보 <b>{len(rows)}건</b> (원장 {len(all_rows)}건) · '
             + " · ".join(f'{ax} <b>{sum(1 for r in rows if r["축"]==ax)}</b>' for ax in C.AXES)
             + f'&nbsp;·&nbsp; 만든 때 {ran}</div>')

    # 맨 위 = 교육 진행 버튼 (2026-10-28 사용자: 링크 글자 없이 버튼으로)
    # ⚠️ 진행표는 비공개 아티팩트다 — 공유받은 사람만 열린다.
    prog = _cfg("교육목록.json").get("진행표")
    if prog:
        H.append(f'<a class="topbtn" href="{prog}" target="_blank" rel="noopener">'
                 f'교육 진행 현황<span>팀별 진행표 열기 ↗</span></a>')
    # ⚠️ 머리 칩(한 쌍 · 대안 · 시드 채널 · 4주 로테이션)은 2026-10-28 에 걷어냈다 —
    #    절이 접힌 카드 안으로 들어가 앵커로 내려가도 안 보인다. 4단계 카드가 그 길을 대신한다.
    no_pair = os.path.exists(os.path.join(out_dir(None, False), "회차유형.json"))

    # 회차별 보기 — 「{slot}주차 = 이달의 사례」 안내 줄이 있던 자리다 (2026-09-10 교체).
    #    슬롯 설명은 아래 <4주 로테이션> 표가 이미 같은 말을 하고 있어 중복이었고,
    #    지난 회차를 다시 보는 **유일한 자리**가 페이지 맨 아래라 아무도 안 내려갔다.
    #    (slot_desc 는 session() 이 계속 들고 있다 — T1·T2 가 같은 값을 쓴다.)
    # ① 기획 — 회차별 기획 · 기획서 · T1 · T2 (2026-10-28 사용자: 4단계 카드)
    H.append(cat_open(1, "plan", "기획", "회차별 기획 · 기획서 · T1 발표 · T2 인스타툰"))
    H.append(rounds_section(date.today()).replace('<h2 id="rounds">회차별 보기</h2>', '', 1))
    H.append(CAT_CLOSE + ARROW)
    # ② 사례 — 유튜브 사례 (한 쌍 · 대안 · 시드 채널 · 4주 로테이션, 기존 그대로)
    H.append(cat_open(2, "case", "사례", "유튜브 AI 업무 사례 · 한 쌍 · 대안 · 시드 채널 · 4주 로테이션"))
    H.append(pool_line)

    if not from_youtube:
        H.append('<div class="note lock"><b>🔒 이 회차는 사내 전용이다.</b> '
                 f'{slot_name}는 <b>유튜브로 대체하지 않는다.</b> '
                 '이 자리가 뚫리면 T1은 <b>「AI 뉴스 브리핑」</b>이 되고 확산 기능이 사라진다. '
                 '소재가 없으면 거르는 게 아니라 <b>3주차 포맷을 한 번 더 쓴다.</b><br>'
                 '3주차 소재는 <code>T6 클리닉 로그</code>·제작 중 실패에서, '
                 '4주차 발표 팀은 <code>기록 시트</code>(T3 선물·T7 진단 받은 팀)에서 고른다.</div>')
        H.append("<h2>재고 확인 — 다음 1·2주차용</h2>")
    elif os.path.exists(os.path.join(out_dir(None, False), "회차유형.json")):
        # ⚠️ **체험 회차 주에는 「한 쌍」 절을 만들지 않는다** (2026-09-18 사용자 지적).
        #    이 절은 **이번 회차의 확정 한 쌍**이고, 체험 회차엔 그런 것이 없다. 그런데
        #    전에는 그려 놓고 **JS 로 감추기만** 했다 — 그래서 **다른 회차 버튼을 누르면
        #    다시 나타나면서** 「9월 3주차 한 쌍」이라는 **엉뚱한 제목의 후보 두 건**이 떴다.
        #    (4주차를 보는 중에 3주차 한 쌍이 뜬다. 내용은 그 주 추천 top1 이라 확정도 아니다.)
        #    후보 발굴 기능은 아래 「후보」 절이 그대로 하므로 잃는 것이 없다.
        H.append('<div class="note"><b>이 회차는 체험 회차다.</b> 확정된 <b>한 쌍이 없어</b> '
                 '「한 쌍·대안」 절을 만들지 않는다 — 회차 상자의 자료를 본다. '
                 '소재 후보는 아래 <b>후보</b> 절에 그대로 있다.</div>')
        H.append("<h2>재고 확인 — 다음 회차용</h2>")
    else:
        # ⚠️ 이 상자는 **회차 버튼과 연동돼 숨는다**(JS `setCaseOnly`). 절을 새로
        #    끼울 때 이 <div class="caseonly"> 안/밖을 헷갈리면 조용히 같이 숨는다.
        H.append('<div class="caseonly">')
        H.append(f'<h2 id="pair">{ses["label"]} 한 쌍</h2>')
        H.append('<div class="pair">')
        for ax, cls in (("분석", "ana"), ("생성", "gen")):
            if picks[ax]:
                H.append(card(picks[ax][0], cls, f"① {ax}", anchor=f"pick-{cls}"))
            else:
                H.append(f'<div class="pick {cls}" id="pick-{cls}">'
                         f'<span class="tag {cls}">① {ax}</span>'
                         f'<h4>후보 없음</h4><div class="why">이 축의 재고가 비었다 — '
                         f'<code>collect.py</code> 를 먼저 도세요.</div></div>')
        H.append("</div>")
        if chosen:
            # 왜 이 둘이 올라왔는지 — fit() 점수만 있던 자리엔 「몇 점」밖에 못 적었다.
            # 제친 후보까지 같이 적는다. **무엇을 버렸는지가 기획이 있었다는 증거**다.
            H.append(f'<div class="note"><b>🤖 이번 회차 기획</b><br>{esc(chosen["기획"])}</div>')
            drop = "".join(
                f'<br><span style="opacity:.7">제침 — {esc(d["제목"])} : {esc(d["왜안골랐나"])}</span>'
                for d in chosen.get("제친후보", []))
            H.append('<div class="note"><b>이 한 쌍을 고른 이유</b><br>'
                     + "<br>".join(
                         f'<b>{ax}</b> — {esc(chosen[ax]["이유"])} '
                         f'<span style="opacity:.75">→ 우리 팀: {esc(chosen[ax]["우리팀"])}</span>'
                         for ax in C.AXES)
                     + f'<br><b>둘이 서로 보완하는 것</b> — {esc(chosen["한쌍이유"])}'
                     + drop + '</div>')
        H.append('<div class="note"><b>두 건을 같은 주제로 붙인다.</b> '
                 '「데이터를 모아온다(분석) → 그걸로 보고자료를 만든다(생성)」처럼 한 흐름이어야 '
                 '13분이 하나의 이야기가 된다. 무관한 두 건이면 <b>6분짜리 소개 두 개</b>로 흩어진다.<br>'
                 + " · ".join(f"<b>{ax}</b> = {AXIS_DEF[ax]}" for ax in C.AXES) + "</div>")
        H.append('<div class="note warn"><b>⚠️ 추천은 「후보」이지 완성 카드가 아니다.</b> '
                 '제목이 유튜브 원문 그대로다 — 세션에 걸기 전에 '
                 '<b>우리 업무 말로 바꾸는 것</b>까지가 한 세트다. '
                 '그대로 쓰면 그 주 세션이 <b>「남의 채널 소개」</b>가 된다.</div>')

        H.append('<h2 id="alt">대안</h2>')
        H.append('<div class="pair">')
        for ax, cls in (("분석", "ana"), ("생성", "gen")):
            for i, r in enumerate(picks[ax][1:], 2):
                H.append(card(r, cls, f"{ax} 대안 {i-1}", alt=True))
        H.append("</div>")
        H.append("</div>")          # /caseonly

    # ⚠️ 「후보 전체」 절은 **화면에서만** 뺐다 (2026-09-09, 6번).
    #    `table(rows)`·검색창은 코드에 그대로 남겨 뒀다 — 다시 보고 싶으면 아래 한 줄만 살린다.
    #    재고·경보·self_test 는 이 절과 무관하게 계속 돈다.
    #    H.append('<h2 id="all">후보 전체</h2>' + table(rows))

    # 시드 채널·4주 로테이션도 **사례 회차에만** 뜻이 있다 — 체험 회차 버튼을 누르면 숨는다
    # (2026-09-16 4차 지시). 한 쌍·대안과 같은 class 라 같은 JS 가 같이 토글한다.
    H.append('<div class="caseonly">')
    H.append(seed_table(all_rows, rows))

    H.append('<h2 id="rot">4주 로테이션</h2>')
    H.append('<div class="scroll"><table><thead><tr><th>주차</th><th>포맷</th>'
             '<th>소재</th><th class="num">재고</th></tr></thead><tbody>')
    for s in (1, 2, 3, 4):
        nm, yt, _ = SLOTS[s]
        src = ("🌐 유튜브 — 분석 1 + 생성 1" if yt else "🔒 <b>사내 전용</b>")
        n = f'{min(len(picks["분석"]), len(picks["생성"]))}쌍' if yt else "—"
        mark = " ←" if s == slot else ""
        H.append(f'<tr><td><b>{s}주차{mark}</b></td><td>{nm}</td>'
                 f'<td>{src}</td><td class="num">{n}</td></tr>')
    H.append("</tbody></table></div>")
    H.append("</div>")              # /caseonly (시드 채널 · 4주 로테이션)

    H.append(CAT_CLOSE + ARROW)
    # ③ 교육 · ④ 게시글
    H.append(cat_open(3, "edu", "교육", "계획된 교육 과정 · 이름 · 링크 · 교육내용"))
    H.append(edu_section())
    H.append(CAT_CLOSE + ARROW)
    H.append(cat_open(4, "post", "게시글", "사내 게시판에 올린 회차별 글 · 링크"))
    H.append(posts_section())
    H.append(CAT_CLOSE + ARROW)
    H.append(cat_open(5, "use", "활용", "직무별 Claude Code 활용 자료 · 링크"))
    H.append(use_section())
    H.append(CAT_CLOSE)

    H.append('<div class="foot">')
    H.append(f'<b>게재 기준</b> — 조회 {C.MIN_VIEWS:,}↑ · 길이 {C.MIN_SEC//60}~{C.MAX_SEC//60}분 · '
             f'제목 한글 {C.MIN_HANGUL}자↑ · 부정·광고 제목 제외 · '
             f'시드 채널 {len(C.SEED_CHANNELS)}개 · 수기 제외 {n_ex}건.<br>')
    H.append('<b>⚠️ 성과지수(조회수÷구독자)는 게이트가 아니다</b> — 표기만 남긴다. '
             '레퍼런스 2건이 <b>0.44배 · 1.9배</b>라 어떤 배수 컷을 걸어도 원하는 소재가 안 들어온다. '
             '대신 <b>시드 채널 선정이 품질을 결정한다</b> — 분기 1회 재점검.<br>')
    H.append('<b>⚠️ 부정적 소재는 수집하지 않는다</b> — 3주차 삽질·주의는 '
             '<b>사내(클리닉·제작 중 실패)</b> 소재만 쓴다.<br>')
    H.append('<b>적합</b> 점수 = 실물 배포(+3) · 직접 만든 과정(+3) · 실명 현업(+2) · '
             '우리 업무 어휘(+2) · 10~45분(+1) · 최근 1년(+1) · <b>도구 강의 어휘(−3)</b>.<br>')
    H.append('기준 정본 <code>AX_source/docs/AX확산/02_확산_워크플로우.md §7.0</code> · '
             '생성 <code>python tools/build_page.py</code> · '
             '수집 <code>python tools/collect.py</code> · '
             '축 뒤집기 <code>out/pool/축지정.csv</code>')
    H.append("</div></div>")
    H.append(f"<script>{JS}</script>")
    H.append("</body></html>")

    io.open(OUT, "w", encoding="utf-8").write("\n".join(H) + "\n")
    print(f"생성 {OUT}")
    print(f"  {ses['label']} · 로테이션 {slot}주차 「{slot_name}」 · 후보 {len(rows)}건"
          + (f" · 기사용 제외 {ses['n_used']}건" if ses.get("n_used") else ""))
    if from_youtube:
        for ax in C.AXES:
            top = picks[ax][0]["제목"][:44] if picks[ax] else "(없음)"
            print(f"  {ax} 추천 {len(picks[ax])}건 : {top}")
    else:
        print("  사내 전용 회차 — 유튜브 추천 없음 (재고만 표시)")

    al = C.supply_check(all_rows)
    if al:
        C.report_alerts(al, ran)
    if a.open:
        webbrowser.open("file:///" + OUT.replace("\\", "/"))


if __name__ == "__main__":
    main()
