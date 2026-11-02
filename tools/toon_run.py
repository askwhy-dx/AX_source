# -*- coding: utf-8 -*-
"""인스타툰 굽기 도우미 — 붙여넣기·이름 짓기·정리를 없앤다. (2026-09-10 신설)

    python tools/toon_run.py --ax 분석      # 감시 시작 (Ctrl+C 로 끝)
    python tools/toon_run.py --ax 분석 --next   # 다음 장만 클립보드에
    python tools/toon_run.py --status           # 어디까지 됐나

사람이 하는 건 셋뿐이다 — **Ctrl+V → 엔터 → 그림 저장(다운로드)**.
나머지는 이 도구가 한다:

  · 다음 장 프롬프트를 **클립보드에 올린다** (1장은 전문, 2장부터 짧은 블록)
  · **다운로드 폴더를 감시**하다가 새 그림이 뜨면 `받은/NN.png` 로 옮긴다
  · 1:1 · 1080px 을 검사하고, 통과하면 **다음 장을 다시 클립보드에** 올린다
  · 1장이 들어오면 그게 **기준판**이라 2장부터 프롬프트에 자동으로 물린다

⚠️ **약관 때문에 브라우저는 건드리지 않는다.** ChatGPT 창을 스크립트로 조종하면
   자동화 금지 조항에 걸리고 제재 대상은 그 계정이다. 그래서 굽는 동작만 사람이 한다.
⚠️ 화풍·얼굴·배지 같은 **눈으로 보는 검사는 이 도구가 안 한다** — 파일로 남겨 두면
   대화에서 내가 본다(`config/인스타툰_마스터.md` 의 검사 기준 9항목).
"""
import argparse, io, json, os, shutil, subprocess, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_page as B
import collect as C

DOWNLOADS = os.path.join(os.path.expanduser("~"), "Downloads")
IMG = (".png", ".jpg", ".jpeg", ".webp")
MIN_PX = 1080
SETTLE = 1.2          # 다운로드가 끝났는지 보는 시간(초) — 커지는 중인 파일을 옮기면 깨진다


def clip(text):
    """클립보드에 올린다. ⚠️ clip.exe 는 한글이 깨진다 — PowerShell 로 UTF-8 파일을 태운다."""
    tmp = os.path.join(os.environ.get("TEMP", "."), "_toon_clip.txt")
    io.open(tmp, "w", encoding="utf-8").write(text)
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command",
                        f"Get-Content -Raw -Encoding UTF8 '{tmp}' | Set-Clipboard"],
                       check=True, capture_output=True)
        return True
    except Exception as e:
        print("  [클립보드 실패] " + str(e)[:60])
        return False


def paths(ax, d=None):
    out = os.path.join(B.out_dir(d), "toon", ax)
    return out, os.path.join(out, "받은")


def want_pages(ax, d=None):
    sp = os.path.join(B.out_dir(d), "T2_대본.json")
    sc = json.load(io.open(sp, encoding="utf-8")).get(ax) or {}
    return len([p for p in (sc.get("장") or []) if isinstance(p, dict)])


def done_pages(got_dir):
    if not os.path.isdir(got_dir):
        return set()
    out = set()
    for f in os.listdir(got_dir):                    # 이름은 자유, **숫자만** 본다
        if not f.lower().endswith(IMG):
            continue
        n = "".join(c for c in os.path.splitext(f)[0] if c.isdigit())
        if n:
            out.add(int(n[-2:]))
    return out


def prompt_for(ax, no):
    """1장은 전문(첨부와 함께), 2장부터는 짧은 블록."""
    out, _ = paths(ax)
    p = os.path.join(out, f"{no:02d}.txt") if no == 1 else os.path.join(out, "짧은", f"{no:02d}.txt")
    return io.open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def check(path):
    try:
        from PIL import Image
        w, h = Image.open(path).size
    except Exception as e:
        return [f"열지 못함: {str(e)[:40]}"]
    bad = []
    if abs(w - h) > 4:
        bad.append(f"정사각이 아님 {w}x{h}")
    if min(w, h) < MIN_PX:
        bad.append(f"작음 {min(w, h)}px < {MIN_PX}")
    return bad


def serve_next(ax, no, total):
    txt = prompt_for(ax, no)
    if not txt:
        print(f"  [없음] {ax} {no}장 프롬프트 — build_toon_prompt.py 를 먼저 도세요")
        return False
    clip(txt)
    kind = "전문 (첨부 4종과 함께 새 대화)" if no == 1 else "짧은 블록 (같은 대화에서 이어서)"
    print(f"\n  ── {ax} {no}/{total} 클립보드에 올렸습니다 · {kind}")
    for ln in txt.splitlines():
        # ⚠️ 「* 상단 제목 위치를 일관되게」 같은 규칙 줄이 아니라 **값이 붙은 줄**만 본다
        if ln.startswith(("* 상단 제목:", "* 말풍선:", "* 회차 표시:")):
            print("     " + ln)
    print("     Ctrl+V → 엔터 → 그림 나오면 다운로드")
    return True


def watch(ax):
    total = want_pages(ax)
    out, got = paths(ax)
    os.makedirs(got, exist_ok=True)
    done = done_pages(got)
    nxt = next((i for i in range(1, total + 1) if i not in done), None)
    if nxt is None:
        print(f"  {ax}: {total}장 다 찼습니다 — python tools/collect_toon.py")
        return 0
    serve_next(ax, nxt, total)

    seen = {f: os.path.getmtime(os.path.join(DOWNLOADS, f))
            for f in os.listdir(DOWNLOADS)} if os.path.isdir(DOWNLOADS) else {}
    print(f"  다운로드 폴더 감시 중… ({DOWNLOADS})   [Ctrl+C 로 끝]")
    while nxt is not None:
        time.sleep(1.2)
        try:
            now = os.listdir(DOWNLOADS)
        except OSError:
            continue
        fresh = [f for f in now if f.lower().endswith(IMG) and f not in seen]
        for f in fresh:
            src = os.path.join(DOWNLOADS, f)
            s1 = os.path.getsize(src); time.sleep(SETTLE)
            if not os.path.exists(src) or os.path.getsize(src) != s1:
                continue                      # 아직 받는 중
            dst = os.path.join(got, f"{nxt:02d}.png")
            shutil.move(src, dst)
            seen[f] = time.time()
            bad = check(dst)
            if bad:
                print(f"  ⚠️ {ax} {nxt:02d} 저장 — 기계 검사 걸림: " + " · ".join(bad))
                print("     (그래도 두었습니다. 다시 받으면 같은 이름으로 덮입니다)")
            else:
                print(f"  ✅ {ax} {nxt:02d} 저장 · 1:1 · {MIN_PX}px 이상")
            if nxt == 1:
                # 1장이 곧 **기준판**이다 — 2장부터 프롬프트에 물리게 다시 만든다
                subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__),
                                                             "build_toon_prompt.py"), "--ax", ax],
                               capture_output=True)
                print("     1장을 기준판으로 물렸습니다 — 2장부터 프롬프트에 들어갑니다")
            done.add(nxt)
            nxt = next((i for i in range(1, total + 1) if i not in done), None)
            if nxt is None:
                print(f"\n  {ax} {total}장 완료. 다음: python tools/collect_toon.py")
                return 0
            serve_next(ax, nxt, total)
        for f in now:
            seen.setdefault(f, time.time())
    return 0


def status():
    for ax in C.toon_axes(B.out_dir()):
        total = want_pages(ax)
        _, got = paths(ax)
        done = sorted(done_pages(got))
        miss = [i for i in range(1, total + 1) if i not in done]
        print(f"  {ax}: {len(done)}/{total}장" + (f" · 남은 장 {miss}" if miss else " · 완료"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ax", default=None, help="분석 / 생성")
    ap.add_argument("--next", action="store_true", help="다음 장만 클립보드에 (감시 안 함)")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status or not a.ax:
        status()
        if not a.ax:
            print("  쓰기: python tools/toon_run.py --ax 분석")
        return 0
    if a.next:
        total = want_pages(a.ax)
        _, got = paths(a.ax)
        done = done_pages(got)
        nxt = next((i for i in range(1, total + 1) if i not in done), None)
        if nxt is None:
            print(f"  {a.ax}: 다 찼습니다")
            return 0
        return 0 if serve_next(a.ax, nxt, total) else 1
    try:
        return watch(a.ax)
    except KeyboardInterrupt:
        print("\n  멈췄습니다. 이어서 하려면 같은 명령을 다시 도세요.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
