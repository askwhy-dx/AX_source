# -*- coding: utf-8 -*-
"""
AX_source 소재 축적기 v2 — AX확산 계획(docs/AX확산) T1 1~2주차 「이달의 사례」 소재를 모은다.

v1(~2026-09-07) 과의 차이:
  v1 = 검색어 11종으로 **쇼츠 툴 팁**을 긁었다. 성과지수(조회수÷구독자) 3배 이상만 남겼다.
  v2 = **시드 채널 6개**를 훑어 **분석 / 생성 두 축의 실무 사례**를 쌓는다. 성과지수 게이트는 없다.

왜 바뀌었나 (2026-09-08 실측) — 사용자가 준 레퍼런스 2건이 v1 기준에 **3중으로 걸려 탈락**했다.
  · 생성 레퍼런스 「사내 ERP를 직접 만든 방법」    41분 · 성과지수 1.9배
  · 분석 레퍼런스 「웹 데이터 긁어오는 에이전트」   26분 · 성과지수 **0.44배**
  길이 600초 컷 · 등급 「우수(3배)」 컷 · 툴 how-to 검색어 — 셋 다 통과 못 한다.
  분석 쪽이 0.44배라 컷을 「양호(1배)」로 낮춰도 안 잡힌다. **그래서 성과지수를 게이트에서 뺐다.**
  옛 원장 243건을 다시 재보니 10분 초과 0건 · 60초 이하 149건(61%) 이었다.

기준의 정본은 이 파일이 아니라 `AX_source\\docs\\AX확산\\02_확산_워크플로우.md` §7.0 이다.
거기를 먼저 고치고 여기를 맞춘다.

사용:
    python tools/collect.py                     # 시드 채널 전체 (올해 업로드분)
    python tools/collect.py --ch 빌더 장피엠      # 이름 일부로 채널 고르기
    python tools/collect.py --rebuild           # API 없이 카탈로그만 재생성
    python tools/collect.py --estimate          # 할당량만 계산

산출:
    out/pool/소재풀.csv        누적 원장 (UTF-8 BOM)
    out/pool/소재카탈로그.md    축별 정리본 (사람이 읽는 것)
    out/pool/시드채널.csv      채널 ID 캐시 (한 번 받으면 다시 안 받는다)
    out/pool/수집로그.csv      회차별 실행 기록
"""
import argparse, csv, io, os, re, sys
from datetime import datetime, date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan as S

ROOT = S.ROOT
POOL = os.path.join(ROOT, "out", "pool")
POOL_CSV = os.path.join(POOL, "소재풀.csv")
CATALOG = os.path.join(POOL, "소재카탈로그.md")
RUNLOG = os.path.join(POOL, "수집로그.csv")
SEED_CSV = os.path.join(POOL, "시드채널.csv")
OVERRIDE_CSV = os.path.join(POOL, "축지정.csv")

# ── 시드 채널 ────────────────────────────────────────────────────────
# 정본은 AX_source/docs/AX확산/02_확산_워크플로우.md §7.0 「시드 채널 6개」 표다.
# 채널을 갈아끼우려면 그 표를 먼저 고친다.
#
# ⚠️ 검색이 아니라 채널로 캐는 이유 (2026-09-08 실측 3가지)
#   ① 검색어로는 분석/생성이 안 갈린다 — 축별 검색어 8개를 나눠 돌렸더니
#      상위 22건 중 11건이 같은 영상이었다. 축은 판정 단계에서 갈라야 한다.
#   ② 레퍼런스 2건 모두 특정 채널의 연재물이었다 (한 채널에 분석·생성이 한 쌍).
#   ③ 비용이 1/20 이다 — 검색어 1개 101 units vs 채널 1개 5~6 units.
SEED_CHANNELS = [
    ("빌더 조쉬",   "UCxj3eVTAv9KLdrowXcuCFDQ", "롱폼 기업 인터뷰(HOW I AI) · 생성 레퍼런스 출처"),
    ("장피엠",      "UCSkpTOEl_zW6b4Y7M_Prefg", "「알아서 OO해주는 에이전트」 연재 · 분석 레퍼런스 출처"),
    ("스티브",      "UCDieGYS2T1fy-j9_GZeZeqQ", "자동수집→카톡 발송 구조 · 주식비서 55만"),
    ("루트AI",      "UCDq9_N34UnlMSlFB4kWE15w", "데이터분석·보고서 실습 · 코워크 A to Z 28만"),
    ("에이커",      "UC6PuL8-eXqizOYtvLCK9iJQ", "제미나이+노트북LM PPT 40만 · GEM 업무자동화 31만"),
    ("오빠두엑셀",  "UCZ6UHYBQFBe14WUgxlgmYfg", "회사 서식 그대로 보고서 자동화 30만 · 구독 상한 해제로 편입"),
]

# ── 게재 게이트 ──────────────────────────────────────────────────────
# ⚠️ 성과지수(조회수÷구독자) 는 **게이트가 아니다.** 참고 표기로만 남긴다.
#    레퍼런스가 0.44배 · 1.9배라 어떤 배수 컷을 걸어도 원하는 소재가 안 들어온다.
# ⚠️ 2026-09-11: 30,000 → 5,000 으로 내렸다. **LLM 심사 상시화와 한 벌이다.**
#    3만에서는 중견 실무 채널이 통째로 죽었다 — 어니언 비아이(BI·구독 1만)가 「파워쿼리
#    데이터 전처리 자동화」를 내고도 통과 0건이었다. 발굴 18채널 실측:
#      3만 → 분석 사례 5건 / 1만 → 9건 / **5천 → 13건** / 2천 → 17건 (6개월 기준)
#    유입이 3.4배로 늘지만 그 양은 axis_llm.py 가 받는다. 심사 없이 이 값만 내리면
#    도구 강의가 원장에 쌓인다. 정본은 AX_source/docs/AX확산/02_확산_워크플로우.md §7.0.
MIN_VIEWS = 5_000      # 절대 조회수 하한
MIN_SEC = 300           # 5분  — 그 아래는 사례가 아니라 툴 팁이다
MAX_SEC = 3_600         # 60분 — 그 위는 세션에서 인용하기 어렵다
MIN_HANGUL = 3          # 제목 한글 최소 글자수 (영어권·공장 자동화 영상 차단)

# ⚠️ 수집 창 — 2026-09-11 에 「올해 1월 1일부터」에서 **최근 6개월**로 바꿨다.
#    ① 사용자 기준: **6개월이면 기술 격차**가 생긴다. 작년 것까지 보면 낡은 사례가 섞인다.
#    ② 보충 루프(refill)·채널 실측(find_channels)이 이미 6개월 창을 쓰고 있었다 —
#       시드만 연초부터라 **두 경로의 기준이 달랐다.**
#    ③ 옛 방식(`{올해}-01-01`)은 **연말에 조용히 깨진다** — 1월 1일이 되면 범위가
#       「올해 것」만 남아 신규가 사실상 0이 된다. 이 상수는 그 함정이 없다.
#    ⚠️ 이미 원장에 있는 옛 행은 **지워지지 않는다.** 갱신 대상에서 빠질 뿐이고,
#       재고는 6개월 창으로 따로 세므로(refill.stock) 계산에는 영향이 없다.
FRESH_DAYS = 183        # 수집·재고의 공통 창 (6개월)
_HAN = re.compile("[가-힣]")

# 부정적 소재는 **수집하지 않는다** (2026-09-08 사용자 지시).
# v1 의 C1 「삽질·주의」 카테고리는 폐기했다 — T1 3주차 삽질 소재는 이제 사내
# (T6 클리닉·제작 중 실패)에서만 가져온다. AX확산 계획(docs/AX확산) §7.0.1 잠금 참조.
NEGATIVE = ["실패", "오류", "안되는", "안 되는", "못하는", "거짓말", "환각", "할루시네이션",
            "사기", "주의보", "위험", "논란", "저격", "최악", "망했", "소멸", "일자리",
            "믿으면", "경고", "속지", "당했", "짤린", "대체된다", "끝났다"]
# 광고·부업성 제목도 뺀다 — 세션에서 「제품 광고」로 들리면 그 회차가 죽는다.
PROMO = ["필수템", "언박싱", "협찬", "최저가", "할인", "공동구매", "부업", "수익화",
         "돈 버는", "돈버는", "월 1000", "월천"]

# ── 축 판정 ──────────────────────────────────────────────────────────
# 두 축의 정의는 AX확산 계획(docs/AX확산) 분기말 세션과 **같은 것**을 쓴다.
#   분석 = 있는 데이터에서 몰랐던 관계를 찾았다 · 흩어진 데이터를 모아 정리했다
#   생성 = 없던 산출물·시스템을 자동으로 만들었다
# 제목은 1배, 설명은 0.5배로 센다. 동점이면 「미분류」로 두고 사람이 본다.
ANALYSIS = {"크롤링": 3, "크롤러": 3, "긁어": 3, "수집": 3, "스크래핑": 3,
            "데이터": 2, "엑셀": 2, "스프레드시트": 2, "분석": 2, "모니터링": 2,
            "리서치": 2, "조사": 2, "통계": 2, "대시보드": 2, "VOC": 2,
            "정리": 1, "요약": 1, "검색": 1}
CREATION = {"만들": 3, "만드는": 3, "제작": 3, "구축": 3, "개발": 3, "세팅": 3,
            "시스템": 2, "ERP": 2, "PPT": 2, "슬라이드": 2, "발표자료": 2, "보고서": 2,
            "리포트": 2, "문서": 2, "디자인": 2, "웹사이트": 2, "앱": 2, "로고": 2,
            "사내": 1, "에이전트": 1, "스킬": 1, "워크플로우": 1}
AXES = ("분석", "생성")


def toon_axes(out_d):
    """그 회차 툰의 **편 목록**. 대본에 있는 키 순서를 그대로 쓴다.

    2026-09-18 신설(사용자 지시) — **체험 회차는 툰을 「체험」 한 편만** 만든다.
    소재 축(`AXES`)과 툰의 편은 다른 개념이다. 사례 회차는 분석·생성 두 편이고,
    체험 회차는 체험 한 편이다. 대본이 없으면 `AXES` 로 떨어진다(옛 동작 유지).

    ⚠️ **툴은 이 함수만 본다** — `AXES` 를 직접 돌면 체험 회차에서 「분석축 대본이
       없습니다」를 두 번 찍고 끝난다(실측 전 설계).
    """
    import io as _io, json as _json, os as _os
    p = _os.path.join(out_d, "T2_대본.json")
    if _os.path.exists(p):
        try:
            sc = _json.load(_io.open(p, encoding="utf-8"))
            ks = [k for k, v in sc.items()
                  if isinstance(v, dict) and (v.get("장") or [])]
            if ks:
                return tuple(ks)
        except Exception:
            pass
    return AXES

GRADE_RANK = {"떡상": 0, "우수": 1, "양호": 2, "보통": 3, "저조": 4, "측정불가": 9}

# ⚠️ `출처` 는 2026-09-11 신설. **시드 채널에서 왔나, 보충 루프가 발굴해 왔나.**
#    없으면 신선도 경보가 「시드가 새 걸 안 낸다」를 말하면서 실제로는 발굴분까지 세고,
#    분기 채널 재점검 때 「이 채널이 몇 건 냈나」를 셀 수가 없다. 옛 행은 빈 값이고
#    그건 시드로 친다(발굴 루프가 생기기 전에 들어온 것이므로).
FIELDS = ["영상ID", "축", "분석점수", "생성점수", "등급", "성과지수", "조회수", "구독자",
          "길이초", "업로드", "제목", "채널", "채널ID", "좋아요", "댓글", "링크",
          "최초수집일", "최근확인일", "출처", "태그", "설명", "챕터"]

SRC_SEED = "시드"
SRC_FOUND = "발굴"


def is_seed(r):
    """빈 값은 시드로 친다 — 발굴 루프가 생기기 전 행들이다."""
    return (r.get("출처") or SRC_SEED) == SRC_SEED


def score_axis(title, desc):
    """제목(1배) + 설명(0.5배) 으로 두 축의 점수를 낸다."""
    def hit(table, text, w):
        return sum(v * w for k, v in table.items() if k in text)
    a = hit(ANALYSIS, title, 2) + hit(ANALYSIS, desc, 1)
    c = hit(CREATION, title, 2) + hit(CREATION, desc, 1)
    return a, c


def load_override():
    """수기 축 지정 — 기계 판정을 사람이 뒤집는다 (영상ID, 축, 사유).

    ⚠️ 두 축에 다 걸치는 제목이 있다. 「누구나 **만들 수 있는** 주식 비서 자동화 —
    매일 아침 카톡으로 포트폴리오 관리」는 만드는 이야기(생성)로도, 데이터를 모아
    읽어주는 이야기(분석)로도 읽힌다. 점수는 원장에 남겨 두었으니 사람이 보고 뒤집는다."""
    if not os.path.exists(OVERRIDE_CSV):
        return {}
    with io.open(OVERRIDE_CSV, encoding="utf-8-sig", newline="") as f:
        return {r["영상ID"]: r["축"] for r in csv.DictReader(f) if r.get("축") in AXES}


# 유튜브 설명의 타임스탬프 목록 = 그 영상의 진행 과정이다.
# T1 워크플로우 도형과 T2 컷이 이걸 초안으로 쓴다 (사람이 T1_대본.json 에서 고친다).
TS_LINE = re.compile(r"(?m)^\s*\(?(\d{1,2}:\d{2}(?::\d{2})?)\)?\s*[-\u2013\u2014.)\]:]*\s*(\S.*?)\s*$")


def chapters(desc, keep=12):
    """설명에서 챕터를 뽑아 `mm:ss 제목 | mm:ss 제목` 한 줄로.

    ⚠️ 소재풀의 `설명` 은 300자로 잘려 있어 여기서 못 뽑는다 — **수집 시점의
       전체 설명**으로만 채워진다. 옛 행은 `--chapters` 로 한 번 채운다.
    """
    out = []
    for t, name in TS_LINE.findall(desc or ""):
        name = re.sub(r"\s+", " ", name).strip(" -–—·|")
        if not name or len(name) > 60:
            continue
        out.append("%s %s" % (t, name))
        if len(out) >= keep:
            break
    return " | ".join(out)[:600]


def fetch_details(vids):
    """고른 영상 몇 건의 **설명 전문**을 다시 받는다. {영상ID: {설명, 챕터}}.

    원장의 `설명` 은 수집할 때 300자로 잘린다(62건 평균 297자 = 사실상 전부 잘렸다).
    한 쌍을 고른 뒤 **그 두 건만** 전문으로 다시 받아 원고의 근거로 쓴다 —
    50건당 1 unit 이라 회차당 1 unit 이다. 키가 없거나 API 가 막히면 빈 dict 를
    돌려주고, 부른 쪽은 원장의 잘린 설명으로 그냥 간다(원고가 얕아질 뿐 안 멈춘다).
    """
    vids = [v for v in vids if v]
    if not vids:
        return {}
    try:
        key = S.get_key()
    except SystemExit:
        return {}
    out = {}
    try:
        for c in S.chunk(vids, 50):
            d = S.api("videos", {"part": "snippet", "id": ",".join(c)}, key)
            for it in d.get("items", []):
                desc = it["snippet"].get("description", "") or ""
                out[it["id"]] = {"설명": desc, "챕터": chapters(desc, keep=20)}
    except Exception as e:
        print(f"  [자료] 설명 전문 재취득 실패 — 원장의 잘린 설명으로 갑니다: {e}")
        return out
    return out


def axis_of(title, desc, vid=None, override=None):
    a, c = score_axis(title, desc)
    if override and vid in override:
        return override[vid], a, c
    if a == c:
        return "미분류", a, c
    return ("분석" if a > c else "생성"), a, c


def passes(r):
    """게재 게이트 — 통과 못 하면 원장에 아예 안 넣는다(부정·광고는 수집 금지)."""
    t = r["제목"]
    if any(w in t for w in NEGATIVE) or any(w in t for w in PROMO):
        return False, "부정·광고"
    if len(_HAN.findall(t)) < MIN_HANGUL:
        return False, "한글부족"
    if not (MIN_SEC <= int(r["길이초"] or 0) <= MAX_SEC):
        return False, "길이"
    if int(r["조회수"] or 0) < MIN_VIEWS:
        return False, "조회수"
    return True, ""


# ── 채널 수집 ────────────────────────────────────────────────────────
def load_seed_cache():
    if not os.path.exists(SEED_CSV):
        return {}
    with io.open(SEED_CSV, encoding="utf-8-sig", newline="") as f:
        return {r["채널ID"]: r for r in csv.DictReader(f)}


def save_seed_cache(rows):
    os.makedirs(POOL, exist_ok=True)
    with io.open(SEED_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["채널ID", "별칭", "채널명", "구독자", "역할", "최근확인일"])
        w.writeheader()
        w.writerows(rows)


def fetch_channel(cid, key, since):
    """채널 업로드 재생목록을 훑는다. search 를 안 쓰므로 채널당 5~6 units."""
    ch = S.api("channels", {"part": "snippet,contentDetails,statistics", "id": cid}, key)
    if not ch.get("items"):
        return None, [], 1
    ch = ch["items"][0]
    up = ch["contentDetails"]["relatedPlaylists"]["uploads"]
    subs = int(ch["statistics"].get("subscriberCount") or 0)
    units = 1

    ids, tok, stop = [], None, False
    while not stop:
        d = S.api("playlistItems", {"part": "contentDetails", "playlistId": up,
                                    "maxResults": 50, "pageToken": tok}, key)
        units += 1
        for it in d["items"]:
            c = it["contentDetails"]
            if (c.get("videoPublishedAt") or "9999")[:10] < since:
                stop = True                      # 업로드 역순이라 여기서 끊으면 된다
                continue
            ids.append(c["videoId"])
        tok = d.get("nextPageToken")
        if not tok:
            break

    rows = []
    for c in S.chunk(ids, 50):
        d = S.api("videos", {"part": "snippet,statistics,contentDetails",
                             "id": ",".join(c)}, key)
        units += 1
        for it in d["items"]:
            sn, st, cd = it["snippet"], it["statistics"], it["contentDetails"]
            views = int(st.get("viewCount") or 0)
            ratio = views / subs if subs else None
            rows.append({
                "영상ID": it["id"], "등급": S.grade(ratio),
                "성과지수": round(ratio, 2) if ratio else "",
                "조회수": views, "구독자": subs,
                "길이초": S.parse_dur(cd["duration"]), "업로드": sn["publishedAt"][:10],
                "제목": sn["title"], "채널": sn["channelTitle"], "채널ID": cid,
                "좋아요": st.get("likeCount", ""), "댓글": st.get("commentCount", ""),
                "링크": "https://www.youtube.com/watch?v=" + it["id"],
                "태그": ", ".join(sn.get("tags", []))[:200],
                "설명": (sn.get("description", "") or "").replace("\n", " ")[:300],
                "챕터": chapters(sn.get("description", "")),
            })
    return ch, rows, units


# ── 원장 ─────────────────────────────────────────────────────────────
def load_pool():
    if not os.path.exists(POOL_CSV):
        return {}
    with io.open(POOL_CSV, encoding="utf-8-sig", newline="") as f:
        return {r["영상ID"]: r for r in csv.DictReader(f)}


def save_pool(pool):
    os.makedirs(POOL, exist_ok=True)
    rows = sorted(pool.values(), key=lambda r: (r["축"], -int(r["조회수"] or 0)))
    with io.open(POOL_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    return rows


EXCLUDE_CSV = os.path.join(POOL, "제외목록.csv")


def load_exclude():
    """수기 제외 — 게이트는 통과하지만 업무 세션 소재가 못 되는 것.
    ⚠️ 자동 선별은 「후보」까지다. 「우리 업무에 쓸 수 있나」는 기계가 못 거른다."""
    if not os.path.exists(EXCLUDE_CSV):
        return {}
    with io.open(EXCLUDE_CSV, encoding="utf-8-sig", newline="") as f:
        return {r["영상ID"]: r.get("사유", "") for r in csv.DictReader(f)}


def catalog_rows(all_rows):
    """추천·카탈로그에 실제로 오르는 행 — 축이 정해졌고 수기 제외가 아닌 것."""
    ex = load_exclude()
    return [r for r in all_rows if r["축"] in AXES and r["영상ID"] not in ex]


def write_catalog(all_rows, since, ran_at):
    os.makedirs(POOL, exist_ok=True)
    ex = load_exclude()
    rows = catalog_rows(all_rows)
    unsorted = [r for r in all_rows if r["축"] == "미분류"]

    L = []
    L.append("# AX 소재 카탈로그 — T1 1~2주차 「이달의 사례」")
    L.append("")
    L.append(f"수집 기준일 **{ran_at}** · 대상 **{since} 이후 업로드** · "
             f"게재 **{len(rows)}건** (원장 누적 {len(all_rows)}건)")
    L.append("")
    L.append("> 이 파일은 `tools/collect.py` 가 자동 생성한다. **직접 고치지 않는다** — "
             "다음 수집 때 덮어쓴다. 원장은 `소재풀.csv`.")
    L.append("> 기준의 정본은 `AX_source/docs/AX확산/02_확산_워크플로우.md` §7.0 이다.")
    L.append("")
    L.append(f"> ⚠️ **성과지수(조회수÷구독자)는 게이트가 아니다.** 표기만 남긴다 — "
             f"레퍼런스 2건이 각각 **0.44배 · 1.9배**라 어떤 배수 컷을 걸어도 안 들어온다.")
    L.append(f"> 게이트는 **조회 {MIN_VIEWS:,}↑ · 길이 {MIN_SEC//60}~{MAX_SEC//60}분 · "
             f"제목 한글 {MIN_HANGUL}자↑ · 부정·광고 제목 제외 · 시드 채널 {len(SEED_CHANNELS)}개**다.")
    L.append(f"> ⚠️ **부정적 소재는 수집하지 않는다.** T1 3주차 삽질·주의는 "
             f"**사내(T6 클리닉·제작 중 실패)** 소재만 쓴다.")
    L.append("")
    L.append("## 축별 요약")
    L.append("")
    L.append("| 축 | 무엇을 한 사례인가 | 건수 |")
    L.append("|---|---|--:|")
    L.append(f"| **분석** | 있는 데이터에서 몰랐던 관계를 찾았다 · 모아서 정리했다 | "
             f"{sum(1 for r in rows if r['축']=='분석')} |")
    L.append(f"| **생성** | 없던 산출물·시스템을 자동으로 만들었다 | "
             f"{sum(1 for r in rows if r['축']=='생성')} |")
    L.append(f"| *미분류* | *두 축 점수가 같아 사람이 봐야 한다* | {len(unsorted)} |")
    L.append("")

    for ax in AXES:
        rs = [r for r in rows if r["축"] == ax]
        rs.sort(key=lambda r: -int(r["조회수"] or 0))
        L.append(f"## {ax}  *({len(rs)}건)*")
        L.append("")
        L.append("| 조회수 | 구독자 | 지수 | 길이 | 업로드 | 제목 | 채널 |")
        L.append("|--:|--:|--:|--:|---|---|---|")
        for r in rs[:30]:
            title = r["제목"].replace("|", "\\|")[:60]
            ch = r["채널"].replace("|", "\\|")[:18]
            sec = int(r["길이초"] or 0)
            L.append(f"| {int(r['조회수'] or 0):,} | {int(r['구독자'] or 0):,} | "
                     f"{r['성과지수']} | {sec//60}분 | {r['업로드']} | "
                     f"[{title}]({r['링크']}) | {ch} |")
        if len(rs) > 30:
            L.append("")
            L.append(f"*상위 30건만 표시 · 전체 {len(rs)}건은 `소재풀.csv`*")
        L.append("")

    if unsorted:
        L.append("## 미분류 — 사람이 축을 정해야 한다")
        L.append("")
        L.append("| 조회수 | 길이 | 제목 |")
        L.append("|--:|--:|---|")
        for r in sorted(unsorted, key=lambda r: -int(r["조회수"] or 0))[:15]:
            L.append(f"| {int(r['조회수'] or 0):,} | {int(r['길이초'] or 0)//60}분 | "
                     f"[{r['제목'].replace('|','\\|')[:60]}]({r['링크']}) |")
        L.append("")
    if ex:
        L.append(f"*수기 제외 {len(ex)}건은 `제외목록.csv` 참조*")
        L.append("")

    io.open(CATALOG, "w", encoding="utf-8").write("\n".join(L) + "\n")


# ── 공급 경보 ────────────────────────────────────────────────────────
#  ① 신선도 — 이번 회차 신규 적립이 축별 3건 미만 → 시드 채널이 새 걸 안 낸다
#  ② 재고   — 축별 게재 후보가 3건 미만        → 그 축의 세션 소재가 없다 (더 급하다)
#  ⚠️ 축별로 따로 센다. 합계로 세면 분석 20건·생성 0건일 때도 정상으로 보이는데,
#     그 주 세션은 반쪽이 된다.
MIN_FRESH = 3
MIN_STOCK = 3
ALERT_LOG = os.path.join(POOL, "경보.log")


def supply_check(all_rows, new_by_axis=None, weeks=1):
    """공급 경보. `weeks` = 이번 수집이 «며칠치»를 새로 본 것인가.

    ⚠️ **같은 주에 두 번 돌리면 신규는 당연히 0이다.** 2026-09-11 리허설에서 재실행만으로
       「분석·생성 신규 0건 — 시드 채널이 낡았다」가 울렸다. 문구까지 단정형이라
       **엉뚱한 조치(채널 교체)로 유도**한다. 그래서 **신규가 0이면 침묵**한다 —
       0은 「채널이 낡았다」가 아니라 「이미 훑은 범위를 다시 훑었다」는 뜻이기 때문이다.
       진짜 고갈 신호는 **재고 경보**가 잡는다(그쪽은 누적을 보므로 재실행에 안 흔들린다).
    """
    al = []
    shown = catalog_rows(all_rows)
    if new_by_axis is not None:
        for ax in AXES:
            n = new_by_axis.get(ax, 0)
            if 0 < n < MIN_FRESH:
                al.append(("신선도", f"{ax} 신규 적립 {n}건 (하한 {MIN_FRESH}) : "
                                    f"시드 채널 산출이 얇다 — §7.0 채널 표를 확인한다"))
    for ax in AXES:
        n = sum(1 for r in shown if r["축"] == ax)
        n_seed = sum(1 for r in shown if r["축"] == ax and is_seed(r))
        if n >= MIN_STOCK and n_seed < MIN_STOCK:
            al.append(("시드 의존", f"{ax} 게재 후보 {n}건 중 시드 산출은 {n_seed}건 : "
                                  f"발굴분이 떠받치고 있다 — 분기 재점검 때 시드 편입을 본다"))
        if n < MIN_STOCK:
            al.append(("재고", f"{ax} 게재 후보 {n}건 (하한 {MIN_STOCK}) : "
                              f"그 축의 세션 소재가 없다 — 1~2주차가 반쪽이 된다"))
    return al


def report_alerts(al, ran_at):
    """경보는 콘솔·로그로만 알린다. 종료코드는 건드리지 않는다 —
    수집 자체는 성공했는데 배치가 상시 FAIL 로 보이면 아무도 안 본다."""
    os.makedirs(POOL, exist_ok=True)
    if not al:
        print("\n공급 경보 없음 : 두 축 모두 공급 가능")
        return
    print(f"\n{'!'*60}")
    print(f"[경보] 공급 경보 {len(al)}건")   # cp949 콘솔이라 이모지를 쓰지 않는다
    for kind, msg in al:
        print(f"  [{kind}] {msg}")
    print(f"{'!'*60}")
    with io.open(ALERT_LOG, "a", encoding="utf-8") as f:
        for kind, msg in al:
            f.write(f"{ran_at}\t{kind}\t{msg}\n")
    print(f"  기록 {ALERT_LOG}")


def log_run(ran_at, chs, since, found, added, units):
    os.makedirs(POOL, exist_ok=True)
    new = not os.path.exists(RUNLOG)
    with io.open(RUNLOG, "a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["실행일시", "채널", "기준일", "게이트통과", "신규적립", "할당량"])
        w.writerow([ran_at, " ".join(chs), since, found, added, units])


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--ch", nargs="+", help="채널 별칭 일부 (기본: 시드 채널 전체)")
    p.add_argument("--since",
                   default=(date.today() - timedelta(days=FRESH_DAYS)).isoformat(),
                   help=f"이 날짜 이후 업로드분 (기본 최근 {FRESH_DAYS}일)")
    p.add_argument("--rebuild", action="store_true", help="API 없이 카탈로그만 재생성")
    p.add_argument("--reset", action="store_true", help="원장을 비우고 새로 쌓는다")
    p.add_argument("--estimate", action="store_true", help="할당량만 계산하고 종료")
    p.add_argument("--chapters", action="store_true",
                   help="원장의 빈 `챕터` 만 채운다 (영상 50건당 1 unit)")
    a = p.parse_args()

    if a.chapters:
        # 챕터 열은 나중에 생긴 열이라 옛 행은 비어 있다. 설명은 300자로 잘려 저장돼
        # 다시 못 뽑으므로 영상 메타를 다시 받아 채운다 — 50건당 1 unit 이라 값이 싸다.
        pool = load_pool()
        if not pool:
            sys.exit("원장이 비어 있습니다.")
        todo = [v for v, r in pool.items() if not (r.get("챕터") or "").strip()]
        if not todo:
            print("빈 챕터가 없습니다.")
            return
        key, units, filled = S.get_key(), 0, 0
        for c in S.chunk(todo, 50):
            d = S.api("videos", {"part": "snippet", "id": ",".join(c)}, key)
            units += 1
            for it in d["items"]:
                ch = chapters(it["snippet"].get("description", ""))
                if ch:
                    pool[it["id"]]["챕터"] = ch
                    filled += 1
        save_pool(pool)
        print(f"챕터 채움 {filled}/{len(todo)}건 · {units} units 사용")
        return

    if a.rebuild:
        pool = load_pool()
        if not pool:
            sys.exit("원장이 비어 있습니다. 먼저 수집을 돌리세요.")
        ran_at = f"{datetime.now():%Y-%m-%d %H:%M}"
        # ⚠️ 축지정(수기·LLM 판정)을 여기서 **다시 적용한다**. 2026-09-11 까지는 안 했다 —
        #    축지정.csv 를 고치고 rebuild 를 돌려도 **다음 정식 수집 전까지 반영이 안 됐다.**
        #    에러가 안 나서 「고쳤는데 그대로네」로만 보이는 종류의 버그였다.
        ov = load_override()
        moved = 0
        for vid, ax in ov.items():
            if vid in pool and pool[vid]["축"] != ax:
                pool[vid]["축"] = ax
                moved += 1
        if ov:
            print(f"축지정 {len(ov)}건 적용 (바뀐 행 {moved}건)")
        rows = save_pool(pool)
        write_catalog(rows, a.since, ran_at)
        shown = len(catalog_rows(rows))
        print(f"카탈로그 재생성 · 원장 {len(rows)}건 -> 게재 {shown}건")
        print(f"  {CATALOG}")
        report_alerts(supply_check(rows), ran_at)   # 재생성은 신선도를 판정하지 않는다
        return

    seeds = SEED_CHANNELS
    if a.ch:
        seeds = [s for s in SEED_CHANNELS if any(k in s[0] for k in a.ch)]
        if not seeds:
            sys.exit(f"모르는 채널: {a.ch}  (가능: {[s[0] for s in SEED_CHANNELS]})")

    print(f"시드 채널 {len(seeds)}개 · {a.since} 이후 업로드")
    print(f"예상 할당량 약 {len(seeds)*6:,} units (일 한도 10,000)")
    if a.estimate:
        return

    key = S.get_key()
    ran_at = f"{datetime.now():%Y-%m-%d %H:%M}"
    pool = {} if a.reset else load_pool()
    if a.reset and os.path.exists(POOL_CSV):
        print(f"[reset] 기존 원장 {len(load_pool())}건을 버리고 새로 쌓습니다")
    before = len(pool)
    units = found = 0
    new_by_axis, seed_rows = {}, []
    drops = {}
    override = load_override()
    if override:
        print(f"수기 축 지정 {len(override)}건 적용")

    for alias, cid, role in seeds:
        ch, rows, u = fetch_channel(cid, key, a.since)
        units += u
        if ch is None:
            print(f"  [{alias}] 채널을 못 찾았습니다 ({cid})")
            continue
        name = ch["snippet"]["title"]
        subs = int(ch["statistics"].get("subscriberCount") or 0)
        seed_rows.append({"채널ID": cid, "별칭": alias, "채널명": name,
                          "구독자": subs, "역할": role, "최근확인일": ran_at[:10]})

        kept = 0
        for r in rows:
            ok, why = passes(r)
            if not ok:
                drops[why] = drops.get(why, 0) + 1
                continue
            found += 1
            vid = r["영상ID"]
            ax, sa, sc = axis_of(r["제목"], r["설명"], vid, override)
            old = pool.get(vid)
            if not old and ax in AXES:
                new_by_axis[ax] = new_by_axis.get(ax, 0) + 1
            rec = dict(r)
            rec.update({"축": ax, "분석점수": sa, "생성점수": sc,
                        "최초수집일": old["최초수집일"] if old else ran_at[:10],
                        "최근확인일": ran_at[:10],
                        "출처": SRC_SEED})       # 시드에서 다시 보였으면 시드로 승격
            pool[vid] = rec
            kept += 1
        print(f"  [{alias}] {name} (구독 {subs:,}) · 후보 {len(rows)}건 -> 게이트 통과 {kept}건")

    rows = save_pool(pool)
    save_seed_cache(seed_rows)
    write_catalog(rows, a.since, ran_at)
    log_run(ran_at, [s[0] for s in seeds], a.since, found, len(pool) - before, units)

    print(f"\n{'='*60}")
    print(f"게이트 통과 {found}건 · 신규 적립 {len(pool)-before}건 · 누적 {len(pool)}건")
    if drops:
        print("걸러낸 것 : " + " · ".join(f"{k} {v}" for k, v in sorted(drops.items())))
    print(f"축 : " + " · ".join(f"{ax} {sum(1 for r in rows if r['축']==ax)}" for ax in AXES)
          + f" · 미분류 {sum(1 for r in rows if r['축']=='미분류')}")
    print(f"할당량 {units:,} units 사용")
    print(f"원장     {POOL_CSV}")
    print(f"카탈로그 {CATALOG}")
    report_alerts(supply_check(rows, new_by_axis), ran_at)


if __name__ == "__main__":
    main()
