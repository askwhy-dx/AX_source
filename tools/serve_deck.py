# -*- coding: utf-8 -*-
"""회차 폴더를 로컬 서버로 띄우고 T1 덱을 브라우저로 연다.

    python tools/serve_deck.py            # 오늘 회차
    python tools/serve_deck.py 20260908   # 특정 회차

왜 필요한가 (2026-09-08 실측):
  덱을 **파일로 직접**(file://) 열면 유튜브가 임베드를 거부한다 — 플레이어가
  「동영상 플레이어 구성 오류 · 오류 153」만 띄우고 아무것도 안 튼다.
  같은 덱을 http://127.0.0.1 로 열면 오류 없이 재생된다. 출처(origin) 문제라
  덱 코드로는 못 고친다 — 띄우는 방법을 바꿔야 한다.

  ⚠️ 로컬 영상 파일(clips/)만 쓰는 회차는 이게 필요 없다. 유튜브를 안 부르니까.
"""
import argparse, functools, http.server, os, socket, sys, threading, urllib.parse, webbrowser
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def free_port(start=8731, tries=40):
    """쓰는 사람이 여럿이거나 앞 회차 서버가 살아 있을 수 있다 — 빈 포트를 찾는다."""
    for p in range(start, start + tries):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", p)) != 0:
                return p
    sys.exit("빈 포트를 찾지 못했습니다 (%d~%d)" % (start, start + tries))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("day", nargs="?", default=f"{date.today():%Y%m%d}")
    ap.add_argument("--no-open", action="store_true")
    a = ap.parse_args()

    d = os.path.join(ROOT, "out", a.day)
    if not os.path.isdir(d):
        sys.exit(f"회차 폴더가 없습니다: {d}")
    deck = f"T1_부서장회의_{a.day}.html"
    if not os.path.exists(os.path.join(d, deck)):
        sys.exit(f"덱이 없습니다: {deck}  (python tools/build_t1.py 먼저)")

    port = free_port()
    url = "http://127.0.0.1:%d/%s" % (port, urllib.parse.quote(deck))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=d)
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)

    print(f"  {url}")
    print("  브라우저가 열립니다. 발표가 끝나면 이 창을 닫으세요 (Ctrl+C).")
    print("  ※ 파일을 더블클릭해서 열면 유튜브가 오류 153 으로 재생을 막습니다.")
    if not a.no_open:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\n  닫았습니다.")


if __name__ == "__main__":
    main()
