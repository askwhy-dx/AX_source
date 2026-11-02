# -*- coding: utf-8 -*-
"""인스타툰 두 편 → 사내게시판(AI자동화 공유) 글 문구. (2026-09-16 신설)

    python tools/build_board_post.py           # out/<회차>/게시판글_<회차>.txt 생성 + 출력
    python tools/build_board_post.py --clip    # 만들고 클립보드에도
    python tools/build_board_post.py --round 20260909
    python tools/build_board_post.py --self-test

**후킹형(버전2)** 한 틀만 쓴다 — **제목도 본문도 두 편의 표지 질문**으로 열고, 편마다 부장님
대사 한 줄, 끝은 댓글 유도. 문구는 전부 `T2_대본.json` 에서 읽는다. 대본을 고치면 글도 바뀐다.

제목에 들어가는 짧은 질문은 표지 질문을 줄여 쓴다. 줄인 말이 어색하면 **대본 축에
`"게시판훅": "매주 모으시나요?"` 한 줄**을 넣으면 그게 이긴다.

제목 규칙 **2026-09-21 변경**(사용자 지시) — 「N월 M주차 AI자동화 사례 공유」에서
**「N월 M번째 공유 - AI자동화 사례」** 로. 번호의 뜻도 같이 바뀌었다:
달력 주차가 아니라 **그 달에 올린 공유글 순번**이다(9월 2주차 글 = 9월 **첫번째** 공유).

⚠️ 제목의 「N월 M번째」는 `게시판자료전송/watch.js` 가 읽는 **기계 키**다(주차꼴도 계속 읽는다).
⚠️ 순번 출처는 **주차매핑**이고 월은 **회차 날짜**다 — 대본 머리말은 이제 제목에 안 쓴다.
   머리말의 주차를 그대로 쓰면 「그 달 N번째」와 값이 달라 조용히 어긋난다.
⚠️ 그 키가 `게시판자료전송/config.json` 의 주차매핑에 없으면 댓글이 달려도 **스킵**된다.
   그래서 없으면 경고를 찍는다 — 글은 만들어 준다(사람이 매핑을 넣고 올리면 된다).
⚠️ 매핑 값은 **회차(YYYYMMDD)** 또는 **링크 전체**다(2026-09-22). T1 덱이 없는 회차
   (체험 회차 등)는 회차만 넣으면 404 가 나간다 — 그 회차 `회차유형.json` 의 자료 URL 을
   값으로 넣는다. 경고가 둘 중 어느 쪽인지 찍어 준다.
⚠️ 한 달 안에서 주차꼴과 번째꼴을 **섞어 쓰면 안 된다** — 9월 2주차와 9월 두번째가
   같은 키 `9-2` 라 엉뚱한 회차 링크가 나간다.
"""
import argparse, io, json, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_page as B
import collect as C

CONF = os.path.join(C.ROOT, "게시판자료전송", "config.json")


def latest_round():
    """대본이 있는 가장 최근 회차. 툰은 며칠 뒤에 굽혀 나오므로 오늘 회차에는 없을 수 있다."""
    base = os.path.join(C.ROOT, "out")
    got = [d for d in sorted(os.listdir(base), reverse=True) if re.fullmatch(r"\d{8}", d)
           and os.path.exists(os.path.join(base, d, "T2_대본.json"))]
    return os.path.join(base, got[0]) if got else None


def pages(sc):
    return [p for p in (sc.get("장") or []) if isinstance(p, dict)]


def cover(sc):
    """표지 장. 없으면 첫 장."""
    ps = pages(sc)
    return next((p for p in ps if p.get("종류") == "표지"), ps[0] if ps else {})


def closing(sc):
    ps = pages(sc)
    return next((p for p in reversed(ps) if p.get("종류") == "마무리"), {})


def grandpa(sc):
    """부장님(할아버지) 대사 한 줄 — 「그거 사람이 해야 하는 거 아니야?」 자리.

    대본 축에 `"게시판부장님": false` 면 줄째로 뺀다(2026-09-27 — 남은 대사가 칭찬뿐인 회차).
    """
    if sc.get("게시판부장님") is False:
        return ""
    for p in pages(sc):
        if p.get("할아버지") and p.get("말"):
            return oneline(p["말"])
    return ""


def oneline(s):
    return re.sub(r"\s+", " ", (s or "").strip())


def hook(sc):
    """제목에 쓰는 **짧은 질문**. 대본에 「게시판훅」이 있으면 그걸 쓰고, 없으면 표지 질문을 줄인다.

    표지 질문은 두 줄짜리라 제목에 그대로 넣으면 길다 —
    「이 자료, 아직도 매주 손으로 모으세요?」 → 앞의 지시절과 「아직도」를 떼어 「매주 손으로 모으세요?」.
    줄였는데 질문이 아니게 되면(물음표 실종) 줄이지 않은 쪽을 쓴다.
    """
    h = oneline(sc.get("게시판훅"))
    if h:
        return h
    q = oneline(cover(sc).get("제목"))
    short = q.rsplit(",", 1)[-1].strip() if "," in q else q
    short = re.sub(r"^아직도\s*", "", short)
    return short if short.endswith("?") else q


ordinal = B.ordinal     # 회차 이름과 같은 함수 (build_page.round_label)


def mapping(mo=None):
    """주차매핑 전체, 또는 그 달 키의 번호 목록. config 를 못 읽으면 None."""
    try:
        keys = json.load(io.open(CONF, encoding="utf-8")).get("주차매핑", {})
    except Exception:
        return None
    if mo is None:
        return keys
    return sorted(int(k.split("-")[1]) for k in keys
                  if "-" in k and k.split("-")[0] == str(mo) and k.split("-")[1].isdigit())


def seq(mo):
    """이번 글이 그 달 **몇 번째 공유**인가 = 주차매핑에 이미 있는 그 달 글 수 + 1.

    ⚠️ 순번의 출처는 **대본 머리말이 아니라 주차매핑**이다(2026-09-21 규칙 변경).
       머리말의 「N주차」는 달력 주차라 「그 달 N번째 공유」와 값이 다르다 —
       9월 2주차 글이 9월 **첫번째** 공유였다. 머리말에서 끌어오면 번호가 조용히 어긋난다.
    ⚠️ 매핑은 글을 올린 뒤 사람이 넣는다. **지난 글 매핑을 빼먹으면 번호가 겹친다** —
       그래서 이 스크립트는 번호와 함께 그 근거(이미 있는 키)를 늘 찍는다.
    """
    ns = mapping(mo)
    return 1 if ns is None else (max(ns) + 1 if ns else 1)


def mapped(mo, n):
    """주차매핑에 이 번호가 있나. config 를 못 읽으면 판단하지 않는다(None)."""
    keys = mapping()
    return None if keys is None else f"{mo}-{n}" in keys


def build_one(sc, mo, sq):
    """한 편짜리 회차(체험)의 글. 두 편 틀에서 **두 번째 편과 「두 편」이라는 말만** 뺀다.

    2026-09-18 신설(사용자 지시) — 체험 회차는 인스타툰을 **체험편 한 개만** 만든다.
    제목의 「N월 M번째」는 `게시판자료전송/watch.js` 가 읽는 기계 키라 그대로 둔다.
    """
    n = len(pages(sc))
    gp = grandpa(sc)
    title = f"{mo}월 {ordinal(sq)} 공유 - AI자동화 사례 - {hook(sc)}"
    body = f"""{oneline(cover(sc).get('제목'))}

{mo}월 {ordinal(sq)} 공유는 이 질문에서 시작합니다.

{sc.get('제목','')}
{wrap(cover(sc).get('설명'))}.

{wrap(sc.get('축한줄') or AX1)}
""" + (f'"{gp}" 소리를 듣던 일입니다.\n' if gp else "") + f"""결과: {bang(closing(sc).get('제목'))}

{ASK}"""
    return title, body, (mo, sq)


# 축을 한 줄로 설명하는 자리. **사례 회차의 말**이라 체험 회차에서는 맞지 않는다
# (2026-09-18 실측: 설치·규칙 회차 글에 「도는 일은 AI가 합니다」가 그대로 나갔다).
# 그래서 대본이 축 아래 `축한줄` 을 주면 그게 이긴다(`마무리한줄` 은 2026-10-06 글에서 뺐다).
# ⚠️ 기본값은 옛 문장 그대로다 — 지난 회차 글이 바뀌면 안 된다.
AX1 = "사람이 정한 건 어디를 볼지 한 줄로 적는 것까지입니다. 도는 일은 AI가 합니다."
AX2 = "맞지 않는 도구를 참고 쓰는 대신, 필요한 화면을 AI로 직접 만들었습니다."

# 글 모양 **2026-10-06 변경**(사용자 지시 — 「앞으로도 이런 느낌으로」):
# 설명 문장은 쉼표 · 「~더니」에서 줄을 끊어 짧게, 문단 사이 빈 줄, 결과 줄 끝 「!!」,
# 「N컷 첨부합니다」 · 마무리 한 줄 · 「바로 보내드립니다」는 뺀다. 끝인사는 「^^」.
ASK = "적용 방법 및 상세 자료가 필요하시면\n댓글에 회사 메일주소(@askwhy.co.kr)를 남겨 주세요 ^^"


def wrap(s):
    """한 문장을 쉼표 · 「~더니」 뒤에서 끊어 여러 줄로."""
    return re.sub(r"(,|더니)\s+", r"\1\n", oneline(s))


def bang(s):
    return oneline(s).rstrip(".!") + " !!"


def build(sc_all, mo, sq):
    # 편 목록은 대본이 정한다 — **체험 회차는 「체험」 한 편**이다(2026-09-18 사용자 지시).
    # 전에는 분석·생성 두 축을 요구해 체험 회차에서 글이 아예 안 나왔다.
    eds = [v for k, v in sc_all.items() if isinstance(v, dict) and pages(v)]
    if not eds:
        raise SystemExit("  [멈춤] 대본에 장이 있는 편이 하나도 없습니다.")
    if len(eds) == 1:
        return build_one(eds[0], mo, sq)
    a, g = sc_all.get("분석") or {}, sc_all.get("생성") or {}
    if not pages(a) or not pages(g):
        raise SystemExit("  [멈춤] 두 편짜리 대본은 분석·생성 축이어야 합니다 "
                         "(한 편이면 그 편만 두세요).")
    n = min(len(pages(a)), len(pages(g)))
    title = f"{mo}월 {ordinal(sq)} 공유 - AI자동화 사례 - {hook(a)}, {hook(g)}"
    body = f"""{oneline(cover(a).get('제목'))}
{oneline(cover(g).get('제목'))}

{mo}월 {ordinal(sq)} 공유 사례는 이 두 질문에서 시작합니다.

[1편] {a.get('제목','')}
{wrap(cover(a).get('설명'))}.

{wrap(a.get('축한줄') or AX1)}
"{grandpa(a)}" 소리를 듣던 일입니다.
결과: {bang(closing(a).get('제목'))}

[2편] {g.get('제목','')}
{wrap(cover(g).get('설명'))}.

{wrap(g.get('축한줄') or AX2)}
"{grandpa(g)}" 소리를 듣던 일입니다.
결과: {bang(closing(g).get('제목'))}

{ASK}"""
    return title, body, (mo, sq)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", default=None, help="회차 YYYYMMDD (기본: 오늘 회차, 없으면 최근 회차)")
    ap.add_argument("--clip", action="store_true", help="클립보드에도 올린다")
    ap.add_argument("--self-test", action="store_true")
    a = ap.parse_args(argv)
    if a.self_test:
        return self_test()
    out_d = os.path.join(C.ROOT, "out", a.round) if a.round else B.out_dir()
    if not os.path.exists(os.path.join(out_d, "T2_대본.json")) and not a.round:
        out_d = latest_round() or out_d
    sp = os.path.join(out_d, "T2_대본.json")
    if not os.path.exists(sp):
        print("  [건너뜀] T2_대본.json 이 없습니다.")
        return 1
    rnd = os.path.basename(out_d)
    print(f"  회차 {rnd}")
    # 월은 회차 날짜(= 게시하는 수요일)에서, 순번은 주차매핑에서 낸다 — 대본 머리말은 이제 제목에 안 쓴다.
    mo = int(rnd[4:6])
    sq = seq(mo)
    # ⚠️ config/회차이름.json 에 이름이 있으면 그게 이긴다(2026-09-27). 매핑을 글보다 먼저
    #    넣으면(9-3) 「있는 키 + 1」이 9-4 로 밀렸다 — 제목 키가 틀리면 발송이 조용히 어긋난다.
    try:
        nm = json.load(io.open(os.path.join(C.ROOT, "config", "회차이름.json"), encoding="utf-8")).get(rnd, "")
        m = re.match(r"(\d+)월 (\S+)$", nm)
        inv = {ordinal(i): i for i in range(1, 11)}
        if m and m.group(2) in inv:
            mo, sq = int(m.group(1)), inv[m.group(2)]
    except (OSError, ValueError):
        pass
    have = mapping(mo)
    print(f"  제목 키 {mo}-{sq} ({ordinal(sq)}) · 근거: 주차매핑 {mo}월 "
          f"{'키 ' + ', '.join(f'{mo}-{x}' for x in have) if have else '비어 있음'}")
    title, body, (mo, sq) = build(json.load(io.open(sp, encoding="utf-8")), mo, sq)
    path = os.path.join(out_d, f"게시판글_{rnd}.txt")
    io.open(path, "w", encoding="utf-8").write(f"[제목]\n{title}\n\n[본문]\n{body}\n")
    print(f"\n[제목]\n{title}\n\n[본문]\n{body}\n")
    print(f"  → {path}")
    if mapped(mo, sq) is False:
        # 값은 회차(YYYYMMDD) 또는 링크 전체. T1 덱이 없는 회차에 회차만 넣으면 404 가 나간다
        # → 그 회차 회차유형.json 의 자료 URL 을 찍어 준다. (2026-09-22)
        val = rnd
        if not os.path.exists(os.path.join(out_d, f"T1_부서장회의_{rnd}.html")):
            try:
                링크 = json.load(io.open(os.path.join(out_d, "회차유형.json"), encoding="utf-8")).get("링크") or []
                val = 링크[0]["url"] if 링크 else "<자료 URL — 이 회차엔 T1 덱이 없다>"
            except Exception:
                val = "<자료 URL — 이 회차엔 T1 덱이 없다>"
        print(f"  [경고] 게시판자료전송/config.json 주차매핑에 \"{mo}-{sq}\" 가 없습니다 — "
              f"댓글이 달려도 발송이 스킵됩니다. 글을 올린 뒤 \"{mo}-{sq}\": \"{val}\" 를 추가하세요.")
    if a.clip:
        import toon_run
        toon_run.clip(f"{title}\n\n{body}")
    return 0


def self_test():
    """대본 한 벌을 지어 넣고, 기계가 읽는 자리(주차·제목·댓글 유도)가 살아 있나 본다."""
    def ax(head, t, q, desc, gp, close):
        return {"머리말": head, "제목": t, "장": [
            {"종류": "표지", "제목": q, "설명": desc},
            {"종류": "장면", "말": gp, "할아버지": True},
            {"종류": "마무리", "제목": close}]}
    sc = {"분석": ax("9월 2주차 · 가", "가제목", "이거 손으로?", "가 이야기", "사람이 해야지?", "안 한다"),
          "생성": ax("9월 2주차 · 나", "나제목", "저거 손으로?", "나 이야기", "그게 되나?", "된다")}
    title, body, w = build(sc, 9, 2)
    # watch.js 가 읽는 키 — 거기 정규식을 그대로 옮겨 온다. 두 쪽이 갈리면 글이 통째로 무시된다.
    KEY = r"(\d+)\s*월\s*(?:(\d+)\s*주차|(\d+|첫|두|세|네|다섯|여섯)\s*번째)"
    assert re.search(KEY, title), title
    assert "9월 두번째 공유" in title, title                        # 2026-09-21 규칙: 주차 아닌 순번
    assert w == (9, 2)
    assert title.endswith("이거 손으로?, 저거 손으로?"), title      # 제목 = 두 질문
    assert "첫번째" in build(sc, 9, 1)[0] and "열번째" in build(sc, 9, 10)[0]
    assert "11번째" in build(sc, 9, 11)[0]                          # 서수 표가 끝나면 숫자꼴
    sc["분석"]["장"][0]["제목"] = "이 자료, 아직도 매주 손으로 모으세요?"
    assert hook(sc["분석"]) == "매주 손으로 모으세요?"              # 지시절·「아직도」 제거
    sc["분석"]["게시판훅"] = "매주 모으시나요?"
    assert "매주 모으시나요?" in build(sc, 9, 2)[0]                  # 대본 훅이 이긴다
    assert "@askwhy.co.kr" in body and "AI" in body
    assert "이거 손으로?" in body and "사람이 해야지?" in body and "그게 되나?" in body
    assert "결과: 안 한다" in body and "결과: 된다" in body
    assert "장치" not in body
    assert "첨부합니다" not in body and body.endswith("^^")          # 2026-10-06 글 모양
    assert wrap("가는 길에, 나는 했더니 됐다") == "가는 길에,\n나는 했더니\n됐다"
    # 머리말은 이제 제목에 안 쓴다 — 주차가 없어도 글은 나와야 한다(2026-09-21).
    sc["분석"]["머리말"] = sc["생성"]["머리말"] = "주차 없음"
    assert "9월 두번째 공유" in build(sc, 9, 2)[0]
    # 순번은 주차매핑이 정한다 — 있는 키 다음 번호
    assert seq(9) == (max(mapping(9)) + 1 if mapping(9) else 1)
    print("  self-test OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
