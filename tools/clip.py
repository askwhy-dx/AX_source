# -*- coding: utf-8 -*-
"""구간 클립 추출기 — 승인된 재생 구간만 mp4 로 잘라 덱 옆에 둔다. (2026-09-09 신설)

  python tools/clip.py            # 이번 회차의 T1_대본.json 재생 구간을 자른다
  python tools/clip.py --force    # 이미 있어도 다시 받는다
  python tools/clip.py --check    # 무엇이 잘려 있나만 본다

산출: out/<회차>/clips/<축>_<영상ID>_<시작>-<끝>.mp4

## 왜 필요한가
덱을 `file://` 로 열면 **유튜브가 임베드를 거부해 오류 153 만 뜬다.** 그래서 지금까지는
`열기.bat` 으로 로컬 서버를 띄워야 영상이 나왔다. 회의실에서 덱만 받은 사람은 못 튼다.
**구간을 미리 잘라 두면 `<video>` 로 재생되므로 file:// 에서도, 인터넷이 없어도 돈다.**
덱은 이미 `재생[].파일` 을 받도록 돼 있었다 — 사람이 넣던 자리를 이 도구가 채운다.

## 무엇을 자르나 — 승인된 것만
`T1_대본.json` 의 `재생` 구간이다. LLM 이 챕터를 보고 고르고, **수요일 기획서에 실려
사람이 승인할 때 확정된다.** 구간이 비어 있으면 **아무것도 안 자른다** — 찍어서 통째로
받아 두는 것이 더 나쁘다(용량도, 근거도).

⚠️ 클립은 **사내 발표용**이다. `out/<회차>/clips/` 밖으로 내보내지 않는다.
   GitHub 업로드 경로에도 넣지 않는다 (README §9 「이미지 업로드 영구 금지」와 같은 선).
"""
import argparse, io, json, os, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_page as B
import build_t1 as T1
import collect as C

CLIP_DIR = "clips"
MAX_SEC = 300          # 5분 넘는 구간은 애초에 _clamp_play 가 버린다. 두 겹째 방어.


def find_ffmpeg():
    """ffmpeg 경로. winget 으로 깔면 PATH 에 안 잡히는 경우가 있어 한 번 더 뒤진다."""
    p = shutil.which("ffmpeg")
    if p:
        return p
    root = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Microsoft",
                        "WinGet", "Packages")
    if os.path.isdir(root):
        for dirpath, _, files in os.walk(root):
            if "ffmpeg.exe" in files:
                return os.path.join(dirpath, "ffmpeg.exe")
    return None


def clip_name(ax, vid, a, b):
    return f"{ax}_{vid}_{a}-{b}.mp4".replace(":", "")


def cut_one(vid, start, end, out_path, ffmpeg, by="LLM"):
    """유튜브에서 받아 그 구간만 잘라 낸다. (ok, 메시지)

    ⚠️ **구간만 받는 길(`download_ranges`)을 써 봤다가 버렸다** (2026-09-09 실측).
       yt-dlp 가 m3u8 로 붙어 ffmpeg 가 조각을 끌어오는데 **13초짜리가 4분을 넘겨도 안 끝났다.**
       반면 **480p 전체는 26MB · https 직행**이라 훨씬 빠르다. 그래서 통째로 받아
       로컬에서 자르고 **원본은 지운다** — 남는 건 구간 mp4 하나뿐이다.

    ⚠️ **사람이 지정한 구간(`by="사람"`)엔 길이 상한을 걸지 않는다.** 상한은 LLM 이
       찍어서 긴 구간을 적는 걸 막으려는 것이지, 사람 판단을 막으려는 게 아니다.

    ⚠️ 화질을 480p 로 묶는다. 회의실 프로젝터엔 충분하고, 720p 이상은 받는 시간이
       회의 준비를 잡아먹는다.
    """
    import yt_dlp
    a, b = T1.secs(start), T1.secs(end)
    if a is None or b is None or b <= a:
        return False, f"구간을 못 읽었다: {start}~{end}"
    if b - a > MAX_SEC and by != "사람":
        return False, f"{(b - a) // 60}분 — 너무 길다(상한 {MAX_SEC // 60}분)"

    stem = out_path + ".src"
    opts = {
        # https 직행 DASH 를 고른다. m3u8(포맷 6xx·2xx)은 느려서 피한다.
        "format": ("bv*[height<=480][protocol^=http][ext=mp4]+ba[protocol^=http][ext=m4a]/"
                   "bv*[height<=480][protocol^=http]+ba[protocol^=http]/b[height<=480]"),
        "outtmpl": stem + ".%(ext)s",
        "quiet": True, "no_warnings": True, "noprogress": True,
        "merge_output_format": "mp4",
        "ffmpeg_location": os.path.dirname(ffmpeg),
        "overwrites": True,
        "socket_timeout": 30,
        "retries": 3,
    }
    try:
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([f"https://www.youtube.com/watch?v={vid}"])
    except Exception as e:
        _sweep(stem)
        return False, f"받기 실패: {str(e)[:160]}"

    src = next((stem + e for e in (".mp4", ".mkv", ".webm")
                if os.path.exists(stem + e)), None)
    if not src:
        _sweep(stem)
        return False, "받은 파일을 못 찾았다"

    # -ss 를 -i 앞에 두면 키프레임까지만 훑고 들어가 빠르다. 재인코딩으로 시작을 정확히 맞춘다.
    cmd = [ffmpeg, "-y", "-loglevel", "error", "-ss", str(a), "-to", str(b), "-i", src,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-c:a", "aac",
           "-movflags", "+faststart", out_path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
        if r.returncode != 0:
            return False, "ffmpeg 실패: " + (r.stderr or "")[:160]
    except Exception as e:
        return False, f"ffmpeg 예외: {e}"
    finally:
        _sweep(stem)
    if not os.path.exists(out_path):
        return False, "잘린 파일이 안 생겼다"
    mb = os.path.getsize(out_path) / 1024 / 1024
    return True, f"{b - a}초 · {mb:.1f}MB"


def _sweep(stem):
    """받다 만 조각까지 치운다 — `.part`·`.f135.mp4` 같은 것이 남으면 다음 회차가 헷갈린다."""
    d, base = os.path.dirname(stem), os.path.basename(stem)
    if not os.path.isdir(d):
        return
    for f in os.listdir(d):
        if f.startswith(base):
            try:
                os.remove(os.path.join(d, f))
            except OSError:
                pass


def run(force=False, check=False):
    d = B.round_day()
    out_d = B.out_dir(make=False)
    sp = os.path.join(out_d, T1.SCRIPT_NAME)
    if not os.path.exists(sp):
        print("  [건너뜀] T1_대본.json 이 없습니다 — build_t1.py 를 먼저 도세요.")
        return 0
    deck = json.load(io.open(sp, encoding="utf-8"))
    ses = None
    clips_d = os.path.join(out_d, CLIP_DIR)
    os.makedirs(clips_d, exist_ok=True)

    ffmpeg = find_ffmpeg()
    if not ffmpeg and not check:
        print("  [건너뜀] ffmpeg 를 못 찾았습니다 — 덱은 유튜브 임베드로 그대로 돕니다.")
        return 0

    made, changed = [], False
    for ax in C.AXES:
        v = deck.get(ax) or {}
        vid = v.get("영상ID", "")
        for c in (v.get("재생") or []):
            a, b = c.get("시작"), c.get("끝")
            name = clip_name(ax, vid, a, b)
            path = os.path.join(clips_d, name)
            if os.path.exists(path) and not force:
                print(f"  {ax} 있음 — {name}")
                if c.get("파일") != name:
                    c["파일"] = name
                    changed = True
                made.append(name)
                continue
            if check:
                print(f"  {ax} 없음 — {name}")
                continue
            print(f"  {ax} {a}~{b} 자르는 중…", flush=True)
            ok, msg = cut_one(vid, a, b, path, ffmpeg, c.get("출처", "LLM"))
            if ok:
                print(f"     완료 {name} ({msg})")
                c["파일"] = name
                changed = True
                made.append(name)
            else:
                # ⚠️ 실패해도 대본은 안 건드린다 — 파일 이름만 남으면 덱이 없는 파일을 튼다
                print(f"     실패 — {msg}")
                print(f"     이 축은 유튜브 임베드로 갑니다(열기.bat 필요).")

    if changed:
        io.open(sp, "w", encoding="utf-8").write(json.dumps(deck, ensure_ascii=False, indent=2))
        print(f"  대본에 파일 이름을 적었습니다 — {os.path.basename(sp)}")
        print("  ⚠️ 덱을 다시 만들어야 반영됩니다: python tools/build_t1.py")
    if not made and not check:
        print("  자를 구간이 없습니다 — T1_대본.json 의 `재생` 이 비어 있습니다.")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="이미 있어도 다시 받는다")
    ap.add_argument("--check", action="store_true", help="무엇이 잘려 있나만 본다")
    a = ap.parse_args()
    return run(a.force, a.check)


if __name__ == "__main__":
    sys.exit(main())
