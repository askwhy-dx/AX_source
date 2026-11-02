# -*- coding: utf-8 -*-
"""접전 구간 축 판정 — 낱말 점수가 못 가르는 것만 LLM 에게. (2026-09-11 신설)

  python tools/axis_llm.py                 # 접전분 판정 → 축지정.csv 기록 → 원장 반영
  python tools/axis_llm.py --dry-run       # 판정만 보고 아무것도 안 쓴다
  python tools/axis_llm.py --margin 6      # 접전 폭을 넓힌다 (기본 4)
  python tools/axis_llm.py --all           # 원장 전체를 다시 판정 (비싸다)

## 왜 필요한가 — 「만드는 법」이 한국어 유튜브 제목의 관용구다
낱말표에서 **만들·만드는·제작·구축·개발이 각 +6점**을 먹는데, 이 말은 실무 영상 제목에
거의 다 붙는다. 그래서 **데이터를 모아 읽는 영상까지 생성축으로 끌려간다.**

  · 「엑셀 보고서 자동화 … 실시간 웹 **대시보드**」   분석 13 vs 생성 18 → 생성
  · 「구글시트 실시간 **대시보드** 만드는 법」        분석  6 vs 생성 20 → 생성
  · 「엑셀 파일 **취합** + **검색** 자동화 보고서」    분석 10 vs 생성 13 → 생성

2026-09-11 실측 — 발굴 42채널에서 게이트를 넘은 66건의 축 분포가
**분석 5 / 생성 51 / 미분류 10**(분석 7.6%)이었다. 채널을 더 넣어도 이 비율이면 목표에 못 간다.
낱말표 보정(A+B안)으로는 월 1.17 → 1.67건에 그치고 **오탐까지 생겼다**
(「캡컷 영상 편집 40분 완벽 정리」가 분석축으로 넘어왔다).
그래서 **접전 구간만 문맥으로 가른다.**

## 어디에 쓰나 — 기존 「축지정」 통로를 그대로 쓴다
판정 결과를 `out/pool/축지정.csv` 에 적는다. 사람이 손으로 뒤집던 바로 그 파일이라
**되돌리기 쉽고 근거가 남는다.** 사유에 `LLM:` 을 붙여 사람 판정과 구분한다.

⚠️ **사람 판정이 이긴다.** 사유가 `LLM:` 으로 시작하지 않는 행은 건드리지 않는다.
⚠️ **접전만 본다.** 점수차가 큰 건 낱말표가 이미 맞히고 있고, 전부 넘기면 비싸기만 하다.
"""
import argparse, csv, io, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect as C
import llm as L

MARGIN = 4                     # |분석점수 − 생성점수| 가 이 이하면 접전으로 본다
CACHE = os.path.join(C.POOL, "llm_axis")
BATCH = 40                     # 한 번에 넘길 건수 — 프롬프트가 너무 길면 판정이 흐려진다


def contested(rows, margin, everything=False):
    out = []
    for r in rows:
        try:
            a, c = int(r["분석점수"] or 0), int(r["생성점수"] or 0)
        except ValueError:
            continue
        if everything or r["축"] == "미분류" or abs(a - c) <= margin:
            out.append(r)
    return out


EXCL_FIELDS = ["영상ID", "사유"]


def load_excl_rows():
    p = C.EXCLUDE_CSV
    if not os.path.exists(p):
        return []
    return list(csv.DictReader(io.open(p, encoding="utf-8-sig")))


def save_excl_rows(rows):
    os.makedirs(C.POOL, exist_ok=True)
    with io.open(C.EXCLUDE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EXCL_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


KEEP_CSV = os.path.join(C.POOL, "심사복구.csv")


def load_keep():
    """사람이 되살린 것 — **다시는 제외하지 않는다.** 안 그러면 매주 LLM 이 또 뺀다."""
    if not os.path.exists(KEEP_CSV):
        return set()
    return {r["영상ID"] for r in csv.DictReader(io.open(KEEP_CSV, encoding="utf-8-sig"))}


def add_keep(vids):
    old = load_keep()
    os.makedirs(C.POOL, exist_ok=True)
    with io.open(KEEP_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["영상ID"])
        w.writeheader()
        w.writerows([{"영상ID": v} for v in sorted(old | set(vids))])


def load_override_rows():
    p = C.OVERRIDE_CSV
    if not os.path.exists(p):
        return []
    return list(csv.DictReader(io.open(p, encoding="utf-8-sig")))


def save_override_rows(rows):
    os.makedirs(C.POOL, exist_ok=True)
    with io.open(C.OVERRIDE_CSV, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["영상ID", "축", "사유"])
        w.writeheader()
        w.writerows(rows)


def judge(batch, cache_dir, tag):
    lines = []
    for r in batch:
        desc = (r.get("설명") or "").replace("\n", " ")[:160]
        lines.append(f"- {r['영상ID']} | {r['제목'][:90]}\n    설명: {desc}")
    prompt = f"""{L.concept()}

---

# 할 일

아래 영상들은 **낱말 점수로는 분석축과 생성축이 갈리지 않는 것들**이다.
제목과 설명을 읽고 **둘 중 하나로** 판정하라.

**판정 기준은 위 컨셉의 「판정 기준」 절에 있다.** 그 절대로 판정하라 —
①사례인가(아니면 `"제외"`) ②분석/생성 ③우리 회사에서 옮길 자리가 있나.

# 후보 {len(batch)}건

{chr(10).join(lines)}

# 출력

JSON 하나만. 설명 문장 없이.

{{"판정": [
  {{"영상ID": "<위 목록에 있는 ID 그대로>", "축": "분석|생성|제외", "이유": "<결과물이 무엇인지 한 문장>"}}
]}}"""
    data = L.ask(prompt, cache_dir, tag)
    if not isinstance(data, dict):
        return {}
    ids = {r["영상ID"] for r in batch}
    out = {}
    for d in (data.get("판정") or []):
        vid = str((d or {}).get("영상ID", "")).strip()
        ax = str((d or {}).get("축", "")).strip()
        if vid in ids and ax in ("분석", "생성", "제외"):
            out[vid] = (ax, str(d.get("이유", ""))[:90])
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--margin", type=int, default=MARGIN)
    p.add_argument("--all", action="store_true", help="원장 전체 재판정")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--restore", nargs="+", metavar="영상ID",
                   help="LLM 이 제외한 것을 되살린다 (다시는 제외되지 않는다)")
    a = p.parse_args()

    # ── 되돌리기 (C안) ────────────────────────────────────────────────
    if a.restore:
        rows = load_excl_rows()
        gone = [r for r in rows if r["영상ID"] in set(a.restore)]
        human = [r for r in gone if not (r.get("사유") or "").startswith("LLM:")]
        if human:
            print("⚠️ 사람이 넣은 제외는 안 건드립니다: "
                  + ", ".join(r["영상ID"] for r in human))
        drop = {r["영상ID"] for r in gone} - {r["영상ID"] for r in human}
        save_excl_rows([r for r in rows if r["영상ID"] not in drop])
        add_keep(drop)
        print(f"되살림 {len(drop)}건 · 다시 제외되지 않도록 {KEEP_CSV} 에 기록")
        print("다음: python tools/collect.py --rebuild")
        return

    if not L.available():
        sys.exit("LLM 을 못 부릅니다 (claude CLI 확인).")
    if not os.path.exists(C.POOL_CSV):
        sys.exit("원장이 없습니다.")

    rows = list(csv.DictReader(io.open(C.POOL_CSV, encoding="utf-8-sig")))
    human = {r["영상ID"] for r in load_override_rows()
             if not (r.get("사유") or "").startswith("LLM:")}
    excl_now = {r["영상ID"] for r in load_excl_rows()}
    kept_back = load_keep()

    # 이미 제외된 것·사람이 정한 것·되살린 것은 다시 묻지 않는다 (매주 같은 질문 방지)
    skip = human | excl_now | kept_back
    todo = [r for r in contested(rows, a.margin, a.all) if r["영상ID"] not in skip]
    print(f"원장 {len(rows)}건 · 접전 {len(todo)}건 (점수차 ≤{a.margin} 또는 미분류)"
          + (f" · 재심사 제외 {len(skip)}건" if skip else ""))
    if not todo:
        print("판정할 것이 없습니다.")
        return

    verdicts = {}
    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        got = judge(chunk, CACHE, f"축판정_{i//BATCH + 1:02d}")
        print(f"  [{i//BATCH + 1}] {len(chunk)}건 요청 → {len(got)}건 응답")
        verdicts.update(got)

    now = {r["영상ID"]: r["축"] for r in rows}
    title = {r["영상ID"]: r["제목"] for r in rows}
    flips = [(v, now.get(v), ax, why) for v, (ax, why) in verdicts.items()
             if ax != now.get(v)]

    print(f"\n판정 {len(verdicts)}건 · 바뀌는 것 {len(flips)}건")
    for v, old, new, why in sorted(flips, key=lambda x: (x[1] or "", x[2])):
        print(f"  {old:>3} → {new:<3}  {title.get(v, v)[:56]}")
        print(f"            {why}")

    to_a = sum(1 for _v, _o, n, _w in flips if n == "분석")
    to_g = sum(1 for _v, _o, n, _w in flips if n == "생성")
    to_x = sum(1 for _v, _o, n, _w in flips if n == "제외")
    print(f"\n  분석으로 +{to_a} · 생성으로 +{to_g} · **제외 {to_x}**")

    if a.dry_run:
        print("\n[dry-run] 아무것도 쓰지 않았습니다.")
        return

    # ── 축지정 — «기존을 유지하고» 이번 판정을 «병합» 한다 ──────────────
    # ⚠️ 2026-09-11 버그: 사람 행만 남기고 다시 쓰는 바람에, 배치가 두 번 돌자
    #    지난 LLM 판정 32건이 통째로 날아갔다. 재심사 방지(skip) 때문에 이번 verdicts
    #    에는 그것들이 없어서 복원되지도 않았다 — **에러 없이 조용히 사라졌다.**
    #    그러면 매주 강의가 후보로 되살아난다. 반드시 병합이어야 한다.
    by_id = {r["영상ID"]: r for r in load_override_rows()}
    for v, (ax, why) in verdicts.items():
        if ax == "제외":
            continue
        if v in human:
            continue                      # 사람 판정이 이긴다
        by_id[v] = {"영상ID": v, "축": ax, "사유": "LLM: " + why}
    keep = list(by_id.values())
    save_override_rows(keep)

    # ── 제외목록 자동 반영 (C안) ──────────────────────────────────────
    # 원장에서 지우지 않는다. catalog_rows() 가 이 파일을 읽어 «추천·기획에서만» 뺀다.
    ex_rows = load_excl_rows()            # ⚠️ 기존을 «전부» 유지한다 (위 주석 참조)
    ex_have = {r["영상ID"] for r in ex_rows}
    added = 0
    for v, (ax, why) in verdicts.items():
        if ax == "제외" and v not in ex_have and v not in kept_back:
            ex_rows.append({"영상ID": v, "사유": "LLM: " + why})
            added += 1
    save_excl_rows(ex_rows)

    print(f"\n기록 {C.OVERRIDE_CSV} ({len(keep)}행)")
    print(f"기록 {C.EXCLUDE_CSV} ({len(ex_rows)}행 · 이번에 +{added})")
    if added:
        print(f"\n⚠️ 제외 {added}건은 **원장에 그대로 남고 추천·기획에서만 빠진다.**")
        print(f"   되살리려면: python tools/axis_llm.py --restore <영상ID> ...")
    print("\n다음: python tools/collect.py --rebuild   ← 원장·카탈로그에 반영된다")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
