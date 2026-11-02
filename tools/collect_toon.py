# -*- coding: utf-8 -*-
"""구워 온 인스타툰을 회차에 꽂는다. (2026-09-10 신설)

    python tools/collect_toon.py          # 받은/ 을 훑어 정리 + 뷰어
    python tools/collect_toon.py --ax 분석
    python tools/collect_toon.py --check  # 검사만 (파일 안 건드림)

넣는 자리:  out/<회차>/toon/<축>/받은/01.png ... 12.png   (이름은 장 번호만 맞으면 된다)
나오는 것:  out/<회차>/T2_정보채널_<축>_<회차>.png        1장(표지)
            out/<회차>/T2_정보채널_<축>_<회차>_02.png ~    2장부터
            out/<회차>/T2_정보채널_<축>_<회차>.html        넘겨보는 뷰어

## 왜 이름을 굳이 바꾸나
「회차별 보기」 칩이 **이 이름을 찾는다**(`build_page.past_rounds`). 이름이 한 글자만
달라도 칩이 안 생기는데 **에러는 안 난다** — 페이지는 멀쩡하고 그 회차만 조용히 빈다.
그래서 사람이 받은 파일 이름은 자유롭게 두고, 여기서 규약으로 옮긴다.

## 검사하는 것 (에러 없이 틀리는 자리)
  · 장 수가 대본과 같은가        — 한 장 빠뜨리면 캐러셀이 그 자리서 끊긴다
  · 정사각인가                   — 인스타는 1:1 밖이면 잘라 버린다
  · 1080px 이상인가              — 작으면 글자가 뭉갠다
"""
import argparse, io, json, os, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_page as B
import collect as C

MIN_PX = 1080


def got_dir(out_d, ax):
    return os.path.join(out_d, "toon", ax, "받은")


def scan(d):
    """받은/ 안의 그림을 장 번호로 줍는다. {번호: 경로}"""
    out = {}
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
            continue
        digits = "".join(ch for ch in os.path.splitext(f)[0] if ch.isdigit())
        if not digits:
            continue
        n = int(digits[-2:]) if len(digits) >= 2 else int(digits)
        if 1 <= n <= 30:
            out[n] = os.path.join(d, f)
    return out


def check(path):
    """(가로, 세로, 문제 목록)"""
    try:
        from PIL import Image
        w, h = Image.open(path).size
    except Exception as e:
        return 0, 0, [f"열지 못함: {str(e)[:40]}"]
    bad = []
    if abs(w - h) > 4:
        bad.append(f"정사각이 아니다 ({w}x{h})")
    if min(w, h) < MIN_PX:
        bad.append(f"작다 ({min(w, h)}px < {MIN_PX})")
    return w, h, bad


VIEW = """<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title><style>
html,body{height:100%%;margin:0;background:#E9EAE4;font:14px/1.6 "Pretendard","Malgun Gothic",sans-serif}
#stage{position:fixed;inset:0 0 62px;display:flex;align-items:center;justify-content:center}
#deck{position:relative;width:min(92vmin,900px);aspect-ratio:1/1;background:#F7F0DF;
  box-shadow:0 24px 70px rgba(20,30,35,.28)}
.slide{position:absolute;inset:0;display:none}.slide.on{display:block}
.slide img{width:100%%;height:100%%;object-fit:contain;display:block}
#bar{position:fixed;left:0;right:0;bottom:0;height:62px;display:flex;align-items:center;
  justify-content:center;gap:14px;background:#fff;border-top:1px solid #d8d8d2}
button{font:inherit;border:1px solid #cfcfc8;background:#fff;border-radius:8px;
  padding:7px 15px;cursor:pointer}
#no{font-variant-numeric:tabular-nums;color:#666}
</style></head><body>
<div id="stage"><div id="deck">%(slides)s</div></div>
<div id="bar"><button id="p">← 이전</button><span id="no"></span><button id="n">다음 →</button></div>
<script>
var i=0,S=document.querySelectorAll('.slide');
function go(k){i=(k+S.length)%%S.length;S.forEach(function(s,j){s.classList.toggle('on',j===i);});
  document.getElementById('no').textContent=(i+1)+' / '+S.length;}
document.getElementById('n').onclick=function(){go(i+1)};
document.getElementById('p').onclick=function(){go(i-1)};
document.addEventListener('keydown',function(e){
  if(e.key==='ArrowRight')go(i+1); if(e.key==='ArrowLeft')go(i-1);});
document.getElementById('deck').onclick=function(){go(i+1)};
go(0);
</script></body></html>"""


def build_viewer(paths, title, out_html):
    """뷰어 — 파일을 **참조**한다(내장 아님). 같은 폴더에 PNG 가 같이 있어야 열린다."""
    slides = "".join(
        '<div class="slide%s"><img src="%s" alt="%d"></div>'
        % (" on" if k == 0 else "", os.path.basename(p), k + 1)
        for k, p in enumerate(paths))
    io.open(out_html, "w", encoding="utf-8").write(VIEW % {"title": title, "slides": slides})


def check_size(path):
    """(가로, 세로). 못 열면 (0, 0)."""
    try:
        from PIL import Image
        return Image.open(path).size
    except Exception:
        return 0, 0


def run_axis(ax, d, out_d, want, do_write, up=False):
    got = scan(got_dir(out_d, ax))
    if not got:
        print(f"  {ax}: 받은/ 이 비어 있습니다 — 아직 굽지 않았습니다")
        return False
    if up:
        big = max((check_size(g)[0] for g in got.values()), default=0)
        for n, f in sorted(got.items()):
            w, h = check_size(f)
            if w and w < big:
                from PIL import Image
                keep = os.path.join(os.path.dirname(f), "원본_저해상")
                os.makedirs(keep, exist_ok=True)
                shutil.copyfile(f, os.path.join(keep, os.path.basename(f)))
                Image.open(f).convert("RGB").resize((big, big), Image.LANCZOS).save(f)
                print(f"       {ax} {n:02d} {w}px → {big}px 로 올림 (원본은 원본_저해상/)")

    miss = [n for n in range(1, want + 1) if n not in got]
    extra = [n for n in got if n > want]
    bad_any = False
    for n in sorted(got):
        w, h, bad = check(got[n])
        if bad:
            bad_any = True
            print(f"  FAIL {ax} {n:02d}: " + " · ".join(bad))
    if miss:
        print(f"  FAIL {ax}: {len(miss)}장 빠짐 {miss} (대본 {want}장)")
    if extra:
        print(f"  ⚠️ {ax}: 대본에 없는 장 {extra} — 무시합니다")
    if miss or bad_any:
        return False
    if not do_write:
        print(f"  OK   {ax} {want}장 · 정사각 · {MIN_PX}px 이상")
        return True

    base = B.t2_path(d, ax)                     # T2_정보채널_<축>_<회차>.png
    stem, ext = os.path.splitext(base)
    outs = []
    for n in range(1, want + 1):
        dst = base if n == 1 else f"{stem}_{n:02d}{ext}"
        shutil.copyfile(got[n], dst)
        outs.append(dst)
    build_viewer(outs, f"{ax} 인스타툰 {want}장", stem + ".html")
    # PDF — 검토·보관용 한 파일. ⚠️ 게시물은 어디까지나 PNG 낱장이다.
    #    PIL 의 여러 쪽 PDF 는 판형을 그대로 담는다(1:1 이 안 깨진다).
    try:
        from PIL import Image
        ims = [Image.open(f).convert("RGB") for f in outs]
        # ⚠️ Pillow 12 부터는 형식을 **명시**해야 한다 — 확장자만 보고 저장하면 'JPEG' 로 죽는다
        ims[0].save(stem + ".pdf", "PDF", save_all=True, append_images=ims[1:], quality=92)
        print(f"       PDF {os.path.basename(stem)}.pdf ({len(ims)}쪽)")
    except Exception as e:
        print("       [PDF 실패] " + str(e)[:60])
    print(f"  OK   {ax} {want}장 → {os.path.basename(base)} 외 · 뷰어 {os.path.basename(stem)}.html")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ax", default=None)
    ap.add_argument("--check", action="store_true", help="검사만 한다")
    ap.add_argument("--upscale", action="store_true",
                    help="규격 미달 장을 가장 큰 장 크기로 올린다 (원본은 따로 보관)")
    a = ap.parse_args()

    from datetime import date
    d = date.today()
    out_d = B.out_dir(d)
    sp = os.path.join(out_d, "T2_대본.json")
    if not os.path.exists(sp):
        print("  [건너뜀] T2_대본.json 이 없습니다 — 몇 장인지 알 수 없습니다.")
        return 1
    sc_all = json.load(io.open(sp, encoding="utf-8"))

    ok = True
    for ax in ([a.ax] if a.ax else list(C.toon_axes(out_d))):
        sc = sc_all.get(ax) or {}
        want = len([p for p in (sc.get("장") or []) if isinstance(p, dict)])
        if not want:
            print(f"  [건너뜀] {ax}축 대본이 없습니다.")
            continue
        ok = run_axis(ax, d, out_d, want, not a.check, a.upscale) and ok
    if ok and not a.check:
        # 두 편이 다 꽂혔으면 게시판 글 문구도 같이 낸다. 붙여넣기만 하면 되도록.
        # 한 축만 정리한 경우(--ax)는 건너뛴다 — 글은 두 편을 같이 소개한다.
        if not a.ax:
            try:
                import build_board_post as P
                P.main(["--round", os.path.basename(out_d)])
            except SystemExit as e:
                print(f"  [게시판글 건너뜀] {e}")
        print("  다음: python tools/build_page.py  — 회차별 보기 칩이 이 파일들을 엽니다")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
