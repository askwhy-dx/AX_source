# -*- coding: utf-8 -*-
"""
AX_source 소재 스캐너 — youtube_search.html 과 같은 로직을 CLI로 돌린다.
검색어 여러 개를 한 번에 훑어 쇼츠만 걸러내고 성과지수(조회수/구독자)로 줄 세운다.

사용:
    python tools/scan.py --axis A            # 축 A(AI 분석 자동화) 기본 검색어
    python tools/scan.py -q "AI 자동화" "클로드 스킬" --days 180 --max-sec 90
출력:
    out/scan_<축>_<날짜>.csv  +  화면 요약표
"""
import argparse, csv, io, json, os, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = "https://www.googleapis.com/youtube/v3/"

# 출력 인코딩은 run_weekly.bat 이 PYTHONUTF8=1 로 고정한다 (2026-09-08~).
# 그래도 이 파일을 손으로 직접 돌리면 cp949 라 «»·em dash·이모지에서
# UnicodeEncodeError 로 죽는다. 인코딩은 건드리지 않고 errors 만 푼다 (못 쓰는 글자는 ?).
# scan.py 를 import 하는 collect.py·build_page.py 에도 함께 적용된다.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(errors="replace")
    except Exception:
        pass

# 두 축의 기본 검색어 — 필요하면 여기만 고치면 된다
AXES = {
    "A": ["AI 자동화", "클로드 자동화", "챗GPT 업무 자동화", "엑셀 AI 자동화",
          "n8n 자동화", "AI 데이터 분석", "클로드 스킬", "AI 엑셀 정리"],
    "B": ["AI 영상 제작", "AI 이미지 생성", "AI 쇼츠 만들기", "AI 썸네일",
          "나노바나나", "AI 음악 만들기", "AI 로고 제작", "AI 광고 영상"],
}


def get_key():
    for line in io.open(os.path.join(ROOT, "..", ".env"), encoding="utf-8"):
        if line.startswith("YOUTUBE_API_KEY="):
            return line.split("=", 1)[1].strip()
    sys.exit("YOUTUBE_API_KEY 를 .env 에서 찾지 못했습니다.")


def api(path, params, key):
    params["key"] = key
    url = API + path + "?" + urllib.parse.urlencode(
        {k: v for k, v in params.items() if v not in ("", None)})
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def parse_dur(iso):
    m = re.match(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return d * 86400 + h * 3600 + mi * 60 + s


def chunk(seq, n):
    return [seq[i:i + n] for i in range(0, len(seq), n)]


def grade(ratio):
    if ratio is None:
        return "측정불가"
    for th, name in ((10, "떡상"), (3, "우수"), (1, "양호"), (0.3, "보통")):
        if ratio >= th:
            return name
    return "저조"


def scan(keywords, key, days, max_sec, order, per_kw):
    after = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace("+00:00", "Z") if days else ""
    vids, seen, units = {}, set(), 0

    for kw in keywords:
        ids, token = [], ""
        while len(ids) < per_kw:
            j = api("search", {"part": "id", "type": "video", "q": kw, "order": order,
                               "maxResults": min(50, per_kw - len(ids)), "regionCode": "KR",
                               "relevanceLanguage": "ko", "publishedAfter": after,
                               "pageToken": token}, key)
            units += 100
            ids += [i["id"]["videoId"] for i in j.get("items", []) if i.get("id", {}).get("videoId")]
            token = j.get("nextPageToken", "")
            if not token:
                break
        new = [i for i in ids if i not in seen]
        seen.update(ids)
        print(f"  [{kw}] 검색 {len(ids)}건 (신규 {len(new)}건)", flush=True)
        for c in chunk(new, 50):
            j = api("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(c)}, key)
            units += 1
            for v in j.get("items", []):
                v["_kw"] = kw
                vids[v["id"]] = v
        time.sleep(0.2)

    ch_ids = list({v["snippet"]["channelId"] for v in vids.values()})
    chs = {}
    for c in chunk(ch_ids, 50):
        j = api("channels", {"part": "statistics", "id": ",".join(c)}, key)
        units += 1
        for ch in j.get("items", []):
            st = ch["statistics"]
            chs[ch["id"]] = None if st.get("hiddenSubscriberCount") else int(st.get("subscriberCount", 0))

    rows = []
    for v in vids.values():
        sec = parse_dur(v["contentDetails"]["duration"])
        if max_sec and not (0 < sec <= max_sec):
            continue
        sn, st = v["snippet"], v["statistics"]
        views = int(st.get("viewCount", 0))
        subs = chs.get(sn["channelId"])
        ratio = views / subs if subs else None
        rows.append({
            "검색어": v["_kw"], "제목": sn["title"], "채널": sn["channelTitle"],
            "구독자": subs, "조회수": views, "성과지수": round(ratio, 2) if ratio else None,
            "등급": grade(ratio), "좋아요": st.get("likeCount"), "댓글": st.get("commentCount"),
            "길이초": sec, "업로드": sn["publishedAt"][:10],
            "태그": ", ".join(sn.get("tags", []))[:200],
            "설명": (sn.get("description", "") or "").replace("\n", " ")[:300],
            "링크": "https://www.youtube.com/watch?v=" + v["id"],
        })
    rows.sort(key=lambda r: (r["성과지수"] or -1), reverse=True)
    return rows, units


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--axis", choices=list(AXES))
    p.add_argument("-q", "--query", nargs="+")
    p.add_argument("--days", type=int, default=180)
    p.add_argument("--max-sec", type=int, default=60, help="0 이면 길이 제한 없음")
    p.add_argument("--order", default="viewCount", choices=["viewCount", "relevance", "date"])
    p.add_argument("--per-kw", type=int, default=50)
    p.add_argument("--top", type=int, default=30)
    a = p.parse_args()

    kws = a.query or AXES.get(a.axis)
    if not kws:
        sys.exit("--axis 또는 -q 로 검색어를 지정하세요.")

    key = get_key()
    print(f"검색어 {len(kws)}개 · 최근 {a.days}일 · 길이 <= {a.max_sec or '제한없음'}초")
    rows, units = scan(kws, key, a.days, a.max_sec, a.order, a.per_kw)

    os.makedirs(os.path.join(ROOT, "out"), exist_ok=True)
    tag = a.axis or "custom"
    path = os.path.join(ROOT, "out", f"scan_{tag}_{datetime.now():%Y%m%d}.csv")
    with io.open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)

    print(f"\n조건 통과 {len(rows)}건 · 할당량 {units} units · 저장 {path}\n")
    print(f"{'성과':>7} {'등급':<5} {'조회수':>9} {'구독자':>9} {'초':>3}  제목")
    print("-" * 100)
    for r in rows[:a.top]:
        print(f"{(r['성과지수'] or 0):>7.1f} {r['등급']:<5} {r['조회수']:>9,} "
              f"{(r['구독자'] or 0):>9,} {r['길이초']:>3}  {r['제목'][:52]}")


if __name__ == "__main__":
    main()
