# -*- coding: utf-8 -*-
"""인스타툰 장별 프롬프트 — 굽기 직전까지 기계가 차려 준다. (2026-09-10 신설)

    python tools/build_toon_prompt.py            # 이번 회차 24장
    python tools/build_toon_prompt.py --ax 분석  # 한 축만
    python tools/build_toon_prompt.py --no-llm   # 연출 칸 없이 틀만

산출: out/<회차>/toon/<축>/01.txt ~ 12.txt   ChatGPT 에 그대로 붙이는 프롬프트
      out/<회차>/toon/<축>/전체.md            한 파일로 훑어보는 판
      out/<회차>/toon/첨부.md                 무엇을 어떤 순서로 첨부하나

## 왜 이 도구가 있나
**그림은 사람이 ChatGPT 창에서 굽는다.** codex 는 코딩 에이전트라 그림을 못 만들고
이 PC 엔 이미지 API 키가 없다. 그래서 파이프라인이 하는 일은 두 가지다 —
**붙일 것을 다 차려 놓기**(이 파일)와 **받아 온 그림을 회차에 꽂기**(collect_toon.py).

## 어디서 오나
  · 원고(제목·말풍선)   out/<회차>/T2_대본.json   ← 기획서 §4 에 실려 나간 그 문장
  · 그림 규칙           config/인스타툰_마스터.md  ← **프롬프트 정본. 고칠 자리는 여기다**
  · 연출 세 칸          llm.write_toon_direction() ← 화면문구·메모문구·장면설명

⚠️ **마스터를 코드에 복사해 두지 않는다.** 두 곳에 있으면 갈린다 — 이 폴더가 그걸로
   여러 번 데였다. 프롬프트 문장을 고치려면 `config/인스타툰_마스터.md` 만 고친다.
"""
import argparse, io, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_page as B
import collect as C
import llm as L

MASTER = os.path.join(C.ROOT, "config", "인스타툰_마스터.md")
REF_DIR = os.path.join(C.ROOT, "assets", "인스타툰", "레퍼런스_판")
CHAR = os.path.join(C.ROOT, "assets", "인스타툰", "캐릭터", "유삐_캐릭터시트.png")
GUIDE_DIR = os.path.join(C.ROOT, "assets", "인스타툰", "품질가이드")


def guide_files():
    """품질 가이드 — **이 정도 완성도를 내라**는 목표 그림(우리 캐릭터). 매 회차 붙인다."""
    if not os.path.isdir(GUIDE_DIR):
        return []
    return [os.path.join(GUIDE_DIR, f) for f in sorted(os.listdir(GUIDE_DIR))
            if f.lower().endswith(".png")]


def anchor_file(out_dir, ax):
    """**이번 회차에서 승인한 1장.** 2장부터 붙어 회차 안의 톤을 고정한다.

    ⚠️ 품질가이드와 다른 것이다 — 가이드는 목표 수준, 기준판은 이번 시리즈의 실제 1장.
       승인 전에는 없다(그래서 1장 프롬프트엔 안 들어간다).
    """
    # ⚠️ 이름을 강제하지 않는다. 사람이 「분석_01.png」로 받아 두는 일이 실제로 있었다 —
    #    숫자만 뽑아 1장을 찾는다.
    d = os.path.join(out_dir, ax, "받은")
    if not os.path.isdir(d):
        return ""
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        n = "".join(c for c in os.path.splitext(f)[0] if c.isdigit())
        if n and int(n[-2:]) == 1:
            return os.path.join(d, f)
    return ""


def master_prompt():
    """마스터에서 PROMPT_START ~ PROMPT_END 사이만 뽑는다."""
    t = io.open(MASTER, encoding="utf-8").read()
    a = t.index("## PROMPT_START") + len("## PROMPT_START")
    b = t.index("## PROMPT_END")
    return t[a:b].strip()


def text_block(p, no, total, dirs):
    """「텍스트는 아래 내용을 정확하게 반영해줘」 아래 붙는 줄들.

    ⚠️ **빈 칸은 줄째로 뺀다.** 「말풍선: 없음」이라고 적으면 그 글자가 판에 박힌다 —
       제작기준이 예시에서 빈 따옴표를 남겨 둔 자리가 그 위험이다.
    """
    rows = []
    title = (p.get("제목") or "").replace(chr(10), " ").strip()
    say = (p.get("말") or "").replace(chr(10), " ").strip()
    if title:
        rows.append(f'* 상단 제목: "{title}"')
    rows.append(f'* 회차 표시: "{no}/{total}"')
    if say:
        rows.append(f'* 말풍선: "{say}"')
    # ⚠️ **대본에 적은 연출이 이긴다**(2026-09-18 신설). 표지처럼 구도를 고정해야 하는
    #    장이 있는데, LLM 연출은 회차마다 새로 써서 **같은 표지가 매번 달라진다.**
    #    대본 칸이 비어 있을 때만 LLM 값을 쓴다.
    d = dirs.get(no) or {}
    screen = p.get("화면문구") or d.get("화면문구")
    memo = p.get("메모문구") or d.get("메모문구")
    if screen:
        rows.append(f'* 노트북/모니터 화면 문구: "{screen}"')
    if memo:
        rows.append(f'* 메모장/포스트잇 문구: "{memo}"')
    return chr(10).join(rows)


def scene_text(p, no, dirs):
    """이번 장면 설명. LLM 이 못 채웠으면 원고에서 최소한으로 만든다."""
    # 대본 > LLM > 원고 자동생성 (2026-09-18 — 위 text_block 과 같은 이유)
    d = p.get("장면설명") or (dirs.get(no) or {}).get("장면설명", "")
    if d:
        return d
    who = "유삐와 회색 곰 상사가 마주 선 장면. " if p.get("할아버지") else "유삐가 "
    line = (p.get("제목") or p.get("말") or "").replace(chr(10), " ").strip()
    if p.get("종류") == "표지":
        return f"{who}표지 장면. 「{line}」라고 묻는 상황이 한눈에 보이게, 책상과 노트북 정도로 단순하게."
    if p.get("종류") == "댓글":
        return f"{who}밝게 웃으며 마무리하는 장면. 광고 배너처럼 보이지 않게 인스타툰 톤으로."
    return f"{who}「{line}」 상황을 겪는 장면. 표정과 손동작으로 감정이 드러나게, 소품은 서너 개까지."


def delta_block(p, no, total, dirs):
    """2장부터 쓰는 **짧은 블록**. 첨부·규칙은 대화 첫 장에서 이미 줬다.

    ⚠️ 「같은 시리즈·같은 화풍」을 매번 다시 못 박는다 — 대화가 길어지면 모델이
       앞 규칙을 흘린다. 실제로 이 계통에서 5장쯤부터 톤이 미끄러지는 일이 흔하다.
    """
    L = ["다음 장을 같은 방식으로 그려줘. **앞 장과 같은 시리즈**다 — 화풍·선 굵기·색감·",
         "제목 위치·우측 상단 배지 모양·유삐 얼굴을 **그대로** 유지해라.", ""]
    L.append(text_block(p, no, total, dirs))
    L += ["", "이번 장면 설명:", scene_text(p, no, dirs), "",
          "카드뉴스나 템플릿처럼 보이지 않게, 한 컷 전체를 완성된 일러스트로.",
          "글씨는 크고 선명하게.",
          # ⚠️ 1장에서 배운 것(2026-09-10): 소품을 열거하면 배경이 빽빽해져 「여백이 많고
          #    정돈된 한 컷」이 깨진다. 그리고 판 테두리는 **첫 장이 정한 대로** 끌고 간다.
          "소품은 이 장면에 꼭 필요한 서넛까지만. 나머지는 여백으로 둬라.",
          "판 테두리(프레임) 유무도 앞 장과 똑같이 유지해라."]
    return chr(10).join(L)


def build_axis(ax, sc, out_dir, chosen, use_llm=True):
    pages = [p for p in (sc.get("장") or []) if isinstance(p, dict)]
    total = len(pages)
    dirs = {}
    if use_llm and L.available():
        dirs = L.write_toon_direction(ax, pages, B.llm_dir(), chosen)
    d = os.path.join(out_dir, ax)
    os.makedirs(d, exist_ok=True)
    tmpl = master_prompt()
    anc = anchor_file(out_dir, ax)
    mark = "* 첨부한 유삐 캐릭터 이미지는 주인공 캐릭터 디자인 기준이다."
    extra = []
    if guide_files():
        extra.append("* 첨부한 **품질 가이드 이미지**는 «이 정도 완성도를 내라»는 목표다. "
                     "우리 유삐로 그려진 예시이며 화풍·채색·글자 크기·소품 밀도의 **목표 수준**이다. "
                     "장면 내용은 이번 지시를 따르되, **완성도는 이 그림 이상**이어야 한다.")
    if anc:
        extra.append("* 첨부한 **기준판 이미지(이번 시리즈의 1장)** 는 이 시리즈의 최종 기준이다. "
                     "화풍·선 굵기·색감·제목 글자체와 위치·우측 상단 배지 모양·유삐 얼굴을 "
                     "**이 그림에 맞춰라.** 레퍼런스와 기준판이 다르면 기준판을 따른다.")
    if extra:
        i = tmpl.index(mark); j = tmpl.index(chr(10), i)
        tmpl = tmpl[:j] + chr(10) + chr(10).join(extra) + tmpl[j:]
    whole = [f"# {ax}축 인스타툰 {total}장 — 장별 프롬프트", "",
             f"첨부물은 `첨부.md` 참고. **1장을 먼저 굽고** 마음에 들면 2장부터 순차로 간다.", ""]
    for i, p in enumerate(pages, 1):
        txt = (tmpl.replace("{회차표시}", f"{i}/{total}")
                   .replace("{텍스트블록}", text_block(p, i, total, dirs))
                   .replace("{장면설명}", scene_text(p, i, dirs)))
        io.open(os.path.join(d, f"{i:02d}.txt"), "w", encoding="utf-8").write(txt + chr(10))
        if i > 1:      # 2장부터는 짧은 블록도 같이 (한 대화에서 이어 굽는 길)
            os.makedirs(os.path.join(d, "짧은"), exist_ok=True)
            io.open(os.path.join(d, "짧은", f"{i:02d}.txt"), "w",
                    encoding="utf-8").write(delta_block(p, i, total, dirs) + chr(10))
        head = (p.get("제목") or p.get("말") or "").replace(chr(10), " ")
        body = txt if i == 1 else delta_block(p, i, total, dirs)
        tag = "전문(첫 장 · 첨부와 함께)" if i == 1 else "짧은 블록(같은 대화에서 이어서)"
        whole += [f"## {i}/{total} — {head}", f"*{tag}*", "", "```", body, "```", ""]
    io.open(os.path.join(d, "전체.md"), "w", encoding="utf-8").write(chr(10).join(whole))
    return total, len(dirs)


def gather_attachments(out_dir, d):
    """붙일 파일을 `toon/첨부물/` 에 **번호를 붙여** 복사한다. (2026-09-10 신설)

    ⚠️ 경로 네 군데(회차 폴더·레퍼런스_판·캐릭터·품질가이드)에 흩어져 있으면 첨부할 때마다
       탐색기를 네 번 연다. 굽는 사람은 **폴더 하나만 열어 전부 끌어다 놓으면** 된다.
    ⚠️ 링크가 아니라 **복사**다. 회차가 지나도 그때 무엇을 붙였는지 그대로 남는다 —
       레퍼런스나 품질가이드를 나중에 갈아도 지난 회차 기록은 안 흔들린다.
    """
    import shutil
    dst = os.path.join(out_dir, "첨부물")
    os.makedirs(dst, exist_ok=True)
    n = 0
    brief = os.path.join(B.out_dir(d), f"기획서_{B.round_day(d):%Y%m%d}.pdf")
    if os.path.exists(brief):
        shutil.copyfile(brief, os.path.join(dst, "1_" + os.path.basename(brief))); n += 1
    if os.path.isdir(REF_DIR):
        for f in sorted(os.listdir(REF_DIR)):
            if f.lower().endswith(".png"):
                shutil.copyfile(os.path.join(REF_DIR, f),
                                os.path.join(dst, f"2_레퍼런스_{f}")); n += 1
    if os.path.exists(CHAR):
        shutil.copyfile(CHAR, os.path.join(dst, "3_캐릭터_유삐.png")); n += 1
    for k, g in enumerate(guide_files(), 1):
        shutil.copyfile(g, os.path.join(dst, f"4_품질가이드_{k:02d}.png")); n += 1
    return dst, n


def write_attach(out_dir, d, anchor=""):
    refs = sorted(f for f in os.listdir(REF_DIR) if f.endswith(".png")) if os.path.isdir(REF_DIR) else []
    brief = os.path.join(B.out_dir(d), f"기획서_{B.round_day(d):%Y%m%d}.pdf")
    anchor = os.path.relpath(anchor, C.ROOT).replace(os.sep, "/") if anchor else "아직 없음 — 1장을 승인하면 생긴다"
    box, n = gather_attachments(out_dir, d)
    rel = os.path.relpath(box, C.ROOT).replace(os.sep, "/")
    io.open(os.path.join(out_dir, "첨부.md"), "w", encoding="utf-8").write(f"""# 첨부물 — 이 폴더 하나만 열면 된다

    {rel}/          ({n}개)

ChatGPT **새 대화**를 열고 이 폴더의 파일을 **전부 끌어다 놓은 뒤**, 장별 프롬프트를 붙인다.

| 번호 | 무엇 | 몇 개 |
|---|---|---|
| `1_` | 기획서 PDF (원고) | 1 |
| `2_` | 레퍼런스 (화풍) | {len(refs)} |
| `3_` | 캐릭터 시트 (유삐 디자인) | 1 |
| `4_` | 품질 가이드 («이 정도 완성도») | {len(guide_files())} |

⚠️ 레퍼런스는 **판만 잘라 낸 것**이다. 원본 스크린샷(`assets/인스타툰/레퍼런스/`)을 붙이면
계정명·좋아요 아이콘까지 그림에 따라 들어간다.

## 프롬프트

    {os.path.relpath(out_dir, C.ROOT).replace(os.sep, "/")}/<축>/01.txt        1장 — 전문
    {os.path.relpath(out_dir, C.ROOT).replace(os.sep, "/")}/<축>/짧은/02~12.txt  2장부터 — 8줄 블록
    {os.path.relpath(out_dir, C.ROOT).replace(os.sep, "/")}/<축>/전체.md         12개를 한 파일로

**1장을 먼저 굽고** 마음에 들면 2장부터 순차로 간다. 축이 바뀌면 같은 방식으로 다시 1장부터.
1장이 나오면 `<축>/받은/01.png` 로 저장하고 `python tools/build_toon_prompt.py --ax <축>` 을
한 번 돌리면, **그 1장이 기준판으로 2~12장 프롬프트에 물린다.**

## 받은 그림 두는 자리

    {os.path.relpath(out_dir, C.ROOT).replace(os.sep, "/")}/<축>/받은/01.png ... 12.png

다 채우면 `python tools/collect_toon.py` — 이름 규약대로 정리하고 뷰어를 만든다.
""")
    return brief, len(refs)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ax", default=None, help="한 축만 (분석/생성)")
    ap.add_argument("--no-llm", action="store_true", help="연출 칸 없이 틀만")
    ap.add_argument("--llm-refresh", action="store_true")
    a = ap.parse_args()
    L.enable(not a.no_llm, a.llm_refresh)

    from datetime import date
    d = date.today()
    out_d = os.path.join(B.out_dir(d), "toon")
    os.makedirs(out_d, exist_ok=True)

    sp = os.path.join(B.out_dir(d), "T2_대본.json")
    if not os.path.exists(sp):
        print("  [건너뜀] T2_대본.json 이 없습니다 — 원고가 먼저입니다.")
        return 1
    sc_all = json.load(io.open(sp, encoding="utf-8"))
    ses = B.session()
    chosen = ses.get("chosen")

    # 체험 회차는 「체험」 한 편뿐이다 — 대본이 편 목록을 정한다(2026-09-18).
    axes = [a.ax] if a.ax else list(C.toon_axes(B.out_dir(d)))
    for ax in axes:
        sc = sc_all.get(ax)
        if not isinstance(sc, dict):
            print(f"  [건너뜀] {ax}축 대본이 없습니다.")
            continue
        n, nd = build_axis(ax, sc, out_d, chosen, not a.no_llm)
        print(f"  {ax} {n}장 · 연출 {nd}장 채움 → out/{B.round_day(d):%Y%m%d}/toon/{ax}/")
    brief, nref = write_attach(out_d, d, anchor_file(out_d, axes[0]))
    print(f"  첨부 — 기획서 {'있음' if os.path.exists(brief) else '**없음**'} · "
          f"레퍼런스 {nref}장 · 캐릭터 {'있음' if os.path.exists(CHAR) else '**없음**'}")
    print(f"  다음: out/{B.round_day(d):%Y%m%d}/toon/첨부.md 를 열고 1장부터 굽습니다.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
