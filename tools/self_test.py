# -*- coding: utf-8 -*-
"""
AX_source 자체 점검 — 기준을 고친 뒤 이걸 먼저 돌린다.

    python tools/self_test.py

무엇을 지키나 — **사용자가 준 레퍼런스 2건이 각 축 1~2위에 오는가.**
이 두 건이 이 파이프라인의 「정답」이다. 게이트나 적합도 점수를 만지면
조용히 다른 종류가 위로 올라오는데, 화면상으로는 아무 에러도 안 난다.
v1이 정확히 그렇게 무너졌다 — 추천 3건이 전부 「쇼츠 툴 팁」이었다.

⚠️ 점수표를 고쳐서 이 테스트를 통과시키는 게 목적이 아니다.
   레퍼런스가 밀려났으면 **왜 밀렸는지**를 먼저 본다.
"""
import io, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect as C
import build_page as B

# 사용자가 2026-09-08 에 지정한 레퍼런스 (docs/AX확산/02 §7.0 표와 같은 것)
REFERENCE = {
    "분석": ("iJfRqfDetsI", "알아서 웹 데이터 긁어오는 AI 에이전트 무료로 나눠드려요"),
    "생성": ("CVmbidt-3ro", "토스 PO 출신 대표가 사내 ERP와 AI 에이전트를 직접 만들고"),
}
MAX_RANK = 2          # 각 축 1~2위 안에 있어야 한다
MIN_STOCK = 3         # 축별 최소 재고

# 발행본에 홀로 남은 `>` — 여는 태그가 통째로 지워지면 이 자국이 남는다(2026-09-18 사고).
# ⚠️ 이 패턴은 **모듈 상수로 둔다.** 검사 함수 안에 인라인으로 쓰면 편집·복사 과정에서
#    `\n` 이 실제 줄바꿈으로 풀려 파일이 깨진다 — 이 파일을 고치다 실제로 그랬다.
STRAY_GT = re.compile(r'\n\s*>\s*\n')


BAT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "run_weekly.bat")


def _check_bat(bat=None, name=None):
    """배치가 콘솔 규약을 지키는지. (검사명, 실패사유 or None) 목록.

    ⚠️ **배치가 둘이다**(2026-09-09~) — 수요일 run_plan.bat · 목요일 run_weekly.bat.
       한쪽만 검사하면 **새 배치가 규약을 어겨도 PASS 가 뜬다.** 둘 다 돈다.
    """
    bat = bat or BAT
    name = name or os.path.basename(bat)
    out = []
    try:
        raw = io.open(bat, "rb").read()
    except OSError as e:
        return [("%s 읽기" % name, "읽을 수 없다 - %s" % e)]

    # ① ASCII 전용 — 949 콘솔에서 cmd 가 멀티바이트 줄마다 오프셋이 밀려 줄 중간부터
    #    실행한다. 중간에 chcp 65001 을 켜도 늦다(시작 시점 코드페이지가 파싱을 정한다).
    ko = [i + 1 for i, x in enumerate(raw.split(b"\r\n")) if not x.isascii()]
    out.append(("%s 배치 ASCII 전용" % name,
                None if not ko
                else "비ASCII 줄 %s - 한글은 tools/say.py 로 옮긴다 (949 창에서 줄 중간 실행)"
                     % (ko[:5] + (["..."] if len(ko) > 5 else []))))

    out.append(("%s 배치 CRLF" % name,
                None if b"\r\n" in raw
                else "LF 로 저장됐다 - cmd 가 줄을 잘못 읽어 안내가 깨진다"))

    txt = raw.decode("utf-8", errors="replace")

    # ② 주석에는 경고문으로 chcp 949 가 적혀 있을 수 있다. 실행되는 줄만 본다.
    bad = [x.strip() for x in txt.splitlines()
           if re.match(r"\s*chcp\s+\d+", x) and not re.match(r"\s*chcp\s+65001\b", x)]
    out.append(("%s 콘솔 비오염(chcp)" % name,
                None if not bad
                else "65001 이외로 바꾸는 줄이 있다 %s - 호출한 창이 그 값으로 굳는다" % bad))

    out.append(("%s 파이썬 인코딩 고정" % name,
                None if "PYTHONUTF8=1" in txt
                else "PYTHONUTF8=1 이 없다 - 실행 주체에 따라 로그가 cp949/UTF-8 로 섞인다"))

    # ③ 한글 메시지 창구가 살아 있나
    say = os.path.join(os.path.dirname(os.path.abspath(__file__)), "say.py")
    out.append(("한글 창구 say.py",
                None if os.path.exists(say) else "tools/say.py 가 없다 - 배치 안내가 안 나온다"))
    return out


def main():
    fails = []
    all_rows, rows, _ = B.load_rows()
    print(f"원장 {len(all_rows)}건 · 게재 {len(rows)}건\n")

    # ① 축 판정 — 레퍼런스가 제 축에 들어갔나
    by_id = {r["영상ID"]: r for r in all_rows}
    for ax, (vid, title) in REFERENCE.items():
        r = by_id.get(vid)
        if not r:
            fails.append(f"[축] {ax} 레퍼런스가 원장에 없다 ({vid}) — 게이트에 걸렸는지 본다")
            print(f"  FAIL {ax} 레퍼런스 미수집")
            continue
        mark = "OK  " if r["축"] == ax else "FAIL"
        if r["축"] != ax:
            fails.append(f"[축] {ax} 레퍼런스가 「{r['축']}」으로 분류됐다 "
                         f"(분석{r['분석점수']}/생성{r['생성점수']}) — 축지정.csv 로 뒤집을 수 있다")
        print(f"  {mark} 축 판정 {ax}: {r['축']} (분석{r['분석점수']}/생성{r['생성점수']})")

    # ② 추천 순위 — 레퍼런스가 각 축 상위에 오나
    print()
    for ax, (vid, title) in REFERENCE.items():
        c = [r for r in rows if r["축"] == ax]
        c.sort(key=lambda r: (-r["_fit"], -r["_views"]))
        ids = [r["영상ID"] for r in c]
        rank = ids.index(vid) + 1 if vid in ids else None
        ok = rank is not None and rank <= MAX_RANK
        if not ok:
            fails.append(f"[순위] {ax} 레퍼런스 순위 {rank} (기준 {MAX_RANK} 이내) — "
                         f"적합도 점수표가 다른 종류를 위로 올리고 있다")
        print(f"  {'OK  ' if ok else 'FAIL'} 순위 {ax}: {rank}위 / {len(c)}건")
        for i, r in enumerate(c[:3], 1):
            tag = " <== 레퍼런스" if r["영상ID"] == vid else ""
            print(f"        {i}. 적합{r['_fit']:>3} {r['제목'][:46]}{tag}")

    # ③ 재고 — 두 축이 다 살아 있나 (한쪽만 있으면 그 주 세션이 반쪽이 된다)
    print()
    for ax in C.AXES:
        n = sum(1 for r in rows if r["축"] == ax)
        ok = n >= MIN_STOCK
        if not ok:
            fails.append(f"[재고] {ax} {n}건 (하한 {MIN_STOCK})")
        print(f"  {'OK  ' if ok else 'FAIL'} 재고 {ax}: {n}건")

    # ④ 부정 소재가 새어 들어오지 않았나
    print()
    leaked = [r for r in all_rows
              if any(w in r["제목"] for w in C.NEGATIVE) or any(w in r["제목"] for w in C.PROMO)]
    if leaked:
        fails.append(f"[부정] 부정·광고 제목 {len(leaked)}건이 원장에 있다")
        for r in leaked[:5]:
            print(f"  FAIL 부정 유입: {r['제목'][:56]}")
    else:
        print(f"  OK   부정·광고 유입 0건 (금지어 {len(C.NEGATIVE)+len(C.PROMO)}개 기준)")

    # ⑤ 배치가 공유 콘솔을 오염시키는 상태로 되돌아가지 않았나
    #    코드페이지는 프로세스가 아니라 「창」 속성이라, 배치가 chcp 949 로 바꾸면 같은
    #    창에서 UTF-8 로 그리던 Claude Code 화면이 한글도 ANSI 이스케이프도 통째로 깨진다.
    #    끝에서 되돌리는 줄은 배치가 끝까지 살아야 도는데, 사고는 정확히 「안 끝나는」
    #    경우(타임아웃 킬·Ctrl+C·QuickEdit 프리즈)에 난다 - 필요한 순간에만 작동하지 않는
    #    방어막이었다. 그래서 「되돌린다」를 버리고 「애초에 안 바꾼다」로 갔다.
    #    2026-09-08 실제 사고. README §10 과 한 쌍이다 - 문서만으로는 못 막아서 여기 둔다.
    print()
    # 2026-09-28 자동 수집(스케줄러·배치) 폐지 — 배치가 없으면 검사할 것도 없다.
    plan = os.path.join(os.path.dirname(BAT), "run_plan.bat")
    checks = []
    for b in (BAT, plan):
        if os.path.exists(b):
            checks += [c for c in _check_bat(b) if b == BAT or "say.py" not in c[0]]
    for name, why in checks:
        if why:
            fails.append("[배치] %s - %s" % (name, why))
            print("  FAIL %s: %s" % (name, why))
        else:
            print("  OK   %s" % name)

    # ⑥ 「회차별 보기」 칩이 **그 회차 폴더**를 가리키나 (2026-09-10)
    #    ⚠️ 산출물로 가는 길은 이제 이 칩뿐이다(상단 메뉴는 2026-09-10 삭제).
    #       폴더를 한 번 틀리면 **파일은 멀줦한데 링크만 죽는다** — 배치는 정상
    #       종료하고 페이지도 멀줦해 보여서 **눌러 봐야만 알아차린다**(메뉴에서 실제로 당했다).
    print()
    page = os.path.join(os.path.dirname(BAT), "소재추천.html")
    if not os.path.exists(page):
        print("  --   소재추천.html 이 아직 없다")
    else:
        html = io.open(page, encoding="utf-8").read()
        boxes = re.findall(r'<div class="rbox" data-r="(\d{8})"(.*?)</div></div>', html, re.S)
        if not boxes:
            fails.append("[회차] 「회차별 보기」 상자가 페이지에 없다 - 산출물로 갈 길이 없다")
            print("  FAIL 「회차별 보기」 상자가 없다")
        n_all = bad = 0
        for rnd, body in boxes:
            for href in re.findall(r'class="chip" href="([^"]+)"', body):
                # 회차유형.json 의 외부 자료 링크(교육가이드 등)는 회차 폴더 밖이 정상이다
                # (2026-09-16). 여기서 막으면 체험 회차가 자료로 갈 길을 못 만든다.
                if href.startswith(("http://", "https://")):
                    continue
                n_all += 1
                fp = os.path.join(C.ROOT, href.replace("/", os.sep))
                if not href.startswith("out/%s/" % rnd):
                    fails.append("[회차] %s - %s 회차 칩인데 폴더가 다르다" % (href, rnd))
                    print("  FAIL 칩 링크 폴더가 다름: %s (회차 %s)" % (href, rnd))
                    bad += 1
                elif not os.path.exists(fp):
                    fails.append("[회차] %s - 링크는 있는데 파일이 없다" % href)
                    print("  FAIL 칩이 없는 파일을 가리킴: %s" % href)
                    bad += 1
        if boxes and not bad:
            print("  OK   회차별 보기 칩 %d개 살아 있음 (회차 %d개)" % (n_all, len(boxes)))

        # 머리 칩(#앵커)이 **실제로 있는 절**을 가리키나 (2026-09-18 신설)
        # 두 번 데인 자리다 — 2026-09-10 에는 셋이 갈 곳이 없었고, 2026-09-18 에는
        # 체험 회차 주에 「한 쌍·대안」 절을 안 만들면서 그 칩만 남았다.
        # **갈 곳 없는 칩은 눌러 봐야 안다** — 화면은 멀쩡해 보인다.
        anchors = set(re.findall(r'<h2 id="([a-zA-Z0-9_-]+)"', html))
        dead = [h for h in re.findall(r'class="chip"[^>]*href="#([a-zA-Z0-9_-]+)"', html)
                if h not in anchors]
        if dead:
            fails.append("[칩] 머리 칩이 없는 절을 가리킨다: %s — 절을 빼면 칩도 뺀다"
                         % ", ".join("#" + d for d in dead))
            print("  FAIL 죽은 머리 칩: %s" % ", ".join("#" + d for d in dead))
        else:
            print("  OK   머리 칩 앵커 전부 살아 있음 (절 %d개)" % len(anchors))

    # ── ⑦ 소스에 제어문자가 섞이지 않았나 (2026-09-18 신설) ───────────
    # 2026-09-18 사고: `publish.py` 의 `re.sub(..., r'\1', ...)` 자리에 **제어문자 0x01
    # 한 바이트**가 들어 있었다. 그래서 `hidden` 만 지우는 대신 **여는 태그를 통째로
    # 지웠고**, 공개본에서 회차 상자가 사라졌다. **에러는 안 났다** — 파이썬에게 0x01 은
    # 그냥 문자다. 문서로는 못 막아서(같은 계열로 이미 여러 번 데였다) 여기서 센다.
    print()
    CTRL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f]')
    tools_dir = os.path.dirname(os.path.abspath(__file__))
    dirty = []
    for fn in sorted(os.listdir(tools_dir)):
        if not fn.endswith(".py"):
            continue
        raw = io.open(os.path.join(tools_dir, fn), "rb").read().decode("utf-8", "replace")
        for i, line in enumerate(raw.splitlines(), 1):
            m = CTRL.search(line)
            if m:
                dirty.append("%s:%d (0x%02x)" % (fn, i, ord(m.group())))
    if dirty:
        fails.append("[소스] 제어문자가 섞였다: %s — `\\1` 같은 escape 가 한 바이트로 "
                     "바뀐 자리다. 에러 없이 조용히 동작이 바뀐다" % ", ".join(dirty[:5]))
        print("  FAIL 제어문자 %d곳: %s" % (len(dirty), ", ".join(dirty[:5])))
    else:
        print("  OK   tools/*.py 에 제어문자 없음")

    # ── ⑧ 발행본 화면 구조가 성립하나 (2026-09-18 신설) ───────────────
    # **로컬은 멀쩡한데 공개본만 깨지는** 층이다. 발행기는 로컬 페이지에서 미발행 회차를
    # 잘라 내므로, 그 가위질이 틀리면 로컬을 아무리 봐도 안 보인다. 그래서 발행 **직전
    # 판(staged)** 을 여기서 만들어 본다 — 회차마다 ①상자가 다 있나 ②펼친 상자가 정확히
    # 하나인가 ③버튼 `on` 이 그 회차인가 ④떠돌이 `>` 가 없나.
    print()
    try:
        import publish as PB
        page = io.open(os.path.join(B.C.ROOT, PB.PAGE), encoding="utf-8").read()
        allr = set(re.findall(r'<div class="rbox" data-r="(\d{8})"', page))
        # 회차를 잘라 내는 경로까지 태운다 — 가장 오래된 회차를 미발행으로 본 판도 같이 본다.
        # (실제 발행이 그 모양이다: 원격에 없는 회차는 화면에서 빠진다)
        sets = [allr] + ([allr - {min(allr)}] if len(allr) > 1 else [])
        bad = []
        for keep in sets:
            for rnd in sorted(keep):
                st, _ = PB.drop_other_rounds(PB.inject_noindex(page), keep, rnd)
                boxes = re.findall(r'<div class="rbox" data-r="(\d{8})"([^>]*)>', st)
                opened = [r for r, at in boxes if "hidden" not in at]
                on = re.findall(r'class="rbtn on"[^>]*data-r="(\d{8})"', st)
                if len(boxes) != len(keep):
                    bad.append("%s: 상자 %d/%d" % (rnd, len(boxes), len(keep)))
                if opened != [rnd]:
                    bad.append("%s: 펼친 상자 %s" % (rnd, opened or "없음"))
                if on != [rnd]:
                    bad.append("%s: 버튼 on %s" % (rnd, on or "없음"))
                if STRAY_GT.search(st):
                    bad.append("%s: 떠돌이 `>`" % rnd)
        if bad:
            fails.append("[발행본] 화면 구조가 깨진다: %s — 로컬 페이지는 멀쩡해 보인다"
                         % "; ".join(bad[:5]))
            print("  FAIL 발행본 구조 %d건: %s" % (len(bad), "; ".join(bad[:5])))
        else:
            print("  OK   발행본 구조 정상 (회차 %d개 각각 펼침·버튼 1개)" % len(keep))
    except Exception as e:
        print("  --   발행본 구조 점검 건너뜀: %s" % e)

    # ── 시스템정리 HTML 이 낡았나 ─────────────────────────────────────
    # 「문서 수정하면 저 HTML 도 같이 고쳐라」를 사람 기억에 맡기지 않는다.
    # 원천 파일 해시가 문서 안 스탬프와 다르면 여기서 FAIL 이 난다.
    print()
    try:
        import sysdoc as SD
        cur, want = SD.current_stamp_in_doc(), SD.stamp()
        if cur is None:
            fails.append("[문서] %s 이 없다 - python tools/sysdoc.py" % SD.NAME)
            print("  FAIL %s 이 없다" % SD.NAME)
        elif cur != want:
            fails.append("[문서] %s 이 낡았다 - python tools/sysdoc.py 로 다시 만든다" % SD.NAME)
            print("  FAIL %s 이 낡았다 (%s != %s)" % (SD.NAME, cur, want))
            print("       원천이 바뀌었다 - python tools/sysdoc.py")
        else:
            print("  OK   %s 최신 (스탬프 %s)" % (SD.NAME, cur))
    except Exception as e:
        print("  --   시스템정리 점검 건너뜀: %s" % e)

    print("\n" + "=" * 60)
    if fails:
        print(f"FAIL {len(fails)}건")
        for f in fails:
            print("  - " + f)
        sys.exit(1)
    print("PASS — 레퍼런스 2건이 각 축 상위에 있고 두 축 재고가 살아 있다")


if __name__ == "__main__":
    main()
