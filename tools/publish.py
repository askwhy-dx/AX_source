# -*- coding: utf-8 -*-
"""
publish.py — 소재추천 페이지와 그 회차 산출물(T1·T2·기획서)을 GitHub Pages 로 발행한다.

  로컬                                   →  원격 (jichang999-dotcom/tes2)
  소재추천.html                          →  axs/<slug>/소재추천.html
  out/<회차>/기획서_<회차>.pdf           →  axs/<slug>/out/<회차>/...
  out/<회차>/T1_부서장회의_<회차>.html   →  axs/<slug>/out/<회차>/...
  out/<회차>/T2_정보채널_<축>_<회차>.html→  axs/<slug>/out/<회차>/...
  out/<회차>/T2_..._NN.png  →(1080 JPEG)→  axs/<slug>/out/<회차>/..._NN.jpg

사용
----
  python tools/publish.py --dry-run     # 무엇이 올라가는지만 (업로드 없음)
  python tools/publish.py               # 발행 (승인된 최신 회차)
  python tools/publish.py --plan        # 승인 전 기획 단계 — 기획서만 올린다(수요일 배치)
  python tools/publish.py --round 20260909
  python tools/publish.py --url         # 공개 URL 만 찍는다

왜 이 구조인가
--------------
`소재추천.html` 은 T1·T2·기획서를 **상대경로** `out/<회차>/...` 로 연다. 그래서
`out/` 의 상대 위치를 로컬과 똑같이 올린다. 경로를 예쁘게 만들려고 발행 때 HTML 의
링크를 고쳐 쓰면 **로컬에서 눈으로 확인한 것과 다른 파일이 서비스된다.**

⚠️ 이 리포는 **public** 이다. GitHub Pages 는 비공개 발행이 안 된다(Enterprise 전용).
   그래서 두 가지로만 가린다 — 둘 다 「검색에 안 뜬다」까지지 「못 본다」가 아니다:
   ① **추측 불가 경로** `axs/<slug>/` (slug 는 config/publish.json 에 한 번 만들어 고정)
   ② 발행본 HTML 에 **noindex 메타** 주입 (로컬 원본은 안 건드린다)
   ⚠️ **PDF·JPG 에는 메타를 못 넣는다.** 경로를 모르면 닿지 못할 뿐, 링크가 한 번
      밖으로 나가면 색인될 수 있다. URL 을 공개 채널에 붙이지 말 것.
   ⚠️ 리포 루트 `robots.txt` 는 **효력이 없다** — robots.txt 는 도메인 루트
      (`jichang999-dotcom.github.io/robots.txt`) 에 있어야 하고 그건 이 리포가 아니다.
      그래서 meta 주입이 유일한 실제 수단이다.

왜 PNG 를 JPEG 로 바꾸나
------------------------
T2 뷰어 HTML 은 **2.6KB 껍데기**고 실물은 PNG 12장×2축이다. 원본은 2048×2048 PNG 라
회차당 **93MB** 다. 리포가 이미 176MB 고 git 은 이력이 쌓여 **지워도 안 줄어든다** —
매주 쌓으면 1GB 한도에 몇 달이면 닿는다. 게다가 단테에서 **대량 이미지 PUT 이
API 실패(exit 255)** 로 터진 선례가 있다.
그래서 **발행본만** 인스타 규격 그대로 1080×1080 JPEG q85 로 줄인다(회차당 ~6MB).
**2048 원본 PNG 는 로컬에 그대로 남아** 실제 인스타 게시에 쓴다.

왜 파일별 PUT 이 아니라 Tree API 인가
------------------------------------
Contents API 는 **파일 하나당 커밋 하나**다. 30여 개면 중간에 하나 실패했을 때
**절반만 올라간 상태가 그대로 서비스된다.** Git Data API 는 blob 을 다 만든 뒤
트리·커밋을 한 번에 올리므로 실패하면 아무것도 안 바뀐다. (지역분석 선례)

⚠️ 이 리포 main 에는 **단테 대시보드가 스케줄로 푸시**한다. blob 올리는 동안 남이
   커밋하면 ref PATCH 가 422 "not a fast forward" 로 튕긴다 — 우리 파일은
   `axs/` 아래라 내용 충돌이 없으니 **최신 head 위에 다시 얹는다**(재시도 4회).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import io as _io
import json
import re
import secrets
import sys
import time
from pathlib import Path

import requests
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OWNER, REPO, BRANCH = "jichang999-dotcom", "tes2", "main"  # 공개 리포 (2026-09-17 tes1 에서 이전)
API = f"https://api.github.com/repos/{OWNER}/{REPO}"

PAGE = "소재추천.html"
JPEG_SIDE, JPEG_Q = 1080, 85

# 발행본에만 주입한다 — 로컬 원본은 안 건드린다
NOINDEX = ('<meta name="robots" '
           'content="noindex,nofollow,noarchive,nosnippet,noimageindex">')


# ── 경로 slug ───────────────────────────────────────────────────────────
def slug() -> str:
    """추측 불가 경로 조각. **한 번 만들고 고정한다** — 바뀌면 이미 나눠 준
    링크가 전부 죽고, 옛 경로는 원격에 남아 계속 서비스된다(지우지 않으므로)."""
    p = ROOT / "config" / "publish.json"
    if p.exists():
        s = (json.loads(p.read_text(encoding="utf-8")).get("slug") or "").strip()
        if s:
            return s
    s = secrets.token_hex(8)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"slug": s}, ensure_ascii=False, indent=2),
                 encoding="utf-8")
    print(f"[publish] 경로 slug 을 새로 만들었다: {s}  (config/publish.json 에 고정)")
    return s


def prefix() -> str:
    return f"axs/{slug()}"


def pages_url() -> str:
    return f"https://{OWNER}.github.io/{REPO}/{prefix()}/{PAGE}"


# ── 회차 고르기 ─────────────────────────────────────────────────────────
def rounds() -> list:
    base = ROOT / "out"
    return sorted([p.name for p in base.iterdir()
                   if p.is_dir() and len(p.name) == 8 and p.name.isdigit()])


def pick_round(want, plan: bool = False):
    """기본 = **승인된 최신 회차**. 승인 없는 회차는 세션에 나간 적이 없다.

    `plan=True`(`--plan`) 는 **승인 전 기획 단계**를 올리는 자리다 — 관리자가
    공개 페이지에서 기획서를 읽고 승인을 판단하기 때문에(2026-09-16 사용자 지시),
    승인 게이트를 건너뛰고 **기획서가 있는 최신 회차**를 고른다. T1·T2 는 없어도 된다.
    """
    rs = rounds()
    if want:
        if want not in rs:
            raise SystemExit(f"[중단] 회차 폴더가 없다: out/{want}")
        return want
    if plan:
        ok = [r for r in rs if (ROOT / "out" / r / f"기획서_{r}.pdf").exists()]
        if not ok:
            raise SystemExit("[중단] 기획서가 있는 회차가 없다 — build_brief.py 먼저.")
        return ok[-1]
    ok = [r for r in rs if (ROOT / "out" / r / "승인.json").exists()]
    if not ok:
        raise SystemExit("[중단] 승인된 회차가 없다 — 승인.bat 먼저. "
                         "(회차를 못 박으려면 --round YYYYMMDD)")
    return ok[-1]


# ── 발행본 만들기 (메모리 위에서) ────────────────────────────────────────
def inject_noindex(html: str) -> str:
    if "noindex" in html:
        return html
    m = re.search(r'<meta\s+charset=[^>]*>', html, re.I)
    if not m:                                   # <head> 뒤에라도 넣는다
        m = re.search(r'<head[^>]*>', html, re.I)
    if not m:
        raise SystemExit("[중단] noindex 를 넣을 자리를 못 찾았다 — head 가 없다")
    return html[:m.end()] + "\n" + NOINDEX + html[m.end():]


def _cut_div(html: str, start: int) -> int:
    """`start` 의 <div ...> 에 짝이 되는 </div> 바로 뒤 위치. rbox 안에 div 가 중첩돼 있어
    정규식으로는 못 자른다 — 깊이를 센다."""
    depth, i = 0, start
    for m in re.finditer(r'<(/?)div\b[^>]*>', html[start:]):
        depth += -1 if m.group(1) else 1
        if depth == 0:
            return start + m.end()
        i = start + m.end()
    raise SystemExit("[중단] 회차 상자의 </div> 짝을 못 찾았다 — 페이지 구조가 바뀌었다")


def remote_rounds(remote_paths) -> set:
    """원격에 **이미 올라가 있는** 회차. 그 회차 버튼은 눌러도 빈손이 아니다."""
    pre = prefix() + "/out/"
    out = set()
    for path in remote_paths:
        if path.startswith(pre):
            r = path[len(pre):].split("/")[0]
            if len(r) == 8 and r.isdigit():
                out.add(r)
    return out


def drop_other_rounds(html: str, keep, cur=None):
    """**발행되지 않은** 회차를 화면에서 통째로 뺀다 (선택 버튼 + 상자).

    `keep` 는 회차 하나(str) 또는 여러 개(집합)다. 원격에 이미 올라간 회차는 남기므로
    공개본에서도 **9월 2주차 · 9월 3주차를 버튼으로 골라** 볼 수 있다(2026-09-16 사용자 지시).
    ⚠️ 열 것이 없는 회차는 여전히 뺀다 — 남겨 두면 **눌러 봐야 빈 것을 알게 된다.**
    ⚠️ 로컬 `소재추천.html` 은 안 건드린다 — 거기가 **지난 회차를 다시 보는 유일한 자리**다.
    """
    keep = {keep} if isinstance(keep, str) else {str(k) for k in keep}
    # 펼쳐 둘 회차 = **지금 발행하는 회차**(`cur`). 안 주면 남은 것 중 최신.
    # ⚠️ 2026-09-18: 전에는 늘 `max(keep)` 이었다. 옛 회차를 발행하면 **방금 만든 회차가 아니라
    #    다음 주 회차가 펼쳐져** 「왜 이것만 나오냐」가 된다(실측). 게다가 build_page 가 펼쳐 둔
    #    상자와 겹쳐 **상자 둘이 동시에 펼쳐졌다.**
    cur = str(cur) if cur else max(keep)
    n = 0
    # ① 회차 상자 <div class="rbox" data-r="...">…</div>
    while True:
        hit = None
        for m in re.finditer(r'<div class="rbox" data-r="(\d{8})"[^>]*>', html):
            if m.group(1) not in keep:
                hit = m
                break
        if not hit:
            break
        html = html[:hit.start()] + html[_cut_div(html, hit.start()):]
        n += 1
    # ② 회차 선택 버튼
    alt = "|".join(sorted(keep))
    html, k = re.subn(
        r'<button class="rbtn[^"]*" data-r="(?!(?:' + alt + r')")\d{8}">.*?</button>',
        "", html)
    # ③ `cur` 만 **펼쳐진 상태**여야 한다 — 지우면서 「on」이 딸려 나갔을 수 있다.
    #    나머지 회차는 hidden 으로 두고 버튼으로 고른다(JS 가 토글한다).
    #    ⚠️ **먼저 전부 hidden 으로 맞춘다** — build_page 가 펼쳐 둔 회차가 `cur` 과 다르면
    #       둘이 동시에 펼쳐진 채로 나간다(2026-09-18 실측).
    html = re.sub(r'<div class="rbox" data-r="(\d{8})"(?![^>]*hidden)',
                  r'<div class="rbox" data-r="\1" hidden', html)
    html = re.sub(r'<button class="rbtn on" data-r="', '<button class="rbtn" data-r="', html)
    # ⚠️ 버튼에 **다른 속성이 붙는다** — 체험 회차 버튼은 `data-nocase="1"` 을 달고 있어
    #    `data-r="…">` 로 닫히지 않는다. 속성을 통째로 살려 둔 채 class 만 바꾼다
    #    (2026-09-18: 이걸 놓쳐 **체험 회차만 「on」이 안 붙었다**).
    html = re.sub(r'<button class="rbtn[^"]*"([^>]*\bdata-r="' + cur + r'")',
                  r'<button class="rbtn on"\1', html)
    # ⚠️ 치환문은 **그룹 1 을 다시 넣어야** 한다(2026-09-18 버그 수정). 이 자리엔 `\1` 이 아니라
    #    **제어문자 0x01 한 바이트**가 들어 있었다 — 그러면 `hidden` 만 지워지는 게 아니라
    #    **여는 태그 `<div class="rbox" data-r="…"` 가 통째로 사라진다.**
    #    결과: ①그 회차 상자가 없어지고 ②남은 `>` 가 화면 맨 위에 찍히고 ③중첩이 깨져
    #    **버튼은 남아 있는데 눌러도 안 바뀐다.** 로컬은 멀쩡하고 **공개본만** 그렇게 나간다.
    #    평소엔 안 터진다 — `cur`(남은 것 중 최신)이 발행 회차와 같으면 그 상자엔 `hidden` 이
    #    없어 매칭이 없다. **옛 회차를 발행할 때만** 터진다(2026-09-16 발행이 그랬다).
    html = re.sub(r'(<div class="rbox" data-r="' + cur + r'")\s+hidden', r'\1', html)
    # ④ ⚠️ 안내문이 화면과 맞아야 한다 — 회차가 하나뿐이면 「지난 회차」는 거짓말이다
    OLD = ('<div class="sub">지난 회차의 기획과 산출물. 페이지는 매주 덮어쓰이므로 여기가 '
           '<b>지난 회차를 다시 보는 유일한 자리</b>다.</div>')
    html = html.replace(OLD, '<div class="sub">이번 회차의 기획과 산출물.</div>'
                        if len(keep) == 1 else
                        '<div class="sub">회차를 골라 보세요 — 발행된 회차의 기획과 산출물입니다.</div>')
    return html, n + k


def stage(rnd: str, plan: bool = False, keep=None):
    """(원격 상대경로, 바이트) 목록. 없는 파일은 즉시 중단한다.

    `plan=True` 면 **기획서만 필수**고 T1·T2 는 없으면 건너뛴다(승인 전 기획 단계).
    칩은 build_page 가 **있는 파일만** 그리므로 화면에 죽은 링크는 남지 않는다.
    """
    rd = ROOT / "out" / rnd
    out = []

    def need(p: Path) -> bytes:
        if not p.is_file():
            if plan:
                raise FileNotFoundError(p)      # plan 단계에선 건너뛴다
            raise SystemExit(f"[중단] 발행 대상이 없다: {p}")
        return p.read_bytes()

    # ① 소재추천.html — noindex + 미발행 회차 칩 비활성
    html = (ROOT / PAGE).read_text(encoding="utf-8")
    # 펼쳐 둘 회차는 **지금 발행하는 회차**다(2026-09-18) — 남은 것 중 최신이 아니다.
    html, dead = drop_other_rounds(inject_noindex(html), keep or rnd, rnd)
    if dead:
        print(f"[publish] 미발행 회차를 화면에서 뺐다 (상자·버튼 {dead}개)")
    out.append((PAGE, html.encode("utf-8")))

    # ② 기획서 PDF
    out.append((f"out/{rnd}/기획서_{rnd}.pdf", need(rd / f"기획서_{rnd}.pdf")))

    # ③ T1 덱 (base64 내장이라 자립한다)
    t1 = f"T1_부서장회의_{rnd}.html"
    try:
        out.append((f"out/{rnd}/{t1}",
                    inject_noindex(need(rd / t1).decode("utf-8")).encode("utf-8")))
    except FileNotFoundError:
        print(f"[publish] T1 덱 없음 — 기획 단계로 올린다 ({t1})")

    # ④ T2 뷰어 + 슬라이드 — png → jpg 로 바꿔 올리고 src 도 같이 바꾼다
    # ⚠️ 편 이름을 박아 두지 않는다 — **체험 회차는 「체험」 한 편**이다(2026-09-18).
    #    박아 두면 그 뷰어가 **조용히 발행에서 빠진다**(중단도 경고도 없다).
    views = sorted(rd.glob(f"T2_정보채널_*_{rnd}.html"))
    if not views:
        print("[publish] T2 뷰어 없음 — 기획 단계로 올린다")
    for v in views:
        ax = v.name[len("T2_정보채널_"):-len(f"_{rnd}.html")]
        try:
            vh = inject_noindex(need(v).decode("utf-8"))
        except FileNotFoundError:
            print(f"[publish] T2 {ax} 없음 — 기획 단계로 올린다")
            continue
        srcs = re.findall(r'<img src="([^"]+\.png)"', vh)
        if not srcs:
            raise SystemExit(f"[중단] T2 뷰어에 슬라이드가 없다: {v}")
        for s in srcs:
            p = rd / s
            if not p.is_file():
                raise SystemExit(f"[중단] 슬라이드가 없다: {p}")
            im = Image.open(p)
            if im.mode != "RGB":                 # 알파는 전부 불투명(실측) — 흰 바탕
                im = im.convert("RGB")
            if max(im.size) > JPEG_SIDE:
                im = im.resize((JPEG_SIDE, JPEG_SIDE), Image.LANCZOS)
            buf = _io.BytesIO()
            im.save(buf, "JPEG", quality=JPEG_Q, optimize=True,
                    progressive=True, subsampling=0)
            out.append((f"out/{rnd}/{s[:-4]}.jpg", buf.getvalue()))
        vh = re.sub(r'(<img src="[^"]+)\.png"', r'\1.jpg"', vh)
        out.append((f"out/{rnd}/{v.name}", vh.encode("utf-8")))

    # ⑤ 남겨 둔 **지난 회차의 기획서**도 같이 본다.
    #    화면에 버튼이 남아 있는데 그 회차 기획서를 로컬에서 고치면(예: 사례 회차를
    #    체험 회차로 바꿈) **공개본만 옛 판으로 남는다** — 2026-09-16 에 실제로 그랬다.
    #    변경 감지가 같은 파일은 걸러내므로 비용은 0 이다.
    #    ⚠️ 지난 회차의 T1·T2 까지 갱신하려면 그 회차를 `--round` 로 지정해 올린다
    #       (여기서 슬라이드 수십 장을 매번 다시 굽지 않기 위해 기획서만 본다).
    for other in sorted(set(keep or []) - {rnd}):
        bp = ROOT / "out" / other / f"기획서_{other}.pdf"
        if bp.is_file():
            out.append((f"out/{other}/기획서_{other}.pdf", bp.read_bytes()))

    return out


# ── GitHub ──────────────────────────────────────────────────────────────
def read_token() -> str:
    # 토큰은 test/.env 에 있다 (여러 프로젝트가 공유)
    for env in (ROOT.parent / ".env", ROOT / ".env"):
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("GITHUB_TOKEN="):
                    v = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if v and not v.startswith("<"):
                        return v
    raise SystemExit("[중단] GITHUB_TOKEN 을 찾지 못했다 (test/.env)")


def git_blob_sha(data: bytes) -> str:
    h = hashlib.sha1()
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


class GH:
    def __init__(self, token: str):
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def req(self, method: str, url: str, retry: int = 3, **kw):
        for i in range(retry + 1):
            r = self.s.request(method, url, timeout=180, **kw)
            if r.status_code < 300:
                return r.json() if r.text else {}
            if r.status_code in (403, 429, 500, 502, 503) and i < retry:
                wait = 5 * (i + 1)
                print(f"    [{r.status_code}] {wait}s 대기 후 재시도")
                time.sleep(wait)
                continue
            raise SystemExit(f"[중단] {method} {url} → {r.status_code}\n{r.text[:400]}")
        raise SystemExit("[중단] 재시도 소진")


def main(argv=None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="변경 감지 무시하고 전량 재업로드")
    ap.add_argument("--round", default=None, help="회차 YYYYMMDD (기본=승인된 최신)")
    ap.add_argument("--message", default=None)
    ap.add_argument("--url", action="store_true", help="공개 URL 만 찍는다")
    ap.add_argument("--plan", action="store_true",
                    help="승인 전 기획 단계 발행 — 기획서만 있으면 올린다(T1·T2 생략)")
    a = ap.parse_args(argv)

    if a.url:
        print(pages_url())
        return 0

    rnd = pick_round(a.round, a.plan)

    # ⚠️ **원격 트리를 staging 보다 먼저 읽는다.** 공개본에 남길 회차가 「이미 올라간
    #    회차」로 정해지기 때문이다(2026-09-16). 전엔 이번 회차만 남겨서 지난 주차가
    #    페이지에서 사라졌다 — 파일은 원격에 그대로 있는데 **버튼이 없어 못 열었다.**
    gh = GH(read_token())
    ref = gh.req("GET", f"{API}/git/ref/heads/{BRANCH}")
    base_commit = ref["object"]["sha"]
    base_tree = gh.req("GET", f"{API}/git/commits/{base_commit}")["tree"]["sha"]

    tree = gh.req("GET", f"{API}/git/trees/{base_tree}?recursive=1")
    truncated = bool(tree.get("truncated"))
    blobs = [e for e in tree.get("tree", []) if e["type"] == "blob"]
    if truncated:
        print("⚠️ 원격 트리가 잘렸다 — 변경 감지를 못 쓰고 전량 업로드한다")
    # --force 는 **변경 감지만** 끈다. 회차 목록은 그대로 쓴다.
    remote = {} if (truncated or a.force) else {e["path"]: e["sha"] for e in blobs}

    keep = remote_rounds(e["path"] for e in blobs) | {rnd}
    files = [(f"{prefix()}/{rp}", d) for rp, d in stage(rnd, a.plan, keep)]
    total = sum(len(d) for _, d in files)
    print(f"[publish] 회차 {rnd} · 남길 회차 {'·'.join(sorted(keep))} · "
          f"대상 {len(files)}개 · {total/1048576:.1f}MB → {OWNER}/{REPO}:{BRANCH}/{prefix()}")
    if truncated:
        print("⚠️ 트리가 잘려 지난 회차를 못 셌다 — 이번 회차만 남는다")

    changed = [(rp, d) for rp, d in files
               if a.force or truncated or remote.get(rp) != git_blob_sha(d)]
    print(f"[publish] 변경 {len(changed)}개 · 동일 {len(files)-len(changed)}개")
    if not changed:
        print("[publish] 바뀐 게 없다. 발행 생략")
        print(f"          {pages_url()}")
        return 0
    if a.dry_run:
        for rp, d in changed:
            print(f"    {len(d)/1024:8.0f}KB  {rp}")
        print("[publish] --dry-run 이라 업로드하지 않았다")
        return 0

    entries = []
    for i, (rp, d) in enumerate(changed, 1):
        b = gh.req("POST", f"{API}/git/blobs", json={
            "content": base64.b64encode(d).decode(), "encoding": "base64"})
        entries.append({"path": rp, "mode": "100644", "type": "blob", "sha": b["sha"]})
        print("    blob %d/%d  %s" % (i, len(changed), rp.rsplit("/", 1)[-1]))

    msg = a.message or f"AX_source 소재추천 발행 {rnd} ({len(changed)}개 갱신)"
    for attempt in range(4):
        new_tree = gh.req("POST", f"{API}/git/trees",
                          json={"base_tree": base_tree, "tree": entries})["sha"]
        commit = gh.req("POST", f"{API}/git/commits",
                        json={"message": msg, "tree": new_tree,
                              "parents": [base_commit]})
        r = gh.s.patch(f"{API}/git/refs/heads/{BRANCH}",
                       json={"sha": commit["sha"]}, timeout=120)
        if r.status_code < 300:
            break
        if r.status_code == 422 and "fast forward" in r.text.lower() and attempt < 3:
            print("    남이 먼저 푸시했다 — 최신 head 위로 다시 얹는다")
            time.sleep(3)
            ref = gh.req("GET", f"{API}/git/ref/heads/{BRANCH}")
            base_commit = ref["object"]["sha"]
            base_tree = gh.req("GET", f"{API}/git/commits/{base_commit}")["tree"]["sha"]
            continue
        raise SystemExit(f"[중단] ref 이동 실패 → {r.status_code}\n{r.text[:400]}")
    else:
        raise SystemExit("[중단] 재시도 4회 모두 충돌 — 잠시 뒤 다시 실행할 것")

    print(f"[publish] 커밋 {commit['sha'][:7]} · {msg}")
    print(f"[publish] ✅ {pages_url()}")
    print("          Pages 반영에 보통 40~60초 걸린다")
    print("⚠️ public 리포다 — 경로를 모르면 못 찾을 뿐, 링크가 나가면 누구나 본다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
