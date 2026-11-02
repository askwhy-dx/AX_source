# -*- coding: utf-8 -*-
"""문서 판 — 기획서 두 종이 같이 쓰는 A4 스타일과 HTML→PDF 렌더러. (2026-09-09 신설)

  tools/build_brief.py       회차 기획서 (매주 바뀐다)
  tools/build_design_doc.py  시스템 기획서 (구조가 바뀔 때만)

왜 여기 모아 뒀나 — 둘이 같은 회사 문서로 보여야 하는데, CSS 를 각자 들고 있으면
한쪽만 고쳐져 **두 문서의 판이 조용히 갈린다.** 폰트 내장도 한 곳에서 한다.

⚠️ PDF 는 playwright chromium 의 `page.pdf()` 로 뽑는다 (T2 스크린샷과 같은 브라우저).
   `print_background=True` 를 빼면 **배경색·표 머리·강조 박스가 전부 흰색으로 인쇄된다** —
   화면에선 멀쩡하고 PDF 만 밋밋해진다.
"""
import base64, io, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import collect as C

FONTS = os.path.join(C.ROOT, "assets", "fonts")


def font_face(fname, weight):
    p = os.path.join(FONTS, fname)
    if not os.path.exists(p):
        return ""      # 폰트가 없으면 시스템 고딕으로 떨어진다 — 문서는 그대로 나온다
    b64 = base64.b64encode(io.open(p, "rb").read()).decode()
    return ("@font-face{font-family:'GmarketSans';font-weight:%d;font-style:normal;"
            "src:url(data:font/woff;base64,%s) format('woff');font-display:block;}"
            % (weight, b64))


# A4 210×297mm. 여백은 CSS @page 가 아니라 pdf(margin=) 으로 준다 — 둘 다 주면 겹친다.
CSS = """
:root{
  --ink:#1E2B33; --dim:#5D6B72; --line:#DDE2DC; --paper:#fff;
  --green:#00A05A; --green-deep:#00794A; --hl:#FFE24D;
  --ana:#2F6FB0; --gen:#7A4E96; --warn:#B8442E; --soft:#F5F7F3;
}
*{margin:0;padding:0;box-sizing:border-box}
body{background:var(--paper);color:var(--ink);
  font-family:'GmarketSans','Malgun Gothic','Apple SD Gothic Neo',sans-serif;
  font-weight:500;font-size:10.5pt;line-height:1.62;word-break:keep-all;
  overflow-wrap:break-word;-webkit-print-color-adjust:exact;print-color-adjust:exact}
b,strong{font-weight:700}
a{color:var(--ana);text-decoration:none;word-break:break-all}

/* 표지 — 첫 장을 통째로 쓴다 */
.cover{height:247mm;display:flex;flex-direction:column;justify-content:center;
  page-break-after:always;break-after:page}
.cover .brand{font-size:11pt;font-weight:700;color:var(--green-deep);
  letter-spacing:.14em;margin-bottom:10mm}
.cover h1{font-size:30pt;line-height:1.34;font-weight:700;letter-spacing:-.01em}
.cover .lead{margin-top:8mm;font-size:12pt;line-height:1.7;color:var(--dim)}
.cover .meta{margin-top:14mm;padding-top:6mm;border-top:2px solid var(--line);
  font-size:9.5pt;color:var(--dim);line-height:1.9}

h2{font-size:16pt;font-weight:700;line-height:1.34;margin:9mm 0 3.5mm;
  padding-bottom:2.2mm;border-bottom:2.5px solid var(--ink);letter-spacing:-.01em;
  page-break-after:avoid;break-after:avoid}
h2:first-of-type{margin-top:0}
h3{font-size:12pt;font-weight:700;margin:6mm 0 2.5mm;color:var(--green-deep);
  page-break-after:avoid;break-after:avoid}
h4{font-size:10.5pt;font-weight:700;margin:4mm 0 1.6mm;
  page-break-after:avoid;break-after:avoid}
p{margin:0 0 2.6mm}
ul,ol{margin:0 0 3mm 5.5mm}
li{margin-bottom:1.4mm}
.dim{color:var(--dim)}
.small{font-size:9pt;line-height:1.6}
.hl{background:linear-gradient(transparent 54%,var(--hl) 54%,var(--hl) 93%,transparent 93%);
  padding:0 2px}

/* 표 — 머리줄이 페이지를 넘어가도 반복된다 */
table{width:100%;border-collapse:collapse;margin:0 0 4mm;font-size:9.5pt;line-height:1.5}
thead{display:table-header-group}
th,td{border:1px solid var(--line);padding:2.2mm 2.6mm;vertical-align:top;text-align:left}
th{background:var(--soft);font-weight:700;white-space:nowrap}
td.n{white-space:nowrap;text-align:right}
tr{page-break-inside:avoid;break-inside:avoid}

/* 강조 상자 */
.box{border:2px solid var(--line);border-radius:3mm;padding:4mm 5mm;margin:0 0 4mm;
  background:var(--soft);page-break-inside:avoid;break-inside:avoid}
.box.warn{border-color:var(--warn);background:#FDF3F0}
.box.plan{border-color:var(--green);background:#F1F8F3}
.box h4{margin-top:0;color:var(--ink)}
.box.warn h4{color:var(--warn)}
.box.plan h4{color:var(--green-deep)}
.box p:last-child,.box ul:last-child{margin-bottom:0}
.quote{font-size:12.5pt;line-height:1.62;font-weight:700}

/* 두 축 카드 */
.duo{display:flex;gap:5mm;margin-bottom:4mm}
.duo .col{flex:1;border:2px solid var(--line);border-radius:3mm;padding:4mm 4.5mm;
  page-break-inside:avoid;break-inside:avoid}
.duo .col.ana{border-color:var(--ana)} .duo .col.gen{border-color:var(--gen)}
.tag{display:inline-block;font-size:8.5pt;font-weight:700;color:#fff;border-radius:99px;
  padding:1.1mm 3.2mm;margin-bottom:2.4mm}
.tag.ana{background:var(--ana)} .tag.gen{background:var(--gen)}
.col h4{font-size:11pt;margin:0 0 2mm}
.col .src{font-size:8.5pt;color:var(--dim);margin-bottom:2.5mm;line-height:1.5}
/* 보는 시간대 — 링크 위. 발표자가 제일 먼저 찾는 값이라 눈에 띄게 둔다 */
.watch{border-left:3px solid var(--green);background:#F1F8F3;border-radius:0 2mm 2mm 0;
  padding:2.2mm 3mm;margin:0 0 2.5mm;font-size:9pt;line-height:1.6;color:var(--ink)}
.watch a{color:var(--green-deep);text-decoration:none}
.watch b{font-size:10pt}
.watch span{color:var(--dim);font-weight:500}
.watch.none{border-left-color:var(--warn);background:#FDF3F0;color:var(--warn)}

/* 흐름도 — 파이프라인 한 칸 */
.flow{border-left:3px solid var(--green);padding:0 0 0 4.5mm;margin:0 0 4mm}
.flow .st{margin-bottom:3mm;page-break-inside:avoid;break-inside:avoid}
.flow .st:last-child{margin-bottom:0}
.flow .no{font-size:8.5pt;font-weight:700;color:var(--green-deep);letter-spacing:.08em}
/* ⚠️ 단계 제목만 한 줄로 세운다. 예전엔 `b` 를 잡아서 **설명 안의 강조까지 줄바꿈돼**
   문장이 토막 났다 — 「게재 통과 / 전량 / 을 읽고」처럼. 클래스로 좁힌다. */
.flow .st .t{display:block;font-size:10.5pt;font-weight:700}
.flow .st .d{font-size:9pt;color:var(--dim);line-height:1.55}
code,.mono{font-family:'Consolas','D2Coding',monospace;font-size:9pt;
  background:var(--soft);padding:.4mm 1.2mm;border-radius:1mm}
pre{background:var(--soft);border:1px solid var(--line);border-radius:2mm;
  padding:3.5mm 4mm;font-family:'Consolas',monospace;font-size:8.6pt;line-height:1.55;
  margin:0 0 4mm;white-space:pre;overflow:hidden;
  page-break-inside:avoid;break-inside:avoid}
.chk{list-style:none;margin-left:0}
.chk li{padding-left:6mm;position:relative}
.chk li::before{content:'☐';position:absolute;left:0;font-weight:700;color:var(--green-deep)}
.pagebreak{page-break-before:always;break-before:page}
"""


def esc(t):
    return (str(t if t is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def page(title, body):
    return ("<!doctype html><html lang=\"ko\"><head><meta charset=\"utf-8\">"
            f"<title>{esc(title)}</title><style>"
            + font_face("GmarketSansMedium.woff", 500)
            + font_face("GmarketSansBold.woff", 700)
            + CSS + "</style></head><body>" + body + "</body></html>")


def render(html, html_path, pdf_path, footer_left=""):
    """HTML 을 남기고 PDF 를 뽑는다. HTML 도 남기는 이유 — 판이 깨졌을 때
    브라우저로 열어 봐야 어디서 넘쳤는지 보인다. PDF 만으론 못 본다."""
    io.open(html_path, "w", encoding="utf-8").write(html)
    from playwright.sync_api import sync_playwright
    foot = (f'<div style="font-family:Malgun Gothic,sans-serif;font-size:7pt;color:#8A968F;'
            f'width:100%;padding:0 14mm;display:flex;justify-content:space-between">'
            f'<span>{esc(footer_left)}</span>'
            f'<span class="pageNumber"></span></div>')
    with sync_playwright() as p:
        br = p.chromium.launch()
        pg = br.new_page()
        pg.goto("file:///" + os.path.abspath(html_path).replace("\\", "/"))
        pg.wait_for_timeout(800)          # 내장 폰트가 앉을 때까지
        pg.pdf(path=pdf_path, format="A4", print_background=True,
               display_header_footer=True, header_template="<div></div>",
               footer_template=foot,
               margin={"top": "16mm", "bottom": "16mm", "left": "18mm", "right": "18mm"})
        br.close()
    return pdf_path
