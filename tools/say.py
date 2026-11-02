# -*- coding: utf-8 -*-
"""배치의 한글 메시지 창구 — run_plan.bat(수) · run_weekly.bat(목) 둘 다 여기로 찍는다.
  `python tools\\say.py <키> [인자...]`

왜 배치가 직접 echo 하지 않고 여기로 오는가 (2026-09-08):
  cp949 콘솔에서 cmd 는 UTF-8 배치의 **멀티바이트 줄을 지날 때마다 파일 오프셋이
  밀린다**. 누적 드리프트가 한 줄을 넘으면 그 다음부터 **줄 중간에서 실행**된다 -
  실측으로 `if not exist ...` 가 `xist` 로 잘려 나갔고, 에러는 한 줄 찍히고 배치는
  계속 돌아 **결과만 조용히 빠진다**.
  중간에 `chcp 65001` 을 켜도 늦다 - **배치 시작 시점의 코드페이지가 파싱을 정한다**
  (65001 을 켠 뒤의 한글 주석에서 또 드리프트했다). 그래서 배치는 ASCII 전용으로
  두고, 한글은 전부 이 파일에 모은다. 파이썬은 파일을 UTF-8 로 읽으니 안전하다.

  ⚠️ 배치에 한글을 도로 넣지 말 것. tools/self_test.py ⑤ 가 FAIL 로 잡는다.
"""
import io, os, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALERT_LOG = os.path.join(ROOT, "out", "pool", "경보.log")


def _now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log_start(mode):
    print("=" * 60)
    print("[%s] AX_source 주간 배치 시작 mode=%s" % (_now(), mode or "collect"))


def log_end():
    print("[%s] 정상 종료" % _now())


def log_fail(step, rc):
    print("[%s] %s 실패 rc=%s" % (_now(), step, rc))


def plan_start(mode=""):
    print("[%s] 기획 배치 시작 %s" % (_now(), mode))


def plan_done(log):
    print()
    print("  기획서가 나왔습니다. 회차 폴더의 기획서_<날짜>.pdf 를 읽어 주세요.")
    print("  괜찮으면 같은 폴더의 승인.bat 을 더블클릭하세요 —")
    print("  승인이 없으면 내일(목) 배치가 T1 덱·T2 툰을 만들지 않습니다.")
    print("  로그 %s" % log)


def human_plan():
    print()
    print("  기획 배치 끝. 다음은 사람 차례입니다 — 기획서 읽고 승인.")


def not_approved():
    print()
    print("  [건너뜀] 이번 회차가 아직 승인되지 않았습니다.")
    print("  기획서를 읽고 회차 폴더의 승인.bat 을 누르면 T1·T2 를 만듭니다.")
    print("  실패가 아닙니다 — 승인 대기 상태입니다.")


def fail_brief(rc, log):
    print()
    print("  [실패] 기획서 생성이 중단됐습니다. rc=%s" % rc)
    print("  대본·기획 JSON 이 깨졌는지 로그를 먼저 봅니다.")
    print("  로그 %s" % log)


def pstep(n, mode=""):
    # ⚠️ 모르는 단계 이름이 와도 죽지 않는다 — 배치가 «안내 문구» 때문에 멈추면 안 된다.
    label = {
        "1": "카탈로그 재생성 - API 호출 없음 ..." if mode.lower() == "rebuild"
             else "시드 채널 수집 A1 ...",
        "2a": "LLM 심사 A1b - 사례인가 · 분석/생성 ...",
        "2b": "재고 확인 A1c - 부족하면 보충 ...",
        "2": "회차 기획 + 기획서 PDF ...",
        "3": "추천 페이지 생성 A2 ...",
        "4": "자체 점검 ...",
        "5": "기획 단계 발행 - 기획서를 공개 페이지에 올린다 ...",
    }.get(n, "%s ..." % n)
    print("[%s] %s" % (n, label))


def step(n, mode=""):
    label = {
        "1": "T1 부서장회의 덱 ...",
        "2": "T2 정보채널 인스타 캐러셀 ...",
        "3": "회차 기획서 갱신(승인 도장) ...",
        "4": "추천 페이지 생성 A2 ...",
        "5": "자체 점검 ...",
        "6": "GitHub Pages 발행 ...",
    }[n]
    print("[%s/6] %s" % (n, label))


def fail_collect(rc, log):
    print()
    print("  [실패] 수집 단계가 중단됐습니다. rc=%s" % rc)
    print("  할당량 초과 quotaExceeded 인지 로그를 먼저 봅니다.")
    print("  리셋은 한국시간 오후 4~5시. 실패해도 지난주 후보 풀로 버팁니다.")
    print("  로그 %s" % log)


def fail_page(rc, log):
    print()
    print("  [실패] 추천 페이지 생성이 중단됐습니다. rc=%s" % rc)
    print("  로그 %s" % log)


def fail_selftest(log):
    print()
    print("  ***** 자체 점검 FAIL - 레퍼런스 2건이 상위에서 밀렸습니다 *****")
    print("  추천을 그대로 쓰면 안 됩니다. 로그의 FAIL 줄을 먼저 봅니다.")
    print("  로그 %s" % log)


def fail_publish(rc, log):
    print()
    print("  ***** 발행 FAIL - 공개본이 지난 회차인 채로 남았습니다 rc=%s *****" % rc)
    print("  화면도 링크도 정상으로 보이기 때문에 눈으로는 못 알아챕니다.")
    print("  로그를 보고 python tools/publish.py 를 손으로 다시 돌립니다.")
    print("  로그 %s" % log)


def published():
    print()
    print("  발행 완료. 공개 URL 은 로그의 publish 줄에 있습니다.")
    print("  python tools/publish.py --url 로도 다시 찍을 수 있습니다.")
    print("  ⚠️ public 리포입니다 - 경로를 모르면 못 찾을 뿐, 링크가 나가면 누구나 봅니다.")


def warn(which):
    # 모르는 이름이 와도 죽지 않는다 — 배치가 경고 한 줄 때문에 멈추면 본말전도다
    name = {"t1": "T1 덱", "t1script": "T1 발표 멘트", "t2": "T2 캐러셀", "brief": "회차 기획서",
            "page": "추천 페이지", "clip": "구간 클립",
            "publish": "GitHub Pages 발행",
            "screen": "LLM 심사", "refill": "재고 보충"}.get(which, which)
    print("  [경고] %s 실패 - 로그를 보세요." % name)


def done(today, log):
    print()
    print("  완료. 추천 페이지 소재추천.html")
    print("  회차 기획서 PDF - 기획-원고를 한 번에 검토하는 문서입니다")
    print("  T1 덱은 out\\%s\\ - 소재추천.html 「회차별 보기」에서도 열립니다"
          % today)
    print("  로그   %s" % log)


def alert():
    """오늘자 공급 경보가 있으면 화면에 다시 띄운다. 없으면 아무것도 안 찍는다."""
    if not os.path.exists(ALERT_LOG):
        return
    today = datetime.now().strftime("%Y-%m-%d")
    hits = [x.rstrip("\n") for x in io.open(ALERT_LOG, encoding="utf-8")
            if today in x]
    if not hits:
        return
    print()
    print("  ***** 공급 경보 - out\\pool\\경보.log *****")
    for h in hits:
        print(h)
    print("  신선도 경보는 시드 채널이 낡았다는 신호입니다. docs 7.0 채널 표를 손봅니다.")


def human(today):
    print()
    print("  [사람이 할 일] T1 덱과 T2 캐러셀은 둘 다 초안입니다.")
    print("  제목·「무엇을」·진행과정 단계는 영상 챕터에서 뽑은 기계 초안이라 우리 업무 말이 아닙니다.")
    print("  T1 은 out\\%s\\T1_대본.json, T2 는 같은 폴더 T2_대본.json 을 고치고" % today)
    print("  build_t1.py 를 다시 돌리면 고친 내용이 유지됩니다.")
    print()
    print("  추천은 후보까지입니다.")
    print("  금요일에 우리 업무 말로 바꾸는 것까지가 한 세트입니다.")
    print("  분석 1건 + 생성 1건을 같은 주제로 붙이면 13분이 한 이야기가 됩니다.")


KEYS = {
    "log_start": log_start, "log_end": log_end, "log_fail": log_fail,
    "step": step, "fail_collect": fail_collect, "fail_page": fail_page,
    "fail_selftest": fail_selftest, "warn": warn, "done": done,
    "plan_start": plan_start, "plan_done": plan_done, "human_plan": human_plan,
    "not_approved": not_approved, "fail_brief": fail_brief, "pstep": pstep,
    "alert": alert, "human": human,
    "fail_publish": fail_publish, "published": published,
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in KEYS:
        sys.stderr.write("say.py: 알 수 없는 키 %r (가능: %s)\n"
                         % (sys.argv[1:2], ", ".join(sorted(KEYS))))
        sys.exit(2)
    KEYS[sys.argv[1]](*sys.argv[2:])
