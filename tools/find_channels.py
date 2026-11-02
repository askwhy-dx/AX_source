# -*- coding: utf-8 -*-
"""시드 채널 후보 실측기 — 「이 채널을 넣으면 분석축이 월 몇 건 늘어나나」. (2026-09-11 신설)

  python tools/find_channels.py --seeds                  # 현 시드 6개를 같은 잣대로 재본다(검증용)
  python tools/find_channels.py --url @handle <URL> ...  # 지정 후보 실측
  python tools/find_channels.py --file 후보.txt           # 한 줄에 하나씩
  python tools/find_channels.py --search "엑셀 자동화 실무" # 후보 발굴 (쿼리당 100 units)
  python tools/find_channels.py --file 후보.txt --months 12   # 창을 넓혀 본다

산출: out/pool/채널후보.csv  (+ 화면 표)

## 왜 「발굴기」가 아니라 「검증기」인가
채널을 감으로 고르면 틀린다. **일잘러 장피엠은 분석축 레퍼런스를 준 바로 그 채널인데
최근 6개월 분석축 산출이 0건**이다(2026-09-11 실측). 그래서 이 도구는 후보 채널을
**collect.py 의 게이트와 축 판정을 그대로 재사용해** 훑고, 「편입하면 실제로 들어올 건수」를
낸다. 리포트 숫자가 곧 편입 후의 현실이다.

## 원장을 건드리지 않는다
`out/pool/소재풀.csv` 에 **쓰지 않는다.** 채택이 정해진 뒤 `collect.py --ch <별칭>` 으로
정식 적립한다. 그래야 「재보기만 했는데 원장이 오염되는」 일이 없다.

⚠️ **채택은 사람이 한다.** 이 도구는 숫자만 낸다 — 화풍·신뢰도·회사 톤은 못 잰다.
⚠️ **시드 채널의 정본은 `AX_source/docs/AX확산/02_확산_워크플로우.md` §7.0 표다.**
   채택했으면 **거기를 먼저 고치고** `collect.SEED_CHANNELS` 를 맞춘다.
"""
import argparse, csv, io, os, re, sys
from collections import Counter
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scan as S
import collect as C
import build_page as B

OUT_CSV = os.path.join(C.POOL, "채널후보.csv")

# ── 채택 기준 (2026-09-11 사용자 컨펌) ─────────────────────────────────
# 분석축이 월 0.5건 = 현 시드 최고치(오빠두엑셀)와 같은 수준. 4채널이면 월 +2건이라
# 분석축 공급이 1.0 → 3.0건/월이 되어 필요량(1~3주차 회차당 1건)을 맞춘다.
MIN_ANA_PER_MONTH = 0.5
MIN_PASS = 3          # 창 안에서 게이트를 통과한 최소 건수 — 그 아래는 우연이다
MAX_JUNK_RATIO = 0.30  # 부정·광고로 떨어진 비율 상한 — 낚시성 채널 차단
WINDOW_MONTHS = 6      # 「6개월이면 기술 격차」 — 사용자 기준 (2026-09-11)


def resolve(token, key):
    """채널 URL·@핸들·UC아이디 → (채널ID, 표기). 못 찾으면 (None, 사유)."""
    t = token.strip().rstrip("/")
    if not t:
        return None, "빈 값"
    m = re.search(r"/channel/(UC[\w-]{20,})", t)
    if m:
        return m.group(1), m.group(1)
    if re.fullmatch(r"UC[\w-]{20,}", t):
        return t, t
    m = re.search(r"/(@[\w.\-가-힣]+)", t) or re.fullmatch(r"(@[\w.\-가-힣]+)", t)
    handle = m.group(1) if m else None
    if not handle and "youtube.com" not in t:
        handle = "@" + t.lstrip("@")
    if handle:
        try:
            d = S.api("channels", {"part": "id", "forHandle": handle}, key)     # 1 unit
            if d.get("items"):
                return d["items"][0]["id"], handle
        except Exception:
            pass
    m = re.search(r"/(?:c|user)/([\w.\-]+)", t)
    if m:
        try:
            d = S.api("channels", {"part": "id", "forUsername": m.group(1)}, key)
            if d.get("items"):
                return d["items"][0]["id"], m.group(1)
        except Exception:
            pass
    return None, f"못 찾음({token})"


def search_channels(q, key, n=10):
    """search.list(type=channel) — **쿼리당 100 units.** 후보를 넓힐 때만 쓴다."""
    d = S.api("search", {"part": "snippet", "type": "channel", "q": q,
                         "maxResults": min(n, 25), "regionCode": "KR",
                         "relevanceLanguage": "ko"}, key)
    out = []
    for it in d.get("items", []):
        cid = (it.get("id") or {}).get("channelId")
        if cid:
            out.append((cid, it["snippet"]["title"]))
    return out


def discover_by_video(q, key, since, n=50):
    """**영상**을 조회수 순으로 찾아 그 채널을 후보로 삼는다. 쿼리당 100 units.

    ⚠️ `--search`(type=channel) 는 2026-09-11 실측에서 **쓸모가 없었다.**
       채널 검색은 관련도 순이라 구독 1천~9천짜리 작은 채널이 올라오는데,
       우리 게이트(조회수 30,000)를 **20개 중 0개**가 넘었다. 252 units 를 태우고 0건.
       그래서 「우리 게이트를 이미 넘긴 영상」을 먼저 찾고 **그 영상의 채널**을 후보로 잡는다.
    """
    params = {"part": "snippet", "type": "video", "q": q,
              "order": "viewCount", "maxResults": min(n, 50),
              "regionCode": "KR", "relevanceLanguage": "ko"}
    if since:                      # None 이면 날짜 제한 없이 — 0건일 때의 재시도용
        params["publishedAfter"] = since + "T00:00:00Z"
    d = S.api("search", params, key)
    # ⚠️ videoDuration=long(20분+) 을 걸었더니 2026-09-11 실측에서 쿼리당 0~2채널로 말랐다.
    #    길이는 우리 게이트(300~3600초)가 이미 보므로 여기서 또 조이지 않는다.
    out = {}
    for it in d.get("items", []):
        sn = it.get("snippet") or {}
        cid = sn.get("channelId")
        if cid:
            out.setdefault(cid, sn.get("channelTitle", cid))
    return list(out.items())


def measure(cid, key, since):
    """한 채널을 훑어 평가만 한다. 원장에는 쓰지 않는다."""
    ch, rows, units = C.fetch_channel(cid, key, since)
    if ch is None:
        return None, units
    kept, drops = [], Counter()
    for r in rows:
        ok, why = C.passes(r)
        if ok:
            ax, sa, sc = C.axis_of(r["제목"], r["설명"], r["영상ID"])
            rr = dict(r); rr["축"] = ax
            kept.append(rr)
        else:
            drops[why] += 1
    by = Counter(r["축"] for r in kept)
    months = max(1, WINDOW_MONTHS)
    # ⚠️ 분석 건수를 그대로 쓰면 **도구 강의가 섞여 부풀려진다.** 2026-09-11 실측에서
    #    원장 분석축 13건 중 10건이 「A to Z·총정리·활용법」류 강의였다.
    #    `fit()` 의 강의 어휘를 재사용해 사례성만 따로 센다 — 채택 판정은 이쪽을 본다.
    ana_rows = [r for r in kept if r["축"] == "분석"]
    ana_case = [r for r in ana_rows if not any(w in r["제목"] for w in B.LECTURE)]
    ana_pm = len(ana_case) / months
    junk = drops["부정·광고"] / len(rows) if rows else 0.0

    if ana_pm >= MIN_ANA_PER_MONTH and len(kept) >= MIN_PASS and junk < MAX_JUNK_RATIO:
        verdict, why = "채택 권장", f"분석 월 {ana_pm:.2f}"
    elif not ana_case:
        verdict, why = "기각", ("창 안에 분석 사례 0건"
                              + (f" (분석 {by['분석']}건은 전부 강의)" if by["분석"] else ""))
    elif ana_pm >= MIN_ANA_PER_MONTH * 0.6 or len(kept) >= MIN_PASS:
        verdict, why = "보류", f"분석 월 {ana_pm:.2f} — 기준 {MIN_ANA_PER_MONTH}"
    else:
        verdict, why = "기각", f"분석 월 {ana_pm:.2f}"
    if junk >= MAX_JUNK_RATIO:
        verdict, why = "기각", f"부정·광고 탈락 {junk:.0%}"

    return {
        "채널ID": cid,
        "채널명": ch["snippet"]["title"],
        "구독자": int(ch["statistics"].get("subscriberCount") or 0),
        "창내영상": len(rows),
        "게이트통과": len(kept),
        "분석": by["분석"], "분석사례": len(ana_case),
        "생성": by["생성"], "미분류": by["미분류"],
        "분석월평균": round(ana_pm, 2),
        "생성월평균": round(by["생성"] / months, 2),
        "부정광고탈락": drops["부정·광고"],
        "길이탈락": drops["길이"], "조회수탈락": drops["조회수"], "한글탈락": drops["한글부족"],
        "판정": verdict, "사유": why,
        "_대표": sorted(ana_case,
                       key=lambda r: -int(r["조회수"] or 0))[:3],
    }, units


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", nargs="+", default=[], help="채널 URL·@핸들·UC아이디")
    p.add_argument("--file", help="후보 목록 (한 줄에 하나, # 는 주석)")
    p.add_argument("--search", nargs="+", default=[],
                   help="채널 검색으로 발굴 (쿼리당 100 units) - 2026-09-11 실측 수확 0건, 권장 안 함")
    p.add_argument("--discover", nargs="+", default=[],
                   help="**영상 조회수 순**으로 찾아 그 채널을 후보로 (쿼리당 100 units) - 이쪽을 쓴다")
    p.add_argument("--seeds", action="store_true", help="현 시드 채널을 같은 잣대로 재본다")
    p.add_argument("--months", type=int, default=WINDOW_MONTHS, help="평가 창 (기본 6개월)")
    p.add_argument("--per", type=int, default=50,
                   help="쿼리당 후보 채널 상한 (측정 시간·할당량 제어)")
    p.add_argument("--estimate", action="store_true", help="할당량만 계산")
    a = p.parse_args()

    globals()["WINDOW_MONTHS"] = a.months     # measure() 가 읽는 창 — 인자로 덮는다
    since = (date.today() - timedelta(days=int(a.months * 30.5))).isoformat()

    tokens = list(a.url)
    if a.file:
        for line in io.open(a.file, encoding="utf-8"):
            line = line.split("#")[0].strip()
            if line:
                tokens.append(line)

    est = (len(tokens) * 6 + (len(a.search) + len(a.discover)) * 100
           + (len(C.SEED_CHANNELS) * 6 if a.seeds else 0))
    print(f"평가 창 {since} 이후 ({a.months}개월) · 예상 할당량 약 {est:,} units")
    if a.estimate:
        return
    if not (tokens or a.search or a.discover or a.seeds):
        sys.exit("후보가 없습니다. --seeds / --url / --file / --search 중 하나를 주세요.")

    key = S.get_key()
    units = 0
    targets = []          # (채널ID, 표기)

    if a.seeds:
        targets += [(cid, alias) for alias, cid, _r in C.SEED_CHANNELS]
    for t in tokens:
        cid, label = resolve(t, key)
        units += 1
        if cid:
            targets.append((cid, label))
        else:
            print(f"  [건너뜀] {label}")
    for q in a.search:
        found = search_channels(q, key)
        units += 100
        print(f"  [채널검색] «{q}» → {len(found)}개")
        targets += [(cid, name) for cid, name in found]
    for q in a.discover:
        found = discover_by_video(q, key, since)[:a.per]
        units += 100
        print(f"  [영상발굴] «{q}» → 채널 {len(found)}개")
        targets += [(cid, name) for cid, name in found]

    seen, uniq = set(), []
    for cid, label in targets:
        if cid not in seen:
            seen.add(cid); uniq.append((cid, label))

    rows = []
    for cid, label in uniq:
        try:
            rec, u = measure(cid, key, since)
        except Exception as e:
            print(f"  [실패] {label}: {str(e)[:70]}")
            continue
        units += u
        if rec is None:
            print(f"  [없음] {label}")
            continue
        rows.append(rec)
        print(f"  {rec['판정']:<6} {rec['채널명'][:26]:<28} "
              f"분석 {rec['분석']:>2}(사례 {rec['분석사례']:>2}) · 생성 {rec['생성']:>2}"
              f" · 월 {rec['분석월평균']:.2f}")

    rows.sort(key=lambda r: (-r["분석월평균"], -r["게이트통과"]))

    print("\n" + "=" * 96)
    print(f"{'판정':<7}{'채널':<28}{'구독':>9}{'통과':>5}{'분석':>5}{'사례':>5}{'생성':>5}{'사례/월':>8}  사유")
    print("-" * 96)
    for r in rows:
        print(f"{r['판정']:<7}{r['채널명'][:26]:<28}{r['구독자']:>9,}{r['게이트통과']:>5}"
              f"{r['분석']:>5}{r['분석사례']:>5}{r['생성']:>5}{r['분석월평균']:>8.2f}  {r['사유']}")

    ok = [r for r in rows if r["판정"] == "채택 권장"]
    if ok:
        print(f"\n채택 권장 {len(ok)}개 → 분석축 월 +{sum(r['분석월평균'] for r in ok):.1f}건")
        for r in ok:
            print(f"\n  ▸ {r['채널명']}  ({r['채널ID']})")
            for v in r["_대표"]:
                print(f"      · {v['제목'][:62]}  ({v['업로드']} · {int(v['조회수']):,})")
    else:
        print("\n채택 권장 0개 — 후보를 더 모으거나 창(--months)을 넓혀 본다.")

    os.makedirs(C.POOL, exist_ok=True)
    cols = [k for k in rows[0].keys() if not k.startswith("_")] if rows else []
    if cols:
        with io.open(OUT_CSV, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            w.writeheader(); w.writerows(rows)
        print(f"\n기록 {OUT_CSV}")
    print(f"할당량 {units:,} units 사용")
    print("\n⚠️ 채택했으면 **AX_source/docs/AX확산/02_확산_워크플로우.md §7.0 표를 먼저** 고치고,")
    print("   collect.SEED_CHANNELS 를 맞춘 뒤 `python tools/collect.py --ch <별칭>` 으로 적립한다.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
