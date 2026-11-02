# -*- coding: utf-8 -*-
"""회차 승인 — 관리자가 기획서를 읽고 「이대로 만들어라」를 남기는 자리. (2026-09-09 신설)

  python tools/approve.py            # 이번 회차 승인
  python tools/approve.py --메모 "생성 사례만 바꿔서"
  python tools/approve.py --취소     # 승인 물리기
  python tools/approve.py --확인     # 지금 승인됐나만 본다 (승인=0 / 미승인=1)

승인이 없으면 **목요일 배치가 T1·T2 를 만들지 않는다.** 기획서만 나오고 멈춘다.

## 왜 파일 하나인가
승인은 사람이 한 번 누르는 것이고, 그 기록이 회차 폴더 안에 남아야 한다. 별도 시스템을
두면 그 시스템이 죽었을 때 배치가 멈춘다 — 여기서는 **파일이 없으면 안 만든다**가 전부다.

⚠️ 승인은 **회차 폴더에 매인다**(`out/<그 주 수요일>/승인.json`). 다음 수요일이 되면
   폴더가 바뀌므로 지난 승인은 따라오지 않는다 — 회차마다 다시 승인해야 한다.
"""
import argparse, getpass, io, json, os, sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_page as B


def main():
    ap = argparse.ArgumentParser()
    # ⚠️ ASCII 별칭이 **필수**다 — 배치 파일은 ASCII 전용이라(§9-10) 한글 인자를 못 쓴다.
    ap.add_argument("--메모", "--note", default="", help="한 줄 메모 (선택)")
    ap.add_argument("--취소", "--cancel", action="store_true")
    ap.add_argument("--확인", "--check", action="store_true")
    a = ap.parse_args()

    p = B.approval_path()
    cur = B.approval()
    round_txt = f"{B.round_day():%Y-%m-%d}(수) 회차"

    if a.확인:
        if cur:
            print(f"승인됨 — {round_txt} · {cur.get('승인시각')} · {cur.get('승인자')}")
            if cur.get("메모"):
                print(f"  메모: {cur['메모']}")
            return 0
        print(f"미승인 — {round_txt}. 기획서를 읽고 승인해야 T1·T2 가 만들어집니다.")
        return 1

    if a.취소:
        if not cur:
            print(f"이미 미승인 상태입니다 — {round_txt}")
            return 0
        os.remove(p)
        print(f"승인을 물렸습니다 — {round_txt}")
        print("  이미 만들어진 T1·T2 파일은 지우지 않았습니다. 필요하면 직접 지우세요.")
        return 0

    if cur:
        print(f"이미 승인돼 있습니다 — {round_txt} · {cur.get('승인시각')}")
        print("  다시 승인하려면 --취소 한 뒤 승인하세요.")
        return 0

    rec = {"회차": f"{B.round_day():%Y-%m-%d}",
           "승인시각": f"{datetime.now():%Y-%m-%d %H:%M}",
           "승인자": getpass.getuser(),
           "메모": a.메모.strip()}
    os.makedirs(os.path.dirname(p), exist_ok=True)
    io.open(p, "w", encoding="utf-8").write(json.dumps(rec, ensure_ascii=False, indent=2))
    print(f"승인했습니다 — {round_txt}")
    print(f"  {p}")
    print("  다음 목요일 09:40 배치가 T1 덱과 T2 툰을 만듭니다.")
    print("  지금 바로 만들려면: python tools/build_t1.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
