# -*- coding: utf-8 -*-
"""T1 부서장회의 세션 덱 — 이번 주 한 쌍(분석 1 + 생성 1)을 13분짜리 슬라이드로.

  python tools/build_t1.py            # 이번 회차
  python tools/build_t1.py --open     # 만들고 브라우저로 연다

산출: out/<YYYYMMDD>/T1_부서장회의_<YYYYMMDD>.html  (단일 파일 · 폰트·썸네일 내장 · 오프라인)
      일곱 장 — 표지 · **현황 지도** · 두 사례 요약 · 분석 사례 · 생성 사례 ·
      **4주 로테이션** · **AX 확산 전략**.  (뒤 넷은 고정 장이다)
      2쪽(현황 지도)과 마지막 쪽(전략)은 **회차마다 안 바뀌는 고정 장**이라
      T1_대본.json 이 아니라 이 파일의 NET_HUBS / TACTICS 상수에서 고친다.

형태는 `와이즈만_수학비서_내신시스템_프레젠테이션.html` 을 그대로 따른다 —
1280×720 무대, 클릭·←→ 넘김, 진행 막대, 형광펜 강조, 카드/흐름/두 칸 비교.

⚠️ **이 덱은 초안이다. 발표본이 아니다.**
   유튜브 제목·설명이 그대로 실려 있는 자리가 있다. 그대로 띄우면 그 주 세션이
   **「남의 채널 소개」**가 된다. 금요일에 사람이 우리 업무 말로 바꾸는 것까지가 한 세트다.
   제목·무엇을·진행과정 단계는 T1_대본.json 에서 고친다(고친 건 다음 회차에도 유지된다).

⚠️ 3·4주차는 **사내 전용**이라 이 덱을 만들지 않는다. 유튜브가 채우는 건 1·2주차뿐이다.
"""
import argparse, base64, io, json, os, sys, webbrowser
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build_page as B
import collect as C
import llm as L

FONTS = os.path.join(C.ROOT, "assets", "fonts")


def font_face(fname, weight):
    p = os.path.join(FONTS, fname)
    if not os.path.exists(p):
        return ""  # 폰트가 없으면 시스템 고딕으로 떨어진다 — 덱은 그대로 열린다
    b64 = base64.b64encode(io.open(p, "rb").read()).decode()
    return ("@font-face{font-family:'GmarketSans';font-weight:%d;font-style:normal;"
            "src:url(data:font/woff;base64,%s) format('woff');font-display:block;}"
            % (weight, b64))


CSS = """
:root{
  --paper:#FAFAF6; --ink:#1E2B33; --ink-soft:#5D6B72;
  --green:#00A05A; --green-deep:#00794A; --hl:#FFE24D; --coral:#F0562F;
  --line:#DEE2DA; --grid:rgba(30,43,51,.055);
  --ana:#2F6FB0; --gen:#7A4E96;
}
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;background:#E9EAE4;overflow:hidden;
  font-family:'GmarketSans','Apple SD Gothic Neo','Malgun Gothic',sans-serif;color:var(--ink);
  font-weight:500;word-break:keep-all;overflow-wrap:break-word}
#stage{position:fixed;inset:0;display:flex;align-items:center;justify-content:center}
#deck{width:1280px;height:720px;position:relative;flex:none;background:var(--paper);
  box-shadow:0 24px 70px rgba(20,30,35,.28);overflow:hidden}
.slide{position:absolute;inset:0;padding:52px 78px 84px;display:none;flex-direction:column}
.slide.on{display:flex;animation:in .45s ease both}
@keyframes in{from{opacity:0;transform:translateY(14px)}to{opacity:1;transform:none}}
@media (prefers-reduced-motion:reduce){.slide.on{animation:none}}
.grid-bg{background-image:
  linear-gradient(var(--grid) 1px,transparent 1px),
  linear-gradient(90deg,var(--grid) 1px,transparent 1px);background-size:44px 44px}

.eyebrow{font-size:20px;font-weight:700;color:var(--green-deep);letter-spacing:.12em;margin-bottom:18px}
.eyebrow .num{display:inline-block;background:var(--ink);color:#fff;border-radius:6px;
  padding:6px 13px 4px;margin-right:12px;letter-spacing:.02em;font-size:19px}
.eyebrow .num.ana{background:var(--ana)} .eyebrow .num.gen{background:var(--gen)}
h1{font-size:60px;line-height:1.36;font-weight:700;letter-spacing:-.01em}
h2{font-size:41px;line-height:1.3;font-weight:700;letter-spacing:-.01em;margin-bottom:12px}
.lead{font-size:23px;line-height:1.58;color:var(--ink-soft)}
b{font-weight:700}
.hl{background:linear-gradient(transparent 52%,var(--hl) 52%,var(--hl) 94%,transparent 94%);
  padding:0 4px;border-radius:2px}
.spacer{flex:1;min-height:14px}

.cards{display:flex;gap:24px}
.card{flex:1;background:#fff;border:2px solid var(--line);border-radius:18px;padding:24px 26px}
.card .tag{display:inline-block;font-size:17px;font-weight:700;color:#fff;background:var(--ink-soft);
  border-radius:999px;padding:8px 18px 6px;margin-bottom:13px}
.card .tag.ana{background:var(--ana)} .card .tag.gen{background:var(--gen)}
.card h3{font-size:23px;font-weight:700;line-height:1.4;margin-bottom:9px}
.card p{font-size:18px;line-height:1.52;color:var(--ink-soft)}

.flow{display:flex;align-items:stretch}
.step{flex:1;background:#fff;border:2px solid var(--line);border-radius:18px;padding:22px 20px;position:relative}
.step + .step{margin-left:44px}
.step + .step::before{content:'→';position:absolute;left:-36px;top:50%;transform:translateY(-50%);
  font-size:30px;font-weight:700;color:var(--green)}
.step .no{font-size:17px;font-weight:700;color:var(--green-deep);margin-bottom:9px;letter-spacing:.08em}
.step h3{font-size:22px;font-weight:700;line-height:1.42;margin-bottom:8px}
.step p{font-size:17px;line-height:1.56;color:var(--ink-soft)}

.duo{display:flex;align-items:stretch;gap:30px}
.duo .col{flex:1;background:#fff;border:2px solid var(--line);border-radius:20px;padding:20px 22px}
.duo .col.ana{border-color:var(--ana)} .duo .col.gen{border-color:var(--gen)}
.duo .arrow{width:104px;display:flex;align-items:center;justify-content:center;
  font-size:44px;font-weight:700;color:var(--green)}
.duo h3{font-size:20px;font-weight:700;margin-bottom:11px;color:var(--ink-soft);line-height:1.3}
.duo .col.ana h3{color:var(--ana)} .duo .col.gen h3{color:var(--gen)}
.duo li{list-style:none;font-size:19px;line-height:1.5;padding:7px 0 7px 28px;position:relative}
.duo li::before{content:'·';position:absolute;left:8px;font-weight:700;font-size:26px;top:2px}

/* 지표 칩 — 유튜브 원본 수치. 발표에선 근거로만 쓰고 앞세우지 않는다 */
.facts{display:flex;flex-wrap:wrap;gap:9px;margin:14px 0 0}
.f{font-size:17px;background:#EEF2EE;border-radius:8px;padding:8px 13px 6px;color:var(--ink-soft)}
.f b{color:var(--ink)}

/* 사람이 채우는 자리 — 비워둔 게 실수로 보이지 않게 「빈칸」임을 명시한다 */
.blanks{display:flex;gap:22px}
.blank{flex:1;border:2.5px dashed var(--ink-soft);border-radius:18px;padding:22px 24px;
  background:rgba(255,255,255,.55)}
.blank .q{font-size:20px;font-weight:700;margin-bottom:12px}
.blank .line{border-bottom:2px dotted var(--line);height:34px}
.note{margin-top:20px;border:2px solid var(--line);border-radius:16px;padding:16px 24px;
  font-size:19px;line-height:1.56;background:#fff;color:var(--ink-soft)}
.note b{color:var(--ink)}
.src{font-size:15px;color:var(--ink-soft);margin-top:14px;line-height:1.5}
.src a{color:var(--ink-soft)}

.cover{justify-content:center}
.cover .brandline{font-size:22px;font-weight:700;color:var(--green-deep);letter-spacing:.08em;margin-bottom:26px}
.cover h1{font-size:64px}
.cover .sub{margin-top:32px;font-size:24px;color:var(--ink-soft);line-height:1.64}
.cover .date{margin-top:36px;font-size:19px;color:var(--ink-soft)}
.closing{justify-content:center;text-align:center;background:var(--ink);color:#fff}
.closing h1{font-size:48px;line-height:1.5;color:#fff}
.hl-solid{background:var(--hl);color:var(--ink);padding:3px 12px;border-radius:6px;
  -webkit-box-decoration-break:clone;box-decoration-break:clone}
.closing .sub{margin-top:28px;font-size:21px;color:#B9C3C8;line-height:1.7}
/* 편집자용 — 발표 때 넘기지 않는 마지막 장 */
.editor{background:#2A2119;color:#F4ECE0}
.editor h2{color:#FFD98A}
.editor li{list-style:none;font-size:21px;line-height:1.5;padding:10px 0 10px 34px;position:relative}
.editor li::before{content:'☐';position:absolute;left:0;color:#FFD98A;font-weight:700}
.editor .warn{margin-top:20px;border:2.5px dashed #FFD98A;border-radius:16px;padding:18px 26px;
  font-size:19px;line-height:1.58}

/* ── 사례 장 — 왼쪽 썸네일(클릭하면 유튜브가 새 탭으로), 오른쪽 진행과정 도형 ──
   ⚠️ 썸네일은 빌드할 때 받아 **파일에 base64 로 박는다**(out/pool/thumbs/ 에 캐시).
      링크로 걸면 인터넷이 없는 회의실에서 그림만 빠진 덱이 된다. */
/* 사례 장은 위에서 아래로 꽉 채운다 — .spacer 를 쓰면 flex:1 이 둘이 되어 본문이 잘린다 */
.slide.case h2{font-size:33px;line-height:1.26;margin-bottom:8px}
.slide.case .lead{font-size:18px;line-height:1.45;color:var(--ink-soft)}
.casebody{display:flex;gap:30px;flex:1;min-height:0;margin-top:16px}
.thumbwrap{width:470px;flex:none}
.thumb{position:relative;display:block;border:3px solid var(--line);border-radius:18px;
  overflow:hidden;background:#0D1418;text-decoration:none}
.thumb img{display:block;width:100%;aspect-ratio:16/9;object-fit:cover}
.thumb .play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
.thumb .play i{width:86px;height:60px;border-radius:16px;background:rgba(240,86,47,.92);
  color:#fff;font-size:26px;font-style:normal;display:flex;align-items:center;justify-content:center}
.thumb:hover .play i{background:var(--coral)}
.thumb.noimg{border-style:dashed;background:#EEF2EE;height:264px;display:flex;
  align-items:center;justify-content:center;color:var(--ink-soft);font-size:19px;
  text-align:center;padding:0 30px;line-height:1.5}
.thumbcap{margin-top:11px;font-size:16px;color:var(--ink-soft);text-align:center}
.thumbcap b{color:var(--coral)}

.vflow{flex:1;display:flex;flex-direction:column;min-width:0}
.vflow .cap{font-size:16px;font-weight:700;color:var(--green-deep);letter-spacing:.08em;margin-bottom:11px}
.vstep{background:#fff;border:2px solid var(--line);border-radius:14px;padding:10px 16px 11px;position:relative}
.vstep + .vstep{margin-top:17px}
.vstep + .vstep::before{content:'↓';position:absolute;left:24px;top:-21px;font-size:21px;
  font-weight:700;color:var(--green)}
.vstep .t{display:inline-block;font-size:14px;font-weight:700;color:#fff;background:var(--ink-soft);
  border-radius:6px;padding:5px 9px 3px;margin-right:9px;vertical-align:2px}
.vstep .t.ana{background:var(--ana)} .vstep .t.gen{background:var(--gen)}
.vstep h3{display:inline;font-size:20px;font-weight:700;line-height:1.35}
.vstep p{font-size:16px;line-height:1.5;color:var(--ink-soft);margin-top:5px}

/* 요약 장 — 두 사례를 나란히 */
.duo .thumbmini{display:block;border:2px solid var(--line);border-radius:13px;overflow:hidden;
  margin:0 0 12px;position:relative;text-decoration:none}
.duo .thumbmini img{display:block;width:100%;aspect-ratio:16/9;object-fit:cover}
.duo .thumbmini .play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
.duo .thumbmini .play i{width:60px;height:42px;border-radius:12px;background:rgba(240,86,47,.9);
  color:#fff;font-size:19px;font-style:normal;display:flex;align-items:center;justify-content:center}
.duo .thumbmini.noimg{height:150px;border-style:dashed;background:#EEF2EE;display:flex;
  align-items:center;justify-content:center;color:var(--ink-soft);font-size:16px;
  text-align:center;padding:0 20px;line-height:1.5}
.duo .what{font-size:18px;line-height:1.45;font-weight:700}
.duo .who{margin-top:9px;font-size:15px;color:var(--ink-soft);line-height:1.45}

/* ── 구간 재생 ────────────────────────────────────────────────────────────
   썸네일을 누르면 그 자리가 유튜브 플레이어로 바뀌고 **지정한 구간만** 순서대로 돈다.
   ⚠️ 새 탭(watch 주소)으로는 「끝나는 지점」을 못 건다 — 그래서 덱 안에서 재생한다.
      재생에는 인터넷이 필요하다. 안 되면 아래 텍스트 링크로 유튜브를 연다. */
.playerbox{position:relative;width:100%;aspect-ratio:16/9;border:3px solid var(--line);
  border-radius:18px;overflow:hidden;background:#0D1418;cursor:pointer}
.playerbox img{display:block;width:100%;height:100%;object-fit:cover}
.playerbox iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.playerbox video{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:#0D1418}
.playerbox.on .play{display:none}
.playerbox .play{position:absolute;inset:0;display:flex;align-items:center;justify-content:center}
.playerbox .play i{width:86px;height:60px;border-radius:16px;background:rgba(240,86,47,.92);
  color:#fff;font-size:26px;font-style:normal;display:flex;align-items:center;justify-content:center}
.playerbox:hover .play i{background:var(--coral)}
.yterr{position:absolute;left:0;right:0;bottom:0;background:rgba(240,86,47,.94);color:#fff;
  font-size:15px;line-height:1.45;padding:12px 16px;text-align:center;z-index:5}
.startlink{display:block;margin-top:10px;font-size:18px;font-weight:700;color:var(--green-deep);
  text-decoration:none;line-height:1.4}
.startlink span{font-weight:500;color:var(--ink-soft)}
.startlink:hover{text-decoration:underline}
.playerbox.noimg{display:flex;align-items:center;justify-content:center;background:#EEF2EE;
  border-style:dashed;color:var(--ink-soft);font-size:18px;text-align:center;padding:0 26px;line-height:1.5}

/* 어떤 구간을 트는지 — 발표자가 먼저 알고 눌러야 한다 */
.clipinfo{flex:1;min-width:0;display:flex;flex-direction:column}
.clipinfo .cap{font-size:16px;font-weight:700;color:var(--green-deep);letter-spacing:.08em;margin-bottom:11px}
.clip{background:#fff;border:2px solid var(--line);border-radius:14px;padding:11px 16px 12px}
.clip + .clip{margin-top:10px}
.clip .t{display:inline-block;font-size:15px;font-weight:700;color:#fff;background:var(--ink-soft);
  border-radius:6px;padding:5px 10px 3px;margin-bottom:7px}
.clip .t.ana{background:var(--ana)} .clip .t.gen{background:var(--gen)}
.clip .n{font-size:18px;font-weight:700;line-height:1.4}
.clipinfo .hint{font-size:15px;color:var(--ink-soft);margin-top:10px}

/* ── 가로 셰브론 진행과정 (도형: "셰브론") ───────────────────────────────── */
.slide.case.wide{padding-bottom:66px}
.topline{display:flex;gap:24px;margin-top:12px}
.topline .thumbwrap{width:380px;flex:none}
.flowarea{margin-top:12px}
.flowarea .cap{font-size:16px;font-weight:700;color:var(--green-deep);letter-spacing:.08em;margin-bottom:9px}
.chev{display:flex;gap:5px}
.chevcol{flex:1;min-width:0}
.chevbox{background:#F0F2EF;padding:8px 8px 7px;text-align:center;
  clip-path:polygon(0 0,calc(100% - 14px) 0,100% 50%,calc(100% - 14px) 100%,0 100%,14px 50%)}
.chevcol:first-child .chevbox{clip-path:polygon(0 0,calc(100% - 14px) 0,100% 50%,calc(100% - 14px) 100%,0 100%)}
.chevcol:last-child .chevbox{clip-path:polygon(0 0,100% 0,100% 100%,0 100%,14px 50%)}
.chevno{font-size:11.5px;font-weight:700;letter-spacing:.1em;color:var(--ink-soft)}
.chevname{font-size:18px;font-weight:700;line-height:1.25;margin-top:2px}
.chevdesc{font-size:13px;line-height:1.42;color:var(--ink-soft);text-align:center;padding:7px 5px 0}
/* 구간 묶음 — 어디까지가 「판단」이고 어디부터 「실행」인지 */
.bands{display:flex;gap:26px;margin-top:10px;border-top:1.5px solid var(--line);padding-top:10px}
.band{flex:1;border-left:3px solid var(--line);padding-left:14px}
.band.on{border-left-color:var(--ana)}
.band .t{font-size:17px;font-weight:700}
.band.on .t{color:var(--ana)}
.band .d{font-size:14px;line-height:1.45;color:var(--ink-soft);margin-top:3px}

/* ── 지도 도형 (도형: "지도") ─────────────────────────────────────────────
   가운데 초록 알약 하나에서 잎으로 점선이 뻗는 형태. 1280×720 무대라 좌표를 박아 둔다
   (잎 개수만 세로로 재배치). 왼쪽 플레이어를 키우고 지도는 오른쪽에만 놓는다. */
/* 세로 가운데 정렬 — 플레이어 밑 캡션을 걷어낸 뒤(2026-09-09) 아래가 텅 비어 보였다.
   지도(414px)가 남는 높이의 위쪽에 붙어 있던 탓이라 위아래로 나눠 갖게 했다. */
.mapline{display:flex;align-items:center;gap:26px;margin-top:14px;flex:1;min-height:0}
.mapline .thumbwrap{width:530px;flex:none}
.mapwrap{position:relative;width:568px;height:414px;flex:none}
.mapwrap svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.mapcenter{position:absolute;left:0;width:176px;background:var(--green);color:#fff;white-space:pre-line;
  border-radius:999px;padding:13px 16px 11px;text-align:center;font-size:18px;font-weight:700;
  line-height:1.3;box-shadow:0 6px 16px rgba(0,160,90,.22)}
.leaf{position:absolute;left:230px;width:338px;background:#fff;border:2px solid var(--line);
  border-radius:26px;padding:8px 18px 8px}
.leaf.g1{border-color:var(--ana)} .leaf.g2{border-color:var(--ink-soft)}
.leaf .no{display:inline-block;font-size:11px;font-weight:700;letter-spacing:.09em;
  color:var(--ink-soft);margin-right:7px;vertical-align:1px}
.leaf.g1 .no{color:var(--ana)}
.leaf b{display:inline;font-size:17px;font-weight:700;line-height:1.28}
.leaf i{display:block;font-style:normal;font-size:12.5px;line-height:1.35;
  color:var(--ink-soft);margin-top:3px}
.maplegend{position:absolute;left:0;bottom:0;width:200px;font-size:13px;line-height:1.4}
.maplegend .lg{display:block;border-left:3px solid var(--line);padding-left:9px;margin-top:9px;color:var(--ink-soft)}
.maplegend .lg b{display:block;font-size:14px;color:var(--ink)}
.maplegend .lg.g1{border-left-color:var(--ana)} .maplegend .lg.g1 b{color:var(--ana)}

/* ── 현황 지도 (2쪽) — 「지금 업무 자동화는 이렇게 하고 있다」 관계 그림 ──
   ⚠️ 좌표가 1124x336 무대에 **박혀** 있다. 잎을 늘리면 라벨이 에러 없이 겹친다.
      늘릴 때는 NET_HUBS 의 각도·거리를 같이 손보고 눈으로 확인할 것. */
.slide.dense h2{font-size:34px;line-height:1.26;margin-bottom:8px}
.slide.dense .lead{font-size:18px;line-height:1.5}
.netwrap{flex:1;min-height:0;display:flex;align-items:center;margin-top:2px}
.net{width:100%;display:block}
.net text{font-family:inherit;font-weight:500}
.net .hubname{font-size:16.5px;font-weight:700}
.net .hubsub{font-size:12px;fill:var(--ink-soft)}
.net .lcat{font-weight:700}
.net .ltxt{fill:var(--ink-soft)}
.stats{display:flex;gap:10px;margin-top:4px}
.stat{flex:1;background:#fff;border:2px solid var(--line);border-radius:14px;padding:9px 13px 10px}
.stat b{display:block;font-size:23px;line-height:1.1;color:var(--green-deep)}
.stat span{display:block;margin-top:4px;font-size:13.5px;line-height:1.38;color:var(--ink-soft)}
.srcline{font-size:12px;color:var(--ink-soft);margin-top:8px}

/* ── 전략 장 (마지막 쪽) — AX확산 계획서(docs/AX확산) v4.2 의 요약. 정본은 저쪽이다 ──
   한 줄에 [번호][하는 일][얻는 것][주기]. 7줄이 720px 안에 딱 들어가므로
   ⚠️ 줄을 늘리거나 글자를 키우면 **말없이 페이지 번호 위로 넘친다**. */
.tlist{flex:1;min-height:0;margin-top:10px}
.trow{display:flex;align-items:center;gap:12px;background:#fff;border:2px solid var(--line);
  border-radius:12px;padding:6px 13px 7px}
.trow + .trow{margin-top:6px}
.trow.now{border-color:var(--green);background:#F1FBF5}
.trow .tno{flex:none;width:40px;font-size:15px;font-weight:700;color:#fff;background:var(--ink-soft);
  border-radius:7px;padding:5px 0 3px;text-align:center}
.trow.now .tno{background:var(--green)}
.trow .tbody{flex:none;width:334px}
.trow .tname{font-size:16.5px;font-weight:700;line-height:1.28}
.trow .tdesc{font-size:12.5px;line-height:1.34;color:var(--ink-soft);margin-top:2px}
.trow .tgain{flex:1;min-width:0;font-size:14px;line-height:1.4;color:var(--ink)}
.trow .tgain .gl{display:inline-block;font-size:11px;font-weight:700;color:var(--green-deep);
  background:#E7F5EC;border-radius:5px;padding:4px 7px 2px;margin-right:8px;vertical-align:1px}
.trow.now .tgain .gl{background:var(--green);color:#fff}
.trow .tcyc{flex:none;font-size:12.5px;font-weight:700;color:var(--ink-soft);
  background:#EEF2EE;border-radius:999px;padding:6px 11px 4px}
.trow.now .tcyc{background:var(--green);color:#fff}

#hud{position:absolute;left:0;right:0;bottom:0;height:54px;display:flex;align-items:center;
  padding:0 78px;justify-content:space-between;pointer-events:none}
#pageno{font-size:16px;font-weight:700;color:var(--ink-soft);letter-spacing:.08em}
#navbtns{pointer-events:auto;display:flex;gap:10px}
#navbtns button{width:44px;height:44px;border-radius:50%;border:2px solid var(--line);background:#fff;
  font-size:19px;font-weight:700;color:var(--ink);cursor:pointer;font-family:inherit}
#navbtns button:hover{border-color:var(--green);color:var(--green-deep)}
#bar{position:absolute;top:0;left:0;height:7px;background:var(--green);transition:width .3s ease}
"""

JS = """

/* ── 구간 재생 ────────────────────────────────────────────────────────────
   썸네일을 누르면 그 자리에 유튜브 플레이어를 만들고 data-clips 의 구간을 순서대로 튼다.
   `end` 에 닿으면 플레이어가 ENDED 를 내므로 그걸 신호로 다음 구간을 건다.
   ⚠️ 덱은 아무 데나 클릭하면 다음 장으로 넘어간다 — 플레이어 안에서는 막는다(아래 guard).
   ⚠️ 인터넷이 없으면 API 가 안 올라온다. 그때는 아래 「유튜브에서 열기」 링크를 쓴다. */
var YT_READY = false, YT_Q = [];
function onYouTubeIframeAPIReady(){ YT_READY = true; YT_Q.splice(0).forEach(function(f){f();}); }
function clipsOf(box){
  try{ return JSON.parse(box.dataset.seq||'[]'); }catch(e){ return []; }
}
function playLocal(box){
  var v = box.querySelector('video'); if(!v) return;
  var clips = clipsOf(box), i = 0;
  box.dataset.on = '1'; box.classList.add('on'); v.controls = true;
  function load(k){
    var c = clips[k]; if(!c) return;
    if(c.f && v.getAttribute('src') !== c.f){ v.setAttribute('src', c.f); v.load(); }
    v.currentTime = c.s || 0;
    v.play();
  }
  function next(){
    i += 1;
    if(i < clips.length) load(i); else v.pause();   // 마지막이 끝나면 멈춘다
  }
  v.addEventListener('timeupdate', function(){
    var c = clips[i];
    if(!c || !c.e || v.currentTime < c.e) return;   // 끝 지점이 있는 구간만 잘라 넘긴다
    next();
  });
  // 잘린 파일은 끝 지점이 없다 — 파일이 끝나는 게 곧 구간의 끝이다
  v.addEventListener('ended', function(){ if(clips[i] && !clips[i].e) next(); });
  if(clips.length) load(0); else v.play();
}
function playBox(box){
  if(box.dataset.on) return;
  if(box.querySelector('video')) return playLocal(box);
  var vid = box.dataset.vid; if(!vid) return;
  var start = function(){
    var clips = clipsOf(box), i = 0;
    box.dataset.on = '1';
    var host = document.createElement('div'); box.innerHTML = ''; box.appendChild(host);
    var opt = function(k){
      var o = {videoId: vid};
      if(clips[k]){ o.startSeconds = clips[k].s; if(clips[k].e) o.endSeconds = clips[k].e; }
      return o;
    };
    var pl = new YT.Player(host, {
      videoId: vid,
      playerVars: {autoplay:1, rel:0, modestbranding:1,
                   start: clips[0]? clips[0].s : 0,
                   end: (clips[0] && clips[0].e)? clips[0].e : undefined},
      events: {
        onReady: function(e){ e.target.playVideo(); },
        onStateChange: function(e){
          if(e.data !== YT.PlayerState.ENDED) return;
          i += 1;
          if(i < clips.length){ pl.loadVideoById(opt(i)); }
        },
        /* 오류 153 = 임베드 출처 거부. 덱을 file:// 로 열면 유튜브가 막는다.
           원인을 유튜브 오류창이 안 알려줘서 여기서 대신 말해 준다. */
        onError: function(e){
          window.__ytErr = e.data;
          var m = document.createElement('div');
          m.className = 'yterr';
          m.innerHTML = (e.data === 153 || e.data === 101 || e.data === 150)
            ? '이 덱을 <b>파일로 직접 열면</b> 유튜브가 재생을 막습니다 (오류 ' + e.data + ').<br>'
              + '같은 폴더의 <b>열기.bat</b> 으로 여세요 — 로컬 서버로 띄우면 재생됩니다.'
            : '유튜브 재생 오류 ' + e.data + ' — 같은 폴더 <b>열기.bat</b> 으로 다시 열어 보세요.';
          box.appendChild(m);
        }
      }
    });
  };
  if(YT_READY) start(); else YT_Q.push(start);
}
document.addEventListener('click', function(e){
  var box = e.target.closest && e.target.closest('.playerbox');
  if(box){ e.stopPropagation(); playBox(box); }
}, true);

const slides=[...document.querySelectorAll('.slide')];
let cur=0;
const bar=document.getElementById('bar'),pageno=document.getElementById('pageno');
function go(n){
  cur=Math.max(0,Math.min(slides.length-1,n));
  slides.forEach((s,i)=>s.classList.toggle('on',i===cur));
  bar.style.width=((cur+1)/slides.length*100)+'%';
  pageno.textContent=(cur+1)+' / '+slides.length;
}
document.getElementById('next').onclick=()=>go(cur+1);
document.getElementById('prev').onclick=()=>go(cur-1);
addEventListener('keydown',e=>{
  if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();go(cur+1);}
  if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();go(cur-1);}
  if(e.key==='Home')go(0); if(e.key==='End')go(slides.length-1);
});
document.getElementById('deck').addEventListener('click',e=>{
  // 링크·플레이어를 누른 건 「다음 장」이 아니다. 예전엔 링크를 눌러도 장이 넘어갔다.
  if(e.target.closest('#navbtns')||e.target.closest('a')||e.target.closest('.playerbox'))return;
  go(cur+1);
});
function fit(){
  const s=Math.min(innerWidth/1280,innerHeight/720)*0.96;
  document.getElementById('deck').style.transform='scale('+s+')';
}
fit();addEventListener('resize',fit);go(0);
function guard(){
  slides.forEach(s=>{
    s.style.zoom='';
    const shown=s.classList.contains('on');
    if(!shown){s.style.visibility='hidden';s.style.display='flex';}
    const need=s.scrollHeight;
    if(need>720){s.style.zoom=String(Math.max(0.78,(720/need)*0.99));}
    if(!shown){s.style.display='';s.style.visibility='';}
  });
}
if(document.fonts&&document.fonts.ready){document.fonts.ready.then(guard);}else{addEventListener('load',guard);}
"""

# 축마다 「무엇을 한 사례인가」와 세션에서 물을 질문이 다르다
AXIS = {
    "분석": dict(cls="ana", one="흩어진 데이터를 모아서 읽었다",
                 q=["우리 팀이 <b>손으로 모으고 있는</b> 데이터는?",
                    "그게 <b>매주 몇 시간</b>인가?",
                    "모아지면 <b>누가</b> 먼저 보나?"]),
    "생성": dict(cls="gen", one="없던 산출물·시스템을 자동으로 만들었다",
                 q=["우리 팀이 <b>매번 새로 만드는</b> 문서는?",
                    "그 문서의 <b>형식이 고정</b>돼 있나?",
                    "초안이 나오면 <b>몇 분</b>이 줄어드나?"]),
}


# ── 썸네일 ──────────────────────────────────────────────────────────────────
THUMBS = os.path.join(C.ROOT, "out", "pool", "thumbs")


def thumb_b64(vid):
    """영상 썸네일을 받아 data URI 로. 한 번 받으면 out/pool/thumbs/ 에 캐시한다.

    ⚠️ 못 받아도 덱은 만들어진다 — 그 자리에 「썸네일 없음」 틀이 들어간다.
       회의실에 인터넷이 없어도 보이게 **파일 안에 박아** 둔다(링크가 아니다).
    """
    if not vid:
        return ""
    os.makedirs(THUMBS, exist_ok=True)
    cache = os.path.join(THUMBS, vid + ".jpg")
    if not os.path.exists(cache):
        import urllib.request
        for name in ("maxresdefault", "hqdefault"):
            try:
                url = "https://i.ytimg.com/vi/%s/%s.jpg" % (vid, name)
                with urllib.request.urlopen(url, timeout=12) as f:
                    b = f.read()
                if len(b) > 3000:            # 404 자리표시자는 아주 작다
                    io.open(cache, "wb").write(b)
                    break
            except Exception:
                continue
    if not os.path.exists(cache):
        return ""
    return "data:image/jpeg;base64," + base64.b64encode(
        io.open(cache, "rb").read()).decode()


# ── 진행과정 단계 ───────────────────────────────────────────────────────────
# 챕터 이름에 이런 게 들어가면 「진행 과정」이 아니라 인사·홍보다 — 도형에서 뺀다.
SKIP = ("인트로", "오프닝", "아웃트로", "엔딩", "마무리 인사", "구독", "협찬", "광고",
        "게스트 소개", "채널 소개", "인사말", "예고")


def steps_from_chapters(raw, n=4):
    """`mm:ss 이름 | ...` 문자열 -> 단계 n개. 시작~끝을 고르게 집어 흐름을 만든다."""
    items = []
    for part in (raw or "").split(" | "):
        part = part.strip()
        if not part or " " not in part:
            continue
        t, name = part.split(" ", 1)
        if any(k in name for k in SKIP):
            continue
        head, _, tail = name.partition("—")
        if not tail:
            head, _, tail = name.partition("-")
        items.append(dict(시각=t.strip(), 이름=cut(head.strip() or name, 26),
                          설명=cut(tail.strip(), 44)))
    if not items:
        return []
    if len(items) <= n:
        return items
    idx = sorted(set(round(k * (len(items) - 1) / (n - 1)) for k in range(n)))
    return [items[k] for k in idx]


AX_FALLBACK = {
    "분석": [dict(시각="", 이름="흩어진 것을 찾는다", 설명="어디에 있는지부터 적는다"),
             dict(시각="", 이름="한 자리에 모은다", 설명="사람이 아니라 도구가 모은다"),
             dict(시각="", 이름="사람이 읽는다", 설명="판단만 남긴다")],
    "생성": [dict(시각="", 이름="형식을 정한다", 설명="매번 같은 틀을 먼저 굳힌다"),
             dict(시각="", 이름="초안을 만든다", 설명="빈 종이에서 시작하지 않는다"),
             dict(시각="", 이름="사람이 고친다", 설명="고치는 시간만 남긴다")],
}

def cut(t, n):
    """말 중간에서 끊기지 않게 자른다 — 잘린 제목이 그대로 발표에 올라가면 티가 난다."""
    t = (t or "").strip()
    if len(t) <= n:
        return t
    head = t[:n]
    if " " in head:
        head = head.rsplit(" ", 1)[0]
    return head.rstrip(" ,·-—") + "…"


def one_line(steps, n=60):
    """단계 이름을 → 로 이어 한 줄로. **낱말 중간이 아니라 화살표에서** 끊는다."""
    out = []
    for st in steps:
        nm = st.get("이름", "").strip()
        if not nm:
            continue
        cand = " → ".join(out + [nm])
        if out and len(cand) > n:
            return " → ".join(out) + " → …"
        out.append(nm)
    return " → ".join(out)


SCRIPT_NAME = "T1_대본.json"


def default_deck(ses, out_d=None):
    """덱 대본 초안 — 제목·한 줄·진행과정 단계. 사람이 T1_대본.json 에서 고친다.

    2026-09-09 부터 **LLM 이 먼저 쓴다.** 유튜브 제목·챕터를 우리 업무 말로 옮긴 원고가
    들어온다. LLM 이 못 돌면 아래 기계 초안(챕터 자르기)으로 그대로 되돌아간다 —
    그때는 제목이 유튜브 원문이라 사람이 반드시 고쳐야 한다.
    """
    llm_deck = (L.write_t1(ses, B.llm_dir(), ses.get("chosen"), ses.get("detail"))
             if L.available() else None)
    src = ("LLM 원고입니다" if llm_deck else "기계 초안입니다")
    out = {"_읽어주세요": f"{src}. 제목·무엇을·단계를 우리 업무 말로 고치고 "
                       "build_t1.py 를 다시 돌리면 고친 내용이 유지됩니다 "
                       "(--reset 하면 초안으로 되돌아갑니다)."}
    for ax in C.AXES:
        r = ses["picks"][ax][0]
        w = (llm_deck or {}).get(ax)
        steps = (w["단계"] if w else None) or steps_from_chapters(r.get("챕터", "")) or AX_FALLBACK[ax]
        out[ax] = {
            "영상ID": r["영상ID"],
            "제목": (w["제목"] if w and w.get("제목") else r["제목"][:52]),
            "무엇을": (w["무엇을"] if w and w.get("무엇을") else one_line(steps)),
            # 로컬영상: out/<날짜>/clips/ 에 둔 파일 이름. 있으면 유튜브 대신 이걸 튼다
            #           (파일은 사람이 넣는다 — 이 도구는 영상을 받지 않는다)
            "로컬영상": "",
            # 재생: [{"시작":"12:12","끝":"28:07","라벨":"...","파일":"(선택) 잘라 둔 mp4"}]
            #       파일을 적으면 그 파일을 통째로 튼다(이미 잘린 것). 안 적으면 풀영상에서
            #       시작~끝만 골라 튼다. 둘 다 없으면 유튜브를 처음부터 튼다.
            # 2026-09-09~ **LLM 이 챕터를 보고 골라 준다.** 근거를 못 대면 빈 배열로 온다.
            "재생": (w.get("재생") or [] if w else []),
            # 도형: "지도"(기본 · 가운데 알약에서 잎이 뻗는다) — `중심` 에 가운데 문구,
            #       단계마다 `묶음`(1/2)으로 색을 나눈다.
            # ⚠️ 2026-09-09 부터 **지도로 고정**이다. "세로"(목록)·"셰브론"(가로 STEP)
            #    렌더러는 남겨 뒀지만 대본에 직접 적었을 때만 나온다 — LLM 은 안 고른다.
            "도형": (w["도형"] if w and w.get("도형") else "지도"),
            "중심": (w.get("중심", "") if w else ""),
            "단계": steps,
        }
    return out


def past_play(vid, out_d):
    """지난 회차 대본에서 **같은 영상의 사람 지정 재생 구간**을 찾아 온다.

    ⚠️ 이게 없으면 회차가 바뀔 때마다 **사람이 손으로 정한 구간이 조용히 사라진다.**
       2026-09-08 에 적어 둔 구간이 09-09 회차로 안 넘어와 LLM 이 새로 채웠고,
       그대로 클립까지 잘렸다 — 파일은 멀쩡하고 에러도 없다.

    최신 회차부터 뒤로 훑어 처음 찾은 것을 쓴다. `출처` 를 「사람」으로 박아 두어
    길이 검문을 건너뛰게 한다 — 검문은 **LLM 환각을 막는 것**이지 사람 판단을 막는 게 아니다.
    """
    root = os.path.join(C.ROOT, "out")
    here = os.path.basename(os.path.normpath(out_d))
    if not os.path.isdir(root):
        return []
    for name in sorted(os.listdir(root), reverse=True):
        if not (len(name) == 8 and name.isdigit()) or name >= here:
            continue
        p = os.path.join(root, name, SCRIPT_NAME)
        if not os.path.exists(p):
            continue
        try:
            d = json.load(io.open(p, encoding="utf-8"))
        except Exception:
            continue
        for ax in C.AXES:
            v = d.get(ax) or {}
            if v.get("영상ID") == vid and (v.get("재생") or []):
                out = []
                for c in v["재생"]:
                    c = dict(c)
                    c.setdefault("출처", "사람")     # 옛 대본엔 출처가 없다 — 사람 것으로 본다
                    out.append(c)
                print(f"  [구간] {name} 회차에서 사람이 지정한 구간 {len(out)}개를 물려받습니다")
                return out
    return []


def load_deck(ses, out_d, reset=False):
    """사람이 고친 대본을 살린다. 단 **사례가 바뀐 축은 초안으로 되돌린다** —
    안 그러면 지난주 사례 설명이 이번 주 영상 옆에 그대로 남는다(에러 없이).

    ⚠️ **재생 구간만은 회차를 넘어 물려받는다** — 같은 영상을 계속 쓰는데 사람이 정한
       구간이 매주 리셋되면 매주 다시 적어야 한다(2026-09-09 실측).
    """
    sp = os.path.join(out_d, SCRIPT_NAME)
    base = default_deck(ses, out_d)

    # 재생 구간 우선순위 — **이번 회차 지정 > 지난 회차 지정 > LLM 제안**.
    # ⚠️ 이 순서가 없으면 `--reset` 할 때마다 **이번 회차에 손으로 고친 구간이
    #    지난 회차 값으로 되돌아간다**(2026-09-09 실측: 10:17~19:24 로 고쳤는데
    #    09-08 의 12:12~28:07 이 다시 올라왔다). 에러는 안 난다.
    cur = {}
    if os.path.exists(sp):
        try:
            cur = json.load(io.open(sp, encoding="utf-8"))
        except Exception:
            cur = {}
    for ax in C.AXES:
        vid = base[ax]["영상ID"]
        mine = (cur.get(ax) or {})
        if mine.get("영상ID") == vid and (mine.get("재생") or []):
            base[ax]["재생"] = mine["재생"]            # 이번 회차에서 고친 것
        else:
            inherited = past_play(vid, out_d)
            if inherited:
                base[ax]["재생"] = inherited          # 지난 회차에서 물려받은 것
    if os.path.exists(sp) and not reset:
        d = json.load(io.open(sp, encoding="utf-8"))
        for ax in C.AXES:
            if d.get(ax, {}).get("영상ID") != base[ax]["영상ID"]:
                d[ax] = base[ax]
        io.open(sp, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, indent=2))
        return d, sp, True
    io.open(sp, "w", encoding="utf-8").write(json.dumps(base, ensure_ascii=False, indent=2))
    return base, sp, False


# ── 조각 ────────────────────────────────────────────────────────────────────
def facts(r):
    return ('<div class="facts">'
            f'<span class="f">조회 <b>{B.human(r["_views"])}</b></span>'
            f'<span class="f">구독 <b>{B.human(r["_subs"])}</b></span>'
            f'<span class="f">길이 <b>{B.dur(r["_sec"])}</b></span>'
            f'<span class="f">{r["업로드"]}</span>'
            f'<span class="f">{B.esc(r["채널"])}</span></div>')


def secs(t):
    """`16:38` / `1:02:03` -> 초. 못 읽으면 None (그 구간은 안 건다)."""
    p = [x for x in str(t or "").strip().split(":") if x.isdigit()]
    if not p:
        return None
    v = 0
    for x in p:
        v = v * 60 + int(x)
    return v


CLIP_DIR = "clips"          # out/<날짜>/clips/ — 덱 옆에 두고 상대경로로 건다


def clip_file(name, out_d):
    """clips/ 안에 그 파일이 실제로 있으면 덱 기준 상대경로를, 없으면 빈 문자열."""
    name = (name or "").strip()
    if not name:
        return ""
    return ("%s/%s" % (CLIP_DIR, name)
            if os.path.exists(os.path.join(out_d, CLIP_DIR, name)) else "")


def local_clip(sc, out_d):
    """대본의 `로컬영상` 이 가리키는 파일이 실제로 있으면 상대경로를 돌려준다.

    ⚠️ 파일은 **덱과 같은 폴더 아래**(out/<날짜>/clips/)에 둔다 — 덱만 따로 옮기면
       영상이 끊긴다. 파일이 없으면 조용히 유튜브 임베드로 떨어진다(에러 아님).
    ⚠️ 영상 파일은 이 도구가 만들지 않는다. 사람이 넣는다.
    """
    return clip_file(sc.get("로컬영상"), out_d)


def player_box(r, img, clips, cls="", local="", out_d=""):
    """썸네일 = 재생 버튼. 클릭하면 이 자리가 플레이어가 되고 지정 구간만 순서대로 돈다.

    ⚠️ 슬라이드 넘김은 덱 아무 데나 클릭이라 여기서 멈춰 세운다(JS 에서 .playerbox 제외).
    """
    # 구간 하나하나가 자기 파일을 가질 수 있다.
    #   파일이 있으면  -> 그 파일을 처음부터 끝까지 (이미 잘려 있으므로 시각은 라벨일 뿐)
    #   파일이 없으면  -> 풀영상(또는 유튜브)에서 시작~끝을 골라 재생
    # ⚠️ 2026-09-09 오후부터 **로컬 클립을 쓰지 않는다**(화질). `파일` 이 적혀 있어도
    #    무시한다 — 옛 대본을 그대로 열었을 때 저화질 mp4 가 조용히 재생되면 안 된다.
    seq, any_file = [], False
    for c in clips or []:
        f = ""
        any_file = any_file or bool(f)
        a, b = secs(c.get("시작")), secs(c.get("끝"))
        if f:
            seq.append({"s": 0, "e": 0, "f": f})
        elif a is not None:
            seq.append({"s": a, "e": b if b is not None else 0, "f": ""})
    # 작은따옴표로 감싸는 속성이라, 값 안의 ' 는 HTML 실체로 바꿔 둔다
    seq_json = json.dumps(seq, ensure_ascii=False).replace("'", "&apos;")
    data = (f' data-vid="{r["영상ID"]}"' + f" data-seq='{seq_json}'")
    local = local or (seq[0]["f"] if (seq and seq[0]["f"]) else "")
    if local:
        # 로컬 파일 재생 — 인터넷도, 유튜브도 필요 없다
        poster = f' poster="{img}"' if img else ""
        inner = (f'<video src="{local}"{poster} preload="metadata" playsinline></video>'
                 '<span class="play"><i>▶</i></span>')
    else:
        inner = (f'<img src="{img}" alt=""><span class="play"><i>▶</i></span>' if img
                 else '썸네일을 받지 못했습니다 — 아래 링크로 유튜브를 엽니다')
    noimg = "" if (img or local) else " noimg"
    # ── 시작점 링크 (2026-09-09 오후) ───────────────────────────────
    # 받아서 자르는 건 그만뒀다 — **화질이 두 번 깎여** 회의실에 걸 수준이 아니었다.
    # 대신 「어디서부터 트는지」를 링크로 잡아 준다. 유튜브가 원본 화질로 틀어 준다.
    # ⚠️ 이 링크는 file:// 에서도 산다 — 임베드만 막히지 새 탭은 안 막힌다.
    start = ""
    if seq and seq[0].get("s"):
        t = int(seq[0]["s"])
        lab = (clips or [{}])[0].get("라벨", "")
        start = (f'<a class="startlink" target="_blank" rel="noopener" '
                 f'href="https://www.youtube.com/watch?v={r["영상ID"]}&t={t}s">'
                 f'▶ {mmss(t)} 부터 유튜브에서 열기'
                 + (f' <span>{esc_(lab)}</span>' if lab else "") + '</a>')
    return (f'<div class="playerbox {cls}{noimg}"{data}>{inner}</div>' + start)


def mmss(sec):
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def esc_(t):
    return B.esc(t)


def thumb_tag(r, img, cls="thumb"):
    """요약 장에서 쓰는 작은 썸네일 — 여기는 예전대로 **새 탭**으로 연다."""
    if not img:
        return (f'<a class="{cls} noimg" href="{r["링크"]}" target="_blank" rel="noopener">'
                '썸네일을 받지 못했습니다 — 클릭하면 유튜브로 갑니다</a>')
    # 2쪽은 이미지만 있으면 된다 — 여기서 재생하지 않으므로 ▶ 배지를 달지 않는다
    return (f'<a class="{cls}" href="{r["링크"]}" target="_blank" rel="noopener">'
            f'<img src="{img}" alt=""></a>')


def clipinfo_html(sc, ax):
    """어떤 구간을 트는지 미리 보여준다 — 누르기 전에 발표자가 알아야 한다."""
    a = AXIS[ax]
    cl = sc.get("재생") or []
    if not cl:
        return ('<div class="clipinfo"><div class="cap">영상</div>'
                '<div class="clip"><div class="n">구간을 지정하지 않아 처음부터 재생됩니다</div>'
                '<div class="hint">T1_대본.json 의 「재생」에 시작·끝을 적으면 그 구간만 돕니다</div>'
                '</div></div>')
    rows = []
    for c in cl:
        rng = f'{c.get("시작", "")} → {c.get("끝", "")}'.strip(" →")
        rows.append(f'<div class="clip"><span class="t {a["cls"]}">{B.esc(rng)}</span>'
                    f'<div class="n">{B.esc(c.get("라벨", ""))}</div></div>')
    tail = ('<div class="hint">두 구간이 <b>이어서</b> 재생됩니다</div>'
            if len(cl) > 1 else "")
    return ('<div class="clipinfo"><div class="cap">이 자리에서 보여줄 구간</div>'
            + "".join(rows) + tail + '</div>')


def steps_html(sc, ax):
    """세로 목록 — 시각 배지 + 이름 + 설명."""
    a = AXIS[ax]
    vs = []
    for k, st in enumerate(sc.get("단계") or AX_FALLBACK[ax], 1):
        t = st.get("시각") or st.get("번호") or ("%d단계" % k)
        desc = f'<p>{B.esc(st.get("설명", ""))}</p>' if st.get("설명") else ""
        vs.append(f'<div class="vstep"><span class="t {a["cls"]}">{B.esc(t)}</span>'
                  f'<h3>{B.esc(st.get("이름", ""))}</h3>{desc}</div>')
    return "".join(vs)


def chev_html(sc):
    """가로 셰브론 — 단계가 5~6개로 많고 「흐름」 자체가 메시지일 때 쓴다."""
    cols = []
    for k, st in enumerate(sc.get("단계") or [], 1):
        cols.append('<div class="chevcol">'
                    f'<div class="chevbox"><div class="chevno">{B.esc(st.get("번호") or "STEP %d" % k)}</div>'
                    f'<div class="chevname">{B.esc(st.get("이름", ""))}</div></div>'
                    f'<div class="chevdesc">{B.esc(st.get("설명", ""))}</div></div>')
    bands = []
    for bd in sc.get("구간") or []:
        on = " on" if bd.get("강조") else ""
        rng = bd.get("범위", "")
        nm = bd.get("이름", "")
        head = f'{rng} · {nm}' if rng and nm else (rng or nm)
        bands.append(f'<div class="band{on}"><div class="t">{B.esc(head)}</div>'
                     f'<div class="d">{B.esc(bd.get("설명", ""))}</div></div>')
    return ('<div class="chev">' + "".join(cols) + '</div>'
            + ('<div class="bands">' + "".join(bands) + '</div>' if bands else ''))


MAP_W, MAP_H = 568, 414          # 오른쪽 지도 칸 (1280x720 무대라 좌표를 박아 둔다)
LEAF_X, LEAF_H = 230, 57
CENTER_W = 176


def map_html(sc, ax):
    """가운데 알약 하나에서 잎으로 점선이 뻗는 지도.

    ⚠️ 잎이 많아지면 세로로만 늘어난다 — 7개를 넘기면 칸을 벗어난다.
       그때는 단계를 줄이거나 도형을 「셰브론」/「세로」로 바꾼다.
    """
    a = AXIS[ax]
    leaves = sc.get("단계") or []
    n = max(1, len(leaves))
    step = min(72, (MAP_H - LEAF_H) / (n - 1)) if n > 1 else 0
    top0 = (MAP_H - (LEAF_H + step * (n - 1))) / 2
    cy = MAP_H / 2

    lines, nodes = [], []
    for i, st in enumerate(leaves):
        y = top0 + step * i
        lines.append(f'<line x1="{CENTER_W}" y1="{cy:.0f}" x2="{LEAF_X}" y2="{y + LEAF_H / 2:.0f}" '
                     'stroke="#C7CDC4" stroke-width="1.6" stroke-dasharray="5 5"/>')
        g = st.get("묶음")
        cls = f" g{g}" if g in (1, 2) else ""
        no = (f'<span class="no">{B.esc(st.get("번호", ""))}</span>' if st.get("번호") else "")
        desc = (f'<i>{B.esc(st.get("설명", ""))}</i>' if st.get("설명") else "")
        nodes.append(f'<div class="leaf{cls}" style="top:{y:.0f}px">{no}'
                     f'<b>{B.esc(st.get("이름", ""))}</b>{desc}</div>')

    legend = ""
    if sc.get("구간"):
        items = []
        for k, bd in enumerate(sc["구간"], 1):
            items.append(f'<span class="lg g{k}"><b>{B.esc(bd.get("범위", ""))}</b>'
                         f'{B.esc(bd.get("이름", ""))}</span>')
        legend = f'<div class="maplegend">{"".join(items)}</div>'

    center = B.esc(sc.get("중심") or a["one"])
    return (f'<div class="mapwrap">'
            f'<svg viewBox="0 0 {MAP_W} {MAP_H}">{"".join(lines)}</svg>'
            f'<div class="mapcenter" style="top:50%;transform:translateY(-50%)">{center}</div>'
            + "".join(nodes) + legend + '</div>')


def case_slide(r, sc, ax, no, img, local="", out_d=""):
    """사례 한 장. 도형이 「셰브론」이면 위 플레이어 / 아래 가로 흐름, 아니면 좌우 두 칸."""
    a = AXIS[ax]
    head = ('<section class="slide case grid-bg">'
            f'<div class="eyebrow"><span class="num {a["cls"]}">{no} {ax}</span>{a["one"]}</div>'
            f'<h2>{B.esc(cut(sc.get("제목") or r["제목"], 40))}</h2>'
            f'<div class="lead">{B.esc(sc.get("무엇을", ""))}</div>')
    box = player_box(r, img, sc.get("재생"), local=local, out_d=out_d)

    if sc.get("도형") == "지도":
        # 구간 안내 패널은 뺀다 — 무엇을 트는지는 플레이어 밑 한 줄로 충분하다
        return (head.replace('class="slide case grid-bg"', 'class="slide case wide grid-bg"')
                + '<div class="mapline"><div class="thumbwrap">' + box + '</div>'
                + map_html(sc, ax) + '</div></section>')

    if sc.get("도형") == "셰브론":
        return (head.replace('class="slide case grid-bg"', 'class="slide case wide grid-bg"')
                + '<div class="topline"><div class="thumbwrap">' + box + '</div>'
                + clipinfo_html(sc, ax) + '</div>'
                + '<div class="flowarea"><div class="cap">진행 과정</div>'
                + chev_html(sc) + '</div></section>')

    return (head
            + '<div class="casebody"><div class="thumbwrap">' + box + facts(r) + '</div>'
            + '<div class="vflow"><div class="cap">진행 과정</div>'
            + steps_html(sc, ax) + '</div></div></section>')



def summary_half(r, sc, ax, no, img):
    a = AXIS[ax]
    return (f'<div class="col {a["cls"]}">'
            f'<h3>{no} {ax} — {a["one"]}</h3>'
            + thumb_tag(r, img, "thumbmini") +
            f'<div class="what">{B.esc(sc.get("무엇을", ""))}</div>'
            f'<div class="who">{B.esc((sc.get("제목") or r["제목"])[:40])}<br>'
            f'{B.esc(r["채널"])} · {B.dur(r["_sec"])}</div></div>')


LAUNCHER = """@echo off
REM ============================================================
REM  Open the T1 deck through a local web server.
REM  ASCII ONLY - see README section 10 (cmd drifts on multi-byte lines).
REM
REM  Why not just double-click the .html?
REM    Opening it as a file:// page makes YouTube refuse the embed and the
REM    player shows only "error 153". The very same deck plays fine from
REM    http://127.0.0.1. Measured 2026-09-08.
REM ============================================================
setlocal
cd /d "%~dp0"
set "OLDCP="
for /f "tokens=2 delims=:" %%c in ('chcp') do for /f "tokens=1" %%d in ("%%c") do set "OLDCP=%%d"
if not "%OLDCP%"=="65001" chcp 65001 > nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
python "%~dp0..\\..\\tools\\serve_deck.py" DAY
if defined OLDCP if not "%OLDCP%"=="65001" chcp %OLDCP% > nul
endlocal
"""


def write_launcher(out_d, day):
    """회차 폴더에 열기.bat 을 둔다 — 덱과 같이 옮겨 다녀야 하므로 여기에 만든다."""
    txt = LAUNCHER.replace("DAY", day).replace("\n", "\r\n")
    io.open(os.path.join(out_d, "열기.bat"), "w",
            encoding="ascii", newline="").write(txt)


# ── 2쪽 「현황 지도」 ────────────────────────────────────────────────────────
# 이 장은 **회차마다 바뀌지 않는다** — T1_대본.json 이 아니라 여기 상수다.
# 매주 바뀌는 건 사례 두 장뿐이고, 2쪽은 「남들은 어디까지 왔나」 고정 배경이다.
#
# ⚠️ 좌표를 1124x336 무대에 **박아** 뒀다. 잎을 늘리거나 문구를 길게 쓰면
#    라벨이 **에러 없이 겹친다**. 고쳤으면 반드시 눈으로 확인할 것.
#    라벨은 전부 노드 위/아래 가운데 정렬이라, 세로로 붙은 두 노드가 제일 위험하다.
NET_W, NET_H = 1124, 336

# 잎 = (분류, 문구, x, y, 반지름, 라벨위치)  ← **절대좌표**다.
# 처음엔 「허브 + 각도 + 거리」로 뽑았는데, 각도를 조금만 건드려도 옆 잎의 라벨과
# 겹쳤다(에러 없이 글자만 포개진다). 좌표를 직접 박아 두면 눈으로 잡은 간격이 유지된다.
# 규칙 두 개 — ①라벨끼리 세로로 25px 이상 벌린다 ②라벨이 허브 원을 지나가지 않게 한다.
NET_HUBS = [
    {"이름": "모아 온다", "부제": "흩어진 자료를 대신 긁어 온다", "색": "#2F6FB0",
     "x": 175, "y": 218, "r": 46, "라벨": "아래",
     "잎": [("수집", "게시판·사이트 훑기", 100, 158, 15, "위"),
            ("정리", "매번 같은 열의 표", 215, 98, 14, "위"),
            ("조회", "시트·DB에 묻기", 320, 168, 13, "아래")]},
    {"이름": "만들어 낸다", "부제": "없던 산출물을 자동으로", "색": "#7A4E96",
     "x": 470, "y": 120, "r": 50, "라벨": "위",
     "잎": [("문서", "보고서·회의록 초안", 390, 215, 15, "아래"),
            ("자료", "발표자료·카드", 530, 242, 14, "아래"),
            ("코드", "반복 작업 스크립트", 600, 178, 13, "아래")]},
    {"이름": "알아서 돈다", "부제": "사람이 안 눌러도 실행된다", "색": "#00A05A",
     "x": 740, "y": 225, "r": 42, "라벨": "아래",
     "잎": [("배치", "정해진 시각에 실행", 640, 148, 14, "위"),
            ("발송", "메일·메신저 발송", 760, 115, 13, "위"),
            ("감시", "실패하면 알림", 880, 270, 12, "위")]},
    {"이름": "물어보면 답한다", "부제": "사내 지식·1차 응대", "색": "#F0562F",
     "x": 985, "y": 115, "r": 34, "라벨": "위",
     "잎": [("검색", "규정·매뉴얼 찾기", 1035, 205, 13, "아래"),
            ("응대", "1차 문의 회신", 905, 195, 13, "위")]},
]

# 허브끼리 잇는 점선 — 네 덩어리가 따로 노는 게 아니라 한 흐름임을 보이는 선.
# ⚠️ 사슬(0-1-2-3)만 잇는다. 전부 이으면 긴 대각선이 잎 라벨을 가로질러 지저분해진다.
NET_TIES = [(0, 1), (1, 2), (2, 3)]

NET_STATS = [
    ("88%", "조직이 한 곳 이상 AI 를 쓴다 — 그런데 전사로 넓힌 곳은 <b>약 1/3</b>"),
    ("62%", "AI 에이전트를 시험 중 · 한 업무라도 <b>정착시킨 곳은 23%</b>"),
    ("25%", "그런데도 근무시간의 이만큼은 <b>여전히 손으로 하는 반복 작업</b>"),
    ("53 : 24", "국내 도입률 <b>서비스업 53% vs 제조업 23.8%</b> — 업종이 아니라 업무가 가른다"),
]

NET_SRC = ("출처 — 2026 공개 조사 종합(McKinsey State of AI · SHRM Navigating AI in the Workplace 2026 · "
           "국내 업종별 AI 에이전트 도입 현황 2026). 링크는 README 「§2쪽 현황 지도」.")


def netmap_html():
    """관계 그림 한 장 — 가운데 덩어리 4개에서 실제 쓰임새가 잎으로 뻗는다."""
    lines, circles, labels = [], [], []

    pts = [(h["x"], h["y"]) for h in NET_HUBS]
    for i, j in NET_TIES:
        lines.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="#C7CDC4" '
                     'stroke-width="1.4" stroke-dasharray="6 6"/>'
                     % (pts[i][0], pts[i][1], pts[j][0], pts[j][1]))

    for h in NET_HUBS:
        col = h["색"]
        for cat, txt, lx, ly, r, pos in h["잎"]:
            lines.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" '
                         'stroke-width="1.5" opacity=".42"/>' % (h["x"], h["y"], lx, ly, col))
            circles.append('<circle cx="%d" cy="%d" r="%d" fill="%s" opacity=".82"/>'
                           % (lx, ly, r, col))
            ty = ly - r - 9 if pos == "위" else ly + r + 17
            labels.append('<text x="%d" y="%d" text-anchor="middle" font-size="12.5">'
                          '<tspan class="lcat" fill="%s">[%s]</tspan> '
                          '<tspan class="ltxt">%s</tspan></text>'
                          % (lx, ty, col, B.esc(cat), B.esc(txt)))

        circles.append('<circle cx="%d" cy="%d" r="%d" fill="%s"/>'
                       % (h["x"], h["y"], h["r"], col))
        ty = h["y"] - h["r"] - 26 if h["라벨"] == "위" else h["y"] + h["r"] + 25
        labels.append('<text x="%d" y="%d" text-anchor="middle" class="hubname" fill="%s">%s</text>'
                      '<text x="%d" y="%d" text-anchor="middle" class="hubsub">%s</text>'
                      % (h["x"], ty, col, B.esc(h["이름"]), h["x"], ty + 18, B.esc(h["부제"])))

    return ('<div class="netwrap"><svg class="net" viewBox="0 0 %d %d">%s</svg></div>'
            % (NET_W, NET_H, "".join(lines) + "".join(circles) + "".join(labels)))


def landscape_slide():
    """2쪽 — 남들은 무엇을 자동화했나. 우리 두 사례를 놓기 전에 지도를 먼저 편다."""
    chips = "".join('<div class="stat"><b>%s</b><span>%s</span></div>' % (n, t)
                    for n, t in NET_STATS)
    return ('<section class="slide dense grid-bg">'
            '<div class="eyebrow">지금 · 업무 자동화 현황</div>'
            '<h2>도입은 이미 지났다 — 갈리는 건 <span class="hl">무엇을</span> 자동화했나</h2>'
            '<div class="lead">쓰는 자리는 네 덩어리로 모입니다. '
            '오늘 볼 두 사례는 이 중 <b>왼쪽 두 덩어리</b>입니다.</div>'
            + netmap_html()
            + '<div class="stats">' + chips + '</div>'
            + '<div class="srcline">' + B.esc(NET_SRC) + '</div>'
            + '</section>')


# ── 마지막 쪽 「AX 확산 전략」 ───────────────────────────────────────────────
# 정본은 AX_source/docs/AX확산/00_AX확산_계획.md (v4.2) — 여기는 요약 사본이다.
# ⚠️ 계획서를 고치면 이 표도 같이 고쳐야 한다. 안 그러면 부서장이 옛 주기를 듣는다.
TACTICS = [
    ("T1", "부서장회의 세션", "사례 공유 13분 + 질의응답 10분 — <b>오늘 이 자리</b>",
     "부서장의 <b>허가와 시간</b> — 알게 해서 클리닉으로 보낸다", "매주 월 30분", True),
    ("T2", "AX 정보채널", "게시판에 카드로 게시 — <b>전부 T1 재활용</b>",
     "무관심한 다수에게 <b>상시 노출</b> — 「우리도 해볼까」의 씨앗", "주 1회", False),
    ("T3", "자동화 선물하기", "팀에 필요한 자동화를 <b>스케줄러까지</b> 만들어 넘긴다",
     "한 팀을 <b>완전한 지지자</b>로 — 다음 사례가 여기서 나온다", "격주 1건", False),
    ("T4", "AI 자동화 동아리", "자기 업무를 붙잡고 실습 30분 + 막힌 곳 공유 30분",
     "<b>챔피언 양성</b> — DX 없이도 팀 안에서 도는 사람", "월 1회", False),
    ("T5", "AX 표준 자동화 코드", "분기 사례를 <b>남의 팀에서도 도는 코드</b>로 패키징",
     "다음 분기 팀의 출발선이 <b>「빈손」이 아니게</b> 된다", "분기 1건", False),
    ("T6", "AX 클리닉", "예약 없이 「이거 되나요?」 — 옆에 앉아 같이 만든다",
     "<b>문턱 제거 + 유스케이스 수집</b> — 진짜 수요가 여기서 나온다", "주 1회 30분", False),
    ("T7", "찾아가는 AX 진단", "팀을 방문해 반복업무를 훑고 <b>자동화 후보 3건</b>",
     "선물 대상과 유입을 <b>찾아 나선다</b> — 대기열의 공급원", "월 1회 60분", False),
]


ROT_CSS = """
/* 로테이션 장 — 네 칸을 가로로 두고 이번 주만 살린다 */
.rot{display:flex;gap:20px;flex:1;min-height:0;align-items:stretch}
.rot .wk{flex:1;background:#fff;border:2.5px solid var(--line);border-radius:20px;
  padding:22px 20px;display:flex;flex-direction:column;position:relative}
.rot .wk.on{border-color:var(--green);border-width:4px;background:#F2FAF5;
  box-shadow:0 10px 26px rgba(0,160,90,.16)}
.rot .wk.lock{background:#F6F5F1}
.rot .no{font-size:17px;font-weight:700;color:var(--ink-soft);letter-spacing:.08em;margin-bottom:10px}
.rot .wk.on .no{color:var(--green-deep)}
.rot h3{font-size:23px;font-weight:700;line-height:1.34;margin-bottom:10px}
.rot p{font-size:17px;line-height:1.5;color:var(--ink-soft)}
.rot .src{margin-top:auto;padding-top:14px;font-size:16px;font-weight:700;color:var(--ink-soft)}
.rot .wk.on .src{color:var(--green-deep)}
.rot .here{position:absolute;top:-15px;left:50%;transform:translateX(-50%);
  background:var(--green);color:#fff;font-size:15px;font-weight:700;
  border-radius:999px;padding:6px 16px 4px;white-space:nowrap}
"""

# 네 칸 = (주차, 이름, 한 줄, 소재, 사내 전용인가)
# ⚠️ **`build_page.SLOTS` 와 같은 내용을 두 곳에 두지 않는다** — 이름·유튜브 여부는
#    거기서 읽어 온다. 여기 있는 건 덱에서만 쓰는 **한 줄 설명**뿐이다.
ROT_LINE = {
    1: ("사례를 보고 「우리 팀 걸로 하면?」을 그 자리서 판정한다", "분석 1 + 생성 1"),
    2: ("각자 하나씩 고르고 T5 레시피로 등록한다", "분석 1 + 생성 1"),
    3: ("같은 형식 + 툰에서 「이건 이렇게 깨진다」까지", "분석 1 + 생성 1"),
    4: ("그 팀 사람이 직접 10분 발표하고 Q&A", "🔒 사내 — 우리 팀 사례"),
}


def rotation_slide(ses):
    """맨 뒤 전략 장 **앞** — 네 주차를 놓고 오늘이 어디인지 표시한다 (2026-09-09 신설).

    ⚠️ 부서장은 매주 오지 않는다. 오늘 것만 보여주면 **「가끔 하는 행사」**로 읽힌다.
       네 칸을 한 번에 보여주고 이번 칸을 켜야 「매주 도는 것」이 된다.
    """
    now = ses["slot"]
    cells = []
    for k in (1, 2, 3, 4):
        nm, yt, _ = B.SLOTS[k]
        line, src = ROT_LINE[k]
        cls = " on" if k == now else ("" if yt else " lock")
        here = '<div class="here">오늘 여기</div>' if k == now else ""
        cells.append(f'<div class="wk{cls}">{here}'
                     f'<div class="no">{k}주차</div><h3>{B.esc(nm)}</h3>'
                     f'<p>{B.esc(line)}</p><div class="src">{src}</div></div>')
    return ('<section class="slide grid-bg">'
            '<div class="eyebrow">이 자리는 매주 돕니다</div>'
            f'<h2>4주에 한 바퀴 — 오늘은 <span class="hl">{now}주차</span>입니다</h2>'
            '<div class="spacer" style="max-height:18px"></div>'
            '<div class="rot">' + "".join(cells) + '</div>'
            '<div class="note">세 주는 <b>바깥 사례</b>를 보고 우리 걸로 바꿔 보고, '
            '네 번째 주는 <b>우리 팀이 직접</b> 발표합니다. '
            '보는 자리와 하는 자리가 번갈아 와야 확산이 굴러갑니다.</div>'
            '</section>')


def strategy_slide():
    """맨 뒤 — 오늘 이 13분이 전체 어디에 붙어 있는지. AX확산 계획(docs/AX확산) v4.2 요약.

    ⚠️ 「하는 일」과 「얻는 것」을 **한 줄에 나란히** 둔다. 계획서의 두 표(전술표 ·
       「각각이 노리는 것」)를 합친 것이다 — 부서장은 무엇을 하느냐보다
       **그래서 뭐가 남느냐**를 먼저 묻는다.
    """
    rows = []
    for no, name, desc, gain, cyc, now in TACTICS:
        rows.append('<div class="trow%s"><div class="tno">%s</div>'
                    '<div class="tbody"><div class="tname">%s</div>'
                    '<div class="tdesc">%s</div></div>'
                    '<div class="tgain"><span class="gl">얻는 것</span>%s</div>'
                    '<div class="tcyc">%s</div></div>'
                    % (" now" if now else "", no, B.esc(name), desc, gain, B.esc(cyc)))
    return ('<section class="slide dense grid-bg">'
            '<div class="eyebrow">AX 확산 전략 · v4.2</div>'
            '<h2>큰 프로그램을 세우지 않습니다 — <span class="hl">침투 경로 7갈래</span>를 동시에 엽니다</h2>'
            '<div class="lead">노리는 사람이 서로 다른 경로를 열어두고 <b>물려 돌아가게</b> 만듭니다 — '
            '하나가 막혀도 나머지가 돕니다.</div>'
            '<div class="tlist">' + "".join(rows) + '</div>'
            '</section>')


def build(ses, d, out, deck, out_d):
    ana = ses["picks"]["분석"][0]
    gen = ses["picks"]["생성"][0]
    img = {ax: thumb_b64(ses["picks"][ax][0]["영상ID"]) for ax in C.AXES}
    loc = {ax: local_clip(deck[ax], out_d) for ax in C.AXES}
    H = ['<!doctype html>', '<html lang="ko"><head><meta charset="utf-8">',
         '<meta name="viewport" content="width=device-width,initial-scale=1">',
         # 구간 재생용. 인터넷이 없으면 조용히 안 올라오고 링크로 떨어진다
         '<script src="https://www.youtube.com/iframe_api"></script>',
         f'<title>T1 부서장회의 · {ses["label"]} 이달의 사례</title>',
         '<style>', ROT_CSS, font_face("GmarketSansMedium.woff", 500),
         font_face("GmarketSansBold.woff", 700), CSS, '</style></head><body>',
         '<div id="stage"><div id="deck">']

    # 1 표지
    H.append(
        '<section class="slide cover grid-bg on">'
        f'<div class="brandline">AX 확산 · T1 부서장회의 &nbsp;|&nbsp; '
        f'{ses["label"]} · {ses["slot_name"]}</div>'
        '<h1>데이터를 <span class="hl">모아 오고</span>,<br>'
        '그걸로 <span class="hl">만들어 냅니다</span>.</h1>'
        '<div class="sub">이번 주 한 쌍 — <b>분석 1건 + 생성 1건</b>.<br>'
        '남이 만든 걸 구경하는 시간이 아니라, <b>우리 팀 걸로 바꿔 보는 13분</b>입니다.</div>'
        f'<div class="date">{d:%Y. %m. %d}</div>'
        '</section>')

    # 2 현황 지도 — 남들은 무엇을 자동화했나 (고정 장)
    H.append(landscape_slide())

    # 3 두 사례 요약 — 무엇을 모아 왔고 무엇을 만들어 냈나
    H.append(
        '<section class="slide grid-bg">'
        '<div class="eyebrow">이번 주 두 사례</div>'
        '<h2>무엇을 <span class="hl">모아 왔고</span>, 무엇을 <span class="hl">만들어 냈나</span></h2>'
        '<div class="spacer"></div>'
        '<div class="duo">'
        + summary_half(ana, deck["분석"], "분석", "①", img["분석"])
        + summary_half(gen, deck["생성"], "생성", "②", img["생성"]) +
        '</div>'
        '</section>')

    # 4·5 사례 두 장
    H.append(case_slide(ana, deck["분석"], "분석", "①", img["분석"], loc["분석"], out_d))
    H.append(case_slide(gen, deck["생성"], "생성", "②", img["생성"], loc["생성"], out_d))

    # 6 로테이션 — 이 자리가 매주 돈다는 것 (고정 장, 전략 장 앞)
    H.append(rotation_slide(ses))

    # 7 전략 — 오늘 이 자리가 어디에 붙어 있는지 (고정 장, 맨 뒤)
    H.append(strategy_slide())

    H.append('<div id="bar"></div>'
             '<div id="hud"><div id="pageno">1 / 1</div>'
             '<div id="navbtns"><button id="prev" aria-label="이전">←</button>'
             '<button id="next" aria-label="다음">→</button></div></div>'
             '</div></div>')
    H.append(f"<script>{JS}</script></body></html>")
    io.open(out, "w", encoding="utf-8").write("\n".join(H))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", type=int, default=None)
    ap.add_argument("--week", type=int, default=None)
    ap.add_argument("--reset", action="store_true",
                    help="사람이 고친 T1_대본.json 을 버리고 초안으로")
    ap.add_argument("--open", action="store_true")
    ap.add_argument("--no-llm", action="store_true", help="LLM 없이 챕터 자르기 초안으로")
    ap.add_argument("--llm-refresh", action="store_true", help="LLM 캐시를 버리고 다시 쓴다")
    a = ap.parse_args()
    L.enable(not a.no_llm, a.llm_refresh)

    d = date.today()
    ses = B.session(a.month, a.week)

    if not ses["from_youtube"]:
        print(f"  {ses['slot']}주차 「{ses['slot_name']}」 는 사내 전용 회차 — T1 덱을 만들지 않습니다.")
        print("  유튜브가 채우는 건 1·2주차뿐입니다. 소재는 T6 클리닉·제작 중 실패에서 가져옵니다.")
        return

    miss = [ax for ax in C.AXES if not ses["picks"][ax]]
    if miss:
        print(f"  [건너뜀] {' · '.join(miss)}축 후보가 비어 T1 덱을 만들 수 없습니다.")
        print("  `python tools/collect.py` 로 재고를 먼저 채우세요.")
        return

    out_d = B.out_dir(d)
    deck, sp, reused = load_deck(ses, out_d, a.reset)
    print(("  대본 재사용 " if reused else "  대본 생성 ") + sp
          + ("  (초안으로 되돌리려면 --reset)" if reused else ""))
    out = B.t1_path(d)
    build(ses, d, out, deck, out_d)
    write_launcher(out_d, f"{B.round_day(d):%Y%m%d}")
    print(f"생성 {out}")
    print(f"  {ses['label']} · 분석 「{ses['picks']['분석'][0]['제목'][:32]}」")
    print(f"  {' ' * 14}생성 「{ses['picks']['생성'][0]['제목'][:32]}」")
    spots = [(ax, c) for ax in C.AXES for c in (deck.get(ax, {}).get("재생") or [])]
    if spots:
        print("  ▶ 시작점 링크가 사례 장마다 붙어 있습니다 — 눌러서 유튜브를 그 지점부터 엽니다.")
        for ax, c in spots:
            print(f"     {ax} {c.get('시작')} ~ {c.get('끝')}  {c.get('라벨','')}")
        print("     덱 안에서 바로 재생하려면 같은 폴더 **열기.bat** (file:// 은 임베드가 막힙니다).")
    else:
        print("  ▶ 재생 구간이 없습니다 — 영상이 처음부터 재생됩니다.")
    # 어느 손에서 나온 초안인지 대본이 알고 있다 — 안내를 고정 문구로 두면 거짓말이 된다
    by_llm = str(deck.get("_읽어주세요", "")).startswith("LLM")
    print("  ⚠️ " + ("LLM 원고입니다 — 영상 제목·챕터만 보고 쓴 것이라 우리 팀 사정은 모릅니다."
                    if by_llm else
                    "기계 초안입니다 — 제목·무엇을·단계가 유튜브 원문 그대로입니다."))
    print(f"     발표 전에 {SCRIPT_NAME} 을 읽고 고치는 것까지가 한 세트입니다.")
    if a.open:
        webbrowser.open("file:///" + out.replace("\\", "/"))


if __name__ == "__main__":
    main()
