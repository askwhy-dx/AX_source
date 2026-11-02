# -*- coding: utf-8 -*-
"""LLM 원고 작성기 — 후보 선택 · T1 덱 원고를 claude -p 로 뽑는다. (2026-09-09 신설)

⚠️ **T2 인스타툰은 2026-09-10 부터 여기서 안 만든다** — GPT 가 그림까지 만든다.
   원고 프롬프트·구도/표정/단계 검문은 걷어냈고, 옛 것은
   `archive/20260910_t2/T2_원고_프롬프트.txt` 에 있다. 새 프롬프트는 사용자가 준다.

**채널을 훑어 자료를 모아 오는 데까지가 파이프라인이고, 거기서부터는 LLM 이 한다.**

이 파일이 들어가기 전까지 세 자리가 **기계 규칙**이었다.

  · 후보 선택   build_page.fit()          제목에 낱말이 있나 없나로 ±점수
  · T1 원고     build_t1.default_deck()   유튜브 챕터를 잘라 붙임

둘 다 **유튜브 원문을 옮겨 적을 뿐**이라, 사람이 금요일에 다시 쓰지 않으면 그 주 세션이
「남의 채널 소개」가 됐다. 이제 LLM 이 **모아 온 자료 전량을 읽고 회차를 기획한 다음**
그 기획에 맞춰 한 쌍을 고르고 원고까지 쓴다. **사람이 고치는 자리는 그대로다** —
T1_대본.json 을 고치면 여전히 유지된다(--reset 해야 초안 복귀).

  ① 기획   plan_session()   전량을 읽고 「이번 회차는 무엇에 대한 회차인가」 + 한 쌍 + 제친 후보
  ②        collect.fetch_details()  고른 두 건만 **설명 전문**을 다시 받는다(1 unit)
  ③ T1 원고 write_t1()      기획 + 전문을 근거로 (재생 구간도 여기서 고른다)

컨셉·회사 맥락은 코드가 아니라 `config/LLM_컨셉.md` 에 있다. 그 파일을 통째로 넣는다.

## 왜 「닫힌 메뉴」로 받나
LLM 이 자유 텍스트를 주면 판이 깨진다. T1 덱은 슬라이드 폭·줄 수가 정해져 있어
제목이 길면 넘치고, 도형 이름이 목록에 없으면 그 장이 빈다. 그래서 받은 JSON 을
그대로 쓰지 않고 `_clamp_*` 가 **어휘를 검문하고 길이를 자른다.**
무엇을 잘랐는지는 화면에 찍는다 — 원고 수준을 눈으로 보라고 남기는 것이다.

## 비용과 캐시
회차당 LLM 2회 호출(기획 1 · T1 1) + YouTube 1 unit(설명 전문).
⚠️ T2 가 빠지면서 **4회 → 2회**가 됐다(2026-09-10).
`session()` 이 배치 안에서 세 번 불리므로 **캐시가 없으면 기획만 세 번 돈다** —
그래서 캐시는 선택이 아니라 필수다.
  out/<YYYYMMDD>/llm/<이름>.json    회수한 JSON (다음 호출은 이걸 읽는다)
  out/<YYYYMMDD>/llm/<이름>.prompt.txt  보낸 프롬프트 (원고가 이상하면 여기를 본다)
  out/<YYYYMMDD>/llm/<이름>.raw.txt     받은 원문 (JSON 회수 실패 시 진단용)

## 꺼짐 · 되돌아가기
`--no-llm` 이면 아예 안 부른다. 호출 실패·JSON 회수 실패·환각(후보에 없는 영상ID)은
**기계 초안으로 조용히 되돌아간다.** 배치는 절대 이것 때문에 멈추지 않는다.
"""
import hashlib, io, json, os, re, shutil, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect as C

ROOT = C.ROOT
EMPTY_MCP = os.path.join(ROOT, "config", "empty_mcp.json")
CONCEPT = os.path.join(ROOT, "config", "LLM_컨셉.md")
CLAUDE_PINNED = os.path.join(os.path.expanduser("~"), ".local", "bin", "claude.exe")

ENABLED = True          # build_page 가 --no-llm 을 보고 끈다
REFRESH = False         # --llm-refresh 면 캐시를 무시하고 다시 부른다
_MEM = {}               # 한 프로세스 안에서 같은 tag 를 두 번 안 부르게


def enable(on=True, refresh=False):
    global ENABLED, REFRESH
    ENABLED, REFRESH = on, refresh


def find_claude():
    """스케줄러 환경은 PATH 가 얇다 — which 가 비면 설치 경로로 핀을 박는다."""
    return shutil.which("claude") or (CLAUDE_PINNED if os.path.exists(CLAUDE_PINNED) else None)


def available():
    return ENABLED and find_claude() is not None


def concept():
    if os.path.exists(CONCEPT):
        return io.open(CONCEPT, encoding="utf-8").read()
    return "(config/LLM_컨셉.md 가 없습니다 — 컨셉 없이 일반 상식으로 씁니다.)"


# ── 호출 ────────────────────────────────────────────────────────────────
def _call(prompt, cache_dir, tag, timeout=600):
    """claude -p 한 번. (ok, text). 프롬프트·원문을 캐시 폴더에 남긴다.

    ⚠️ **출력을 파이프가 아니라 파일로 받는다.** claude 가 startup 에 띄우는 손자
       프로세스가 파이프 fd 를 물고 남으면 EOF 가 안 와서 무한 대기한다 —
       counsel_report 가 2026-07-01 에 그렇게 멈췄다. `--strict-mcp-config` 로
       커넥터를 아예 안 띄우는 것이 그 트리거를 없애는 두 번째 층이다.
    """
    claude = find_claude()
    if not claude:
        return False, "claude 실행파일 없음"
    os.makedirs(cache_dir, exist_ok=True)
    io.open(os.path.join(cache_dir, tag + ".prompt.txt"), "w", encoding="utf-8").write(prompt)
    outp = os.path.join(cache_dir, tag + ".raw.txt")
    errp = os.path.join(cache_dir, tag + ".err.txt")
    # ⚠️ **프롬프트는 argv 가 아니라 stdin 으로 넣는다.** 윈도우 커맨드라인 한도는
    #    32,767 자인데 원장이 커지면서 01_기획 프롬프트가 33,697 자가 됐고,
    #    2026-09-16 배치가 `[WinError 206] 파일 이름이나 확장명이 너무 깁니다` 로
    #    **조용히 기계 초안으로 되돌아갔다**(로그엔 한 줄, 산출물은 그대로 나옴).
    #    `claude -p` 는 프롬프트 인자가 없으면 stdin 을 읽는다 — 한도가 사라진다.
    cmd = [claude, "-p", "--output-format", "text",
           "--allowedTools", "",                       # 도구 없이 글만 쓴다
           "--strict-mcp-config", "--mcp-config", EMPTY_MCP]
    try:
        with io.open(outp, "wb") as fo, io.open(errp, "wb") as fe:
            p = subprocess.run(cmd, cwd=ROOT, input=prompt.encode("utf-8"),
                               stdout=fo, stderr=fe, timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"{timeout}s 타임아웃"
    except Exception as e:
        return False, f"호출 예외: {e}"
    txt = io.open(outp, encoding="utf-8", errors="replace").read()
    if p.returncode != 0:
        return False, (io.open(errp, encoding="utf-8", errors="replace").read().strip()[:200]
                       or f"종료코드 {p.returncode}")
    return True, txt


_FENCE = re.compile(r"```(?:json)?\s*(.+?)```", re.S)


def _json_from(text):
    """원문에서 JSON 한 덩이 회수. 코드펜스 → 통째 → 마지막 중괄호 블록 순서."""
    for cand in ([m.group(1) for m in _FENCE.finditer(text)] + [text]):
        cand = cand.strip()
        try:
            return json.loads(cand)
        except Exception:
            pass
    d = 0
    start = None
    for i, ch in enumerate(text):
        if ch == "{":
            if d == 0:
                start = i
            d += 1
        elif ch == "}" and d:
            d -= 1
            if d == 0:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    pass
    return None


def _key_of(prompt):
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]


def ask(prompt, cache_dir, tag, timeout=600):
    """캐시 → 메모리 → 호출. 실패는 None (부른 쪽이 기계 초안으로 되돌아간다).

    ⚠️ **캐시는 이름이 아니라 프롬프트로 물린다.** 이름만 보고 재사용하면,
       기획을 다시 돌려 한 쌍이 바뀐 뒤에도 **원고 캐시는 옛 사례를 그대로 물고 있다** —
       2026-09-09 실측: 생성축 사례를 바꿨는데 T2 대사가 통째로 이전 사례였고,
       `--reset` 은 대본만 되돌릴 뿐 캐시를 건드리지 않아 **에러 없이 그대로 나왔다.**
       프롬프트에는 영상ID·기획·근거가 다 들어 있으니, 그 해시가 달라지면 다시 부른다.
    """
    key = (cache_dir, tag)
    if key in _MEM:
        return _MEM[key]
    path = os.path.join(cache_dir, tag + ".json")
    keyp = os.path.join(cache_dir, tag + ".key")
    want = _key_of(prompt)
    if os.path.exists(path) and not REFRESH:
        have = ""
        if os.path.exists(keyp):
            try:
                have = io.open(keyp, encoding="utf-8").read().strip()
            except Exception:
                pass
        if have == want:
            try:
                v = json.load(io.open(path, encoding="utf-8"))
                _MEM[key] = v
                print(f"  [LLM] {tag} 캐시 재사용 ({os.path.basename(path)})")
                return v
            except Exception:
                pass
        else:
            print(f"  [LLM] {tag} 캐시가 지금 입력과 다릅니다 — 다시 씁니다"
                  + ("" if have else " (옛 캐시라 표식 없음)"))
    if not available():
        return None
    print(f"  [LLM] {tag} 생성 중…", flush=True)
    ok, out = _call(prompt, cache_dir, tag, timeout)
    if not ok:
        print(f"  [LLM] {tag} 호출 실패 → 기계 초안으로 되돌아갑니다: {out}")
        return None
    data = _json_from(out)
    if data is None:
        print(f"  [LLM] {tag} JSON 회수 실패 → 기계 초안. 원문: {tag}.raw.txt")
        return None
    io.open(path, "w", encoding="utf-8").write(json.dumps(data, ensure_ascii=False, indent=2))
    io.open(keyp, "w", encoding="utf-8").write(want)   # 무엇으로 쓴 캐시인지 표식
    _MEM[key] = data
    return data


# ── 공통 자르개 ──────────────────────────────────────────────────────────
def _cut(t, n):
    t = re.sub(r"\s+", " ", str(t or "")).strip()
    return t if len(t) <= n else t[:n].rstrip(" ,·-—") + "…"


def _one(v, allowed, default):
    """닫힌 어휘 검문 — 목록에 없는 값은 조용히 기본값으로. 환각이 판을 못 깬다."""
    return v if v in allowed else default


def _cand_line(r):
    """후보 한 줄. **적합도 점수는 일부러 안 보여준다** — 보여주면 LLM 이 그 순위를
    그대로 받아 적고, 기계 점수를 한 번 더 통과시키는 꼴이 된다."""
    return (f'- 영상ID={r["영상ID"]} | {r["제목"]} | {r["채널"]} | '
            f'조회 {int(r["조회수"] or 0):,} · 구독 {int(r["구독자"] or 0):,} · '
            f'{int(r["길이초"] or 0)//60}분 · {r["업로드"]}\n'
            f'    챕터: {_cut(r.get("챕터", "") or "(없음)", 200)}')


# ── ① 기획 — 수집된 자료 전량을 보고 이번 회차를 설계한다 ────────────────
def plan_session(rows_by_axis, label, cache_dir):
    """모아 온 자료 **전량**을 보고 이번 회차를 기획하고 한 쌍을 고른다.

    반환 {기획, 분석:{영상ID,이유,우리팀}, 생성:{...}, 한쌍이유, 제친후보[]} 또는 None.

    ⚠️ **fit() 상위 몇 건만 보여주면 그건 기획이 아니다.** 그때는 LLM 이 기계 점수가
       이미 좁혀 놓은 것을 고르는 것뿐이라, 낱말 점수가 놓친 사례는 애초에 후보에
       못 들어온다. 그래서 게재 게이트를 통과한 **전량**을 넘긴다. fit() 은 선택에서
       빠지고 화면 표시·self_test 용으로만 남는다 (성과지수를 v4.2 에서 게이트에서
       뺀 것과 같은 이유다 — 「그 점수가 원하는 종류를 구조적으로 배제한다」).

    ⚠️ 후보 목록에 없는 영상ID 는 **버린다**. LLM 이 그럴듯한 ID 를 지어내면 다운스트림이
       KeyError 없이 엉뚱한 영상을 띄운다 — 에러가 안 나는 종류의 사고다.
    """
    blocks = []
    for ax in C.AXES:
        rows = sorted(rows_by_axis.get(ax, []), key=lambda r: r.get("업로드", ""), reverse=True)
        blocks.append(f"### {ax}축 — 모아 온 자료 {len(rows)}건 (최신순, 순위 아님)\n"
                      + "\n".join(_cand_line(r) for r in rows))
    prompt = f"""{concept()}

---

# 할 일

채널을 훑어 모아 온 자료는 아래가 **전부**다. 점수로 미리 걸러 놓지 않았다.
이걸 다 읽고 {label} T1 부서장회의를 **기획**하라.

순서는 셋이다.

1. **이번 회차를 무엇에 대한 회차로 만들 것인가**를 먼저 정한다 — 이게 기획이다.
   「AI 사례 두 개 소개」가 아니라, 부서장들이 그날 하나 가져갈 생각이 무엇인지 한 줄로 정한다.
2. 그 기획을 세우는 데 가장 좋은 **분석 1건 + 생성 1건**을 고른다.
   목록 순서는 최신순일 뿐 추천 순위가 아니다. **위에 있다고 좋은 게 아니다.**
3. 마지막까지 같이 놓고 고민했지만 **안 고른 후보 2건**과 그 이유를 적는다.
   무엇을 버렸는지가 기획이 실제로 있었다는 증거다.

{chr(10).join(blocks)}

# 출력

JSON 하나만. 설명 문장 없이.

{{
  "기획": "<이번 회차는 무엇에 대한 회차인가. 부서장이 하나 가져갈 생각. 한 문장>",
  "분석": {{
    "영상ID": "<위 분석축 목록에 실제로 있는 ID 그대로>",
    "이유": "<기획에 이게 왜 맞는가. 한 문장>",
    "우리팀": "<우리 회사 어느 업무에 그대로 옮길 수 있나. 한 문장>"
  }},
  "생성": {{ "영상ID": "...", "이유": "...", "우리팀": "..." }},
  "한쌍이유": "<이 둘이 한 회차 안에서 서로 무엇을 보완하나. 한 문장>",
  "제친후보": [
    {{"영상ID": "...", "왜안골랐나": "<한 문장>"}},
    {{"영상ID": "...", "왜안골랐나": "<한 문장>"}}
  ]
}}"""
    data = ask(prompt, cache_dir, "01_기획")
    if not isinstance(data, dict):
        return None
    ok = {"기획": _cut(data.get("기획"), 160)}
    seen = {}
    for ax in C.AXES:
        v = data.get(ax) or {}
        vid = str(v.get("영상ID", "")).strip()
        ids = {r["영상ID"]: r for r in rows_by_axis.get(ax, [])}
        if vid not in ids:
            print(f"  [LLM] 기획 {ax}: 목록에 없는 영상ID «{vid}» → fit() 1위로 되돌립니다")
            return None
        seen.update(ids)
        ok[ax] = {"영상ID": vid, "이유": _cut(v.get("이유"), 130),
                  "우리팀": _cut(v.get("우리팀"), 130)}
    ok["한쌍이유"] = _cut(data.get("한쌍이유"), 150)
    for r in rows_by_axis.values():
        seen.update({x["영상ID"]: x for x in r})
    dropped = []
    for d in (data.get("제친후보") or [])[:3]:
        vid = str((d or {}).get("영상ID", "")).strip()
        if vid in seen:      # 지어낸 ID 는 조용히 뺀다 (기획 자체를 무르지는 않는다)
            dropped.append({"영상ID": vid, "제목": _cut(seen[vid]["제목"], 46),
                            "왜안골랐나": _cut(d.get("왜안골랐나"), 120)})
    ok["제친후보"] = dropped
    return ok


# ── ② T1 원고 ───────────────────────────────────────────────────────────
# 지도만 쓴다(2026-09-09). 옛 값이 대본에 남아 있어도 렌더러는 살아 있다.
T1_SHAPES = ("지도",)


def _spot(v):
    """대본에 적힌 재생 구간을 한 줄로. 없으면 「(미지정)」."""
    for c in ((v or {}).get("재생") or []):
        lab = (" — " + c["라벨"]) if c.get("라벨") else ""
        return f'{c.get("시작")} ~ {c.get("끝")}{lab}'
    return "(미지정 — 영상 전체가 근거다)"


def write_t1(ses, cache_dir, chosen=None, detail=None):
    """T1 덱 원고. 반환 {축: {제목,무엇을,도형,중심,단계[]}} 또는 None."""
    detail = detail or {}
    # 사람이 정해 둔 재생 구간이 있으면 **그 대목이 원고의 중심**이어야 한다 —
    # 세션에서 트는 건 그 구간뿐인데 원고가 딴 데를 설명하면 발표가 어긋난다(2026-09-09).
    # 구간은 **대본에 적혀 있다**(사람이 고치는 자리). cache_dir 은 out/<회차>/llm 이다.
    deck0 = {}
    try:
        dp = os.path.join(os.path.dirname(cache_dir), "T1_대본.json")
        if os.path.exists(dp):
            deck0 = json.load(io.open(dp, encoding="utf-8"))
    except Exception:
        deck0 = {}
    seen = []
    for ax in C.AXES:
        r = ses["picks"][ax][0]
        why = (chosen or {}).get(ax, {})
        d = detail.get(r["영상ID"], {})
        seen.append(f"""### {ax}축 사례
- 유튜브 제목(**그대로 쓰지 말 것**): {r['제목']}
- 채널: {r['채널']} · {int(r['길이초'] or 0)//60}분 · 조회 {int(r['조회수'] or 0):,}
- 챕터: {_cut(d.get('챕터') or r.get('챕터', '') or '(없음)', 900)}
- 설명 {'전문' if d.get('설명') else '(300자로 잘린 것)'}: {_cut(d.get('설명') or r.get('설명', ''), 2500)}
- 기획상 고른 이유: {why.get('이유', '(없음)')}
- 우리 팀 적용: {why.get('우리팀', '(없음)')}
- **세션에서 실제로 트는 구간**: {_spot(deck0.get(ax))}""")
    prompt = f"""{concept()}

---

# 할 일

{ses['label']} T1 부서장회의 덱의 **사례 두 장 원고**를 쓴다.
슬라이드에 그대로 찍히는 글이다. 초안이 아니라 **읽을 수 있는 원고**로 써라.

## 이번 회차 기획 (이미 정해졌다 — 두 장 다 이 기획을 향해야 한다)
> {(chosen or {}).get('기획', '(없음)')}

두 사례가 서로 무엇을 보완하는가: {(chosen or {}).get('한쌍이유', '(없음)')}

{chr(10).join(seen)}

⚠️ **단계는 위 챕터·설명에 실제로 있는 것만 쓴다.** 영상이 안 한 일을 그럴듯하게
지어내면 발표자가 그 자리에서 막힌다. 근거가 얇으면 단계를 줄여라.

⚠️ **「세션에서 트는 구간」이 적혀 있으면 단계를 그 구간에 맞춘다.** 세션에서 보여 주는 건
그 대목뿐인데 단계가 딴 데를 설명하면 **화면과 말이 어긋난다.** 그 구간에 걸치는 챕터를
골라 단계로 만들고, `재생` 은 **이미 정해진 값을 그대로 다시 적는다**(바꾸지 마라).

# 각 항목이 화면에서 하는 일

- `제목` — 슬라이드 큰 제목. **40자 이내.** 유튜브 제목이 아니라 **우리 업무 말**로 다시 쓴다.
  예) "웹 데이터 긁어오는 AI 에이전트" (X) → "매주 손으로 모으던 자료를 대신 모아 온다" (O)
- `무엇을` — 제목 밑 한 줄. **60자 이내.** 무엇을 어떻게 했는지 한 문장.
- `단계` — 진행 과정. **3~5개.** 부서장이 「우리 팀도 되겠네」를 판단하는 자리다.
  - `이름` **26자 이내**, 동사로 끝나는 짧은 문장
  - `설명` **44자 이내**, 그 단계에서 실제로 무슨 일이 일어나는지
  - `묶음` 1 = 사람이 판단하는 단계 / 2 = 도구가 실행하는 단계
- `도형` — **항상 "지도"** 로 적는다. (목록·가로 STEP 형태는 2026-09-09 에 걷어냈다)
- `중심` — **필수.** 지도 가운데 알약에 들어갈 **12자 이내** 문구.
  그 사례를 한 덩이로 부르는 이름이다 (예: "자료 수집 에이전트" · "월간 보고서 자동화").
- `재생` — **세션에서 실제로 틀 구간.** 13분에 두 사례를 다루므로 한 사례당
  **1~3분짜리 한 구간**만 고른다. 위 챕터의 시각을 근거로 `시작`·`끝`을 `mm:ss`
  (한 시간이 넘으면 `h:mm:ss`)로 적고 `라벨`에 **왜 이 구간인가**를 12자 이내로 적는다.
  - 오프닝·채널 소개·광고·마무리 인사는 **고르지 마라.**
  - 「만드는 과정이 실제로 보이는 대목」을 고른다. 말로만 설명하는 대목이 아니다.
  - 챕터가 없어 근거를 못 대겠으면 **빈 배열로 두라** — 찍어서 적으면 회의에서
    엉뚱한 데가 재생된다.

# 출력

JSON 하나만. 설명 문장 없이.

{{
  "분석": {{
    "제목": "...", "무엇을": "...", "도형": "지도", "중심": "12자 이내",
    "재생": [ {{"시작": "12:30", "끝": "15:10", "라벨": "왜 이 구간인가"}} ],
    "단계": [ {{"이름": "...", "설명": "...", "묶음": 1}}, ... ]
  }},
  "생성": {{ ... 같은 모양 ... }}
}}"""
    data = ask(prompt, cache_dir, "02_T1원고")
    if not isinstance(data, dict):
        return None
    out, cut = {}, []
    for ax in C.AXES:
        v = data.get(ax)
        if not isinstance(v, dict) or not v.get("단계"):
            print(f"  [LLM] T1 원고에 {ax}축이 없습니다 → 기계 초안")
            return None
        steps = []
        for s in v["단계"][:6]:
            nm, ds = str(s.get("이름", "")).strip(), str(s.get("설명", "")).strip()
            if not nm:
                continue
            if len(nm) > 26:
                cut.append(f"{ax} 단계이름 {len(nm)}자→26")
            if len(ds) > 44:
                cut.append(f"{ax} 단계설명 {len(ds)}자→44")
            steps.append({"시각": "", "이름": _cut(nm, 26), "설명": _cut(ds, 44),
                          "묶음": 1 if str(s.get("묶음", 1)) == "1" else 2})
        if len(str(v.get("제목", ""))) > 40:
            cut.append(f"{ax} 제목 {len(str(v['제목']))}자→40")
        out[ax] = {"제목": _cut(v.get("제목"), 40), "무엇을": _cut(v.get("무엇을"), 60),
                   "도형": _one(v.get("도형"), T1_SHAPES, "지도"),
                   "중심": _cut(v.get("중심"), 12), "단계": steps[:5],
                   "재생": _clamp_play(v.get("재생"), ses["picks"][ax][0], ax, cut)}
    if cut:
        print("  [LLM] T1 판 맞춤: " + " · ".join(cut))
    return out


def _clamp_play(v, row, ax, cut):
    """재생 구간 검문. 못 믿을 값은 **버린다** — 빈 배열이면 영상이 처음부터 재생될 뿐이다.

    ⚠️ 시작≥끝 · 영상 길이 밖 · 5분 넘는 구간은 전부 버린다. 찍어서 적은 구간을
       그대로 실으면 **회의에서 엉뚱한 데가 재생되는데 파일은 멀쩡하다.**
    """
    import build_t1 as T1
    total = int(row.get("길이초") or 0)
    out = []
    for x in (v or [])[:2]:
        if not isinstance(x, dict):
            continue
        a, b = T1.secs(x.get("시작")), T1.secs(x.get("끝"))
        if a is None or b is None or b <= a:
            cut.append(f"{ax} 재생구간 읽기 실패")
            continue
        if total and b > total:
            cut.append(f"{ax} 재생구간이 영상({total//60}분) 밖")
            continue
        if b - a > 300:
            cut.append(f"{ax} 재생구간 {(b - a)//60}분 → 너무 김")
            continue
        out.append({"시작": str(x.get("시작")).strip(), "끝": str(x.get("끝")).strip(),
                    "라벨": _cut(x.get("라벨"), 14)})
    return out


# ── ③ 인스타툰 연출 지시 (2026-09-10 신설) ──────────────────────
# 툰의 **그림은 GPT 가 그린다.** 여기서 만드는 건 그림 규칙이 아니라 **컷 서술**이다 —
# 「이번 장면 설명」·「화면 문구」·「메모 문구」 세 칸(제작기준이 요구하는 칸).
#
# ⚠️ **구도·표정·소품 이름을 쓰지 않는다.** 그건 걷어낸 우리 렌더러의 어휘였다
#    (`혼자`·`서류산`·`먹구름`…). GPT 는 그 낱말을 모르고, 알아도 우리 판이 아니다.
#    사람이 읽고 그릴 수 있는 **평범한 한국어 서술**로만 쓴다.
# ⚠️ 원고(제목·말풍선)는 **손대지 않는다.** 기획서에 이미 실려 나간 문장이고,
#    여기서 고치면 기획서와 그림이 갈린다.
TOON_MAX = {"화면문구": 24, "메모문구": 20, "장면설명": 220}


def write_toon_direction(ax, pages, cache_dir, chosen=None):
    """축 하나의 12장에 연출 세 칸을 채운다. 반환 {장번호: {화면문구,메모문구,장면설명}}.

    못 부르거나 회수 실패면 **빈 dict** 를 준다 — 프롬프트는 그 칸을 빼고 나간다.
    """
    lines = []
    for i, p in enumerate(pages, 1):
        kind = p.get("종류") or "장면"
        t = (p.get("제목") or "").replace(chr(10), " ").strip()
        say = (p.get("말") or "").replace(chr(10), " ").strip()
        who = " (할아버지=회색 곰 상사 등장)" if p.get("할아버지") else ""
        lines.append(f'  {i}. [{kind}] 제목 «{t}» / 말풍선 «{say}»{who}')
    body = chr(10).join(lines)
    prompt = f"""{concept()}

---

# 할 일

사내 채널에 나갈 **{ax}축 인스타툰 12장**의 그림을 다른 도구가 그린다.
그 도구에 줄 **컷 서술 세 칸**을 장마다 채워라. 원고(제목·말풍선)는 이미 정해져 있다 —
**고치지 말고 그대로 두고**, 그 문장이 그림으로 어떻게 보여야 하는지만 적는다.

## 이번 회차 기획
> {(chosen or {}).get('기획', '(없음)')}

## 12장 원고 (이 순서 그대로다)
{body}

# 세 칸이 하는 일

- `화면문구` — 노트북·모니터 화면에 **적히는 글자**. {TOON_MAX['화면문구']}자 이내.
  화면이 안 나오는 장면이면 **빈 문자열**. 「주소 / 제목 / 날짜 / 링크」처럼 **짧은 항목 나열**이 좋다.
- `메모문구` — 메모장·포스트잇에 적히는 글자. {TOON_MAX['메모문구']}자 이내. 없으면 빈 문자열.
- `장면설명` — 이번 컷의 연출. {TOON_MAX['장면설명']}자 이내. **평범한 한국어로** 쓴다:
  누가 어디서 무엇을 하고 있고, 표정은 어떻고, 책상 위에 무엇이 놓였는지.

# 지킬 것

- ⚠️ **소품은 서너 개까지.** 노트북·메모장·펜·머그컵·서류 더미 정도. 많이 적을수록 판이 복잡해진다.
- ⚠️ **화면·메모 문구를 지어내 채우지 마라.** 그 장에 화면이 없으면 빈칸이 맞다.
- ⚠️ **표정과 손동작을 반드시 적는다.** 그림이 감정을 전달하는 자리다.
- ⚠️ 우리 데이터를 실명으로 쓰지 않는다 — 센터명·매출액·학생수는 화면 문구에도 넣지 않는다.
- ⚠️ 「구도」·「소품 이름」 같은 **도구 어휘를 쓰지 마라.** 사람이 읽는 서술이다.
- 마지막 12장은 **댓글 유도**다. 광고 배너처럼 만들지 말고 밝게 웃으며 마무리하는 장면으로.

# 출력

JSON 하나만. 설명 문장 없이. 키는 장 번호 문자열이다.

{{
  "1": {{"화면문구": "", "메모문구": "오늘도 파이팅",
        "장면설명": "유삐가 책상 앞에서 노트북을 보며 지친 표정을 짓는다. 옆에는 서류 더미가 쌓여 있고 머그컵이 놓여 있다."}},
  "2": {{"화면문구": "주소 / 제목 / 날짜", "메모문구": "볼 것만 정리", "장면설명": "..."}}
}}"""
    data = ask(prompt, cache_dir, f"04_툰연출_{ax}")
    if not isinstance(data, dict):
        return {}
    out, cut = {}, []
    for i in range(1, len(pages) + 1):
        v = data.get(str(i)) or {}
        if not isinstance(v, dict):
            continue
        row = {}
        for k, lim in TOON_MAX.items():
            t = " ".join(str(v.get(k) or "").split())
            if len(t) > lim:
                cut.append(f"{ax}{i}장 {k} {len(t)}자→{lim}")
                t = t[:lim]
            row[k] = t
        out[i] = row
    if cut:
        print("  [LLM] 툰 연출 판 맞춤: " + " · ".join(cut))
    return out


# ── ③ T2 인스타툰 — **이제 여기 없다** (2026-09-10) ────────────
# 툰은 **GPT 가 그림까지 만든다.** 그래서 원고 프롬프트(154줄)·구도·표정·단계 검문을
# 전부 걷어냈다 — 전부 **우리 렌더러를 전제로 한 규칙**이었기 때문이다.
# 옛 프롬프트는 `archive/20260910_t2/T2_원고_프롬프트.txt` 에 떠 둔다(참고용).
# ⚠️ **원고 자리를 비워 두는 것이 아니다**(2026-09-18 사용자 지시) — 이 함수가 없어졌을 뿐이고
#    원고는 **회차마다 반드시** 낸다. 대화에서 써서 `out/<회차>/T2_대본.json` 에 남긴다.
#    규격은 `config/인스타툰_마스터.md` · 확인은 회차 기획서의 원고 표(사례 §4 · 체험 §6).

def _clamp_line(t, lines, chars, tag, what, cut):
    """줄 수와 줄 길이를 동시에 자른다. 컷은 작아서 둘 다 안 지키면 그림 위로 흐른다."""
    out = []
    for ln in [x.strip() for x in str(t or "").split("\n") if x.strip()][:lines]:
        if len(ln) > chars:
            cut.append(f"{tag} {what} {len(ln)}자→{chars}")
        out.append(_cut(ln, chars))
    return "\n".join(out)


