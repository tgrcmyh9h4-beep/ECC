"""Build the English learning booklet PDF from the plain-text files in content/.

Markup (one item per line):
  @PART Title            part divider page
  # Title                chapter (starts a new page, listed in contents)
  ## Title / ### Title   section headings
  - text                 bullet
  > text                 tip box ("Tip:" style)
  ! wrong => right       common-mistake line
  | a | b | c |          table row (first row of a block is the header)
  EX: Title              exercise heading; following "N. question || answer" lines
  @PAGEBREAK             force a new page
  anything else          paragraph text (one paragraph per line)
Inline: **bold**, *italic*.
"""
import glob
import os
import re

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A5
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate,
                                PageBreak, PageTemplate, Paragraph, Spacer, Table,
                                TableStyle, CondPageBreak)
from reportlab.platypus.tableofcontents import TableOfContents

HERE = os.path.dirname(os.path.abspath(__file__))
FONT_DIR = "/usr/share/fonts/truetype/liberation"
pdfmetrics.registerFont(TTFont("Sans", f"{FONT_DIR}/LiberationSans-Regular.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Bold", f"{FONT_DIR}/LiberationSans-Bold.ttf"))
pdfmetrics.registerFont(TTFont("Sans-Italic", f"{FONT_DIR}/LiberationSans-Italic.ttf"))
pdfmetrics.registerFont(TTFont("Sans-BoldItalic", f"{FONT_DIR}/LiberationSans-BoldItalic.ttf"))
# Liberation lacks a few symbols; draw those with DejaVu
pdfmetrics.registerFont(TTFont("Sym", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
SYMBOLS = "✗✓✎↗↘₹"
pdfmetrics.registerFontFamily("Sans", normal="Sans", bold="Sans-Bold",
                              italic="Sans-Italic", boldItalic="Sans-BoldItalic")

BLUE = colors.HexColor("#1F4E79")
LIGHT = colors.HexColor("#E8F1FA")
TIP = colors.HexColor("#FFF6DD")
TIP_EDGE = colors.HexColor("#E0B84C")
BAD = colors.HexColor("#FDECEC")
GREY = colors.HexColor("#555555")

BASE = ParagraphStyle("base", fontName="Sans", fontSize=9.6, leading=13.6, spaceAfter=4)
S = {
    "p": BASE,
    "h1": ParagraphStyle("h1", parent=BASE, fontName="Sans-Bold", fontSize=17, leading=21,
                         textColor=BLUE, spaceAfter=10, spaceBefore=2),
    "h2": ParagraphStyle("h2", parent=BASE, fontName="Sans-Bold", fontSize=12.5, leading=16,
                         textColor=BLUE, spaceBefore=9, spaceAfter=4),
    "h3": ParagraphStyle("h3", parent=BASE, fontName="Sans-Bold", fontSize=10.6, leading=14,
                         spaceBefore=6, spaceAfter=3),
    "bullet": ParagraphStyle("bullet", parent=BASE, leftIndent=12, bulletIndent=2, spaceAfter=2),
    "tip": ParagraphStyle("tip", parent=BASE, fontSize=9.2, leading=13, spaceAfter=0),
    "cell": ParagraphStyle("cell", parent=BASE, fontSize=8.6, leading=11, spaceAfter=0),
    "cellh": ParagraphStyle("cellh", parent=BASE, fontName="Sans-Bold", fontSize=8.6, leading=11,
                            textColor=colors.white, spaceAfter=0),
    "ex": ParagraphStyle("ex", parent=BASE, leftIndent=14, firstLineIndent=-14, spaceAfter=2.5),
    "exh": ParagraphStyle("exh", parent=BASE, fontName="Sans-Bold", textColor=colors.HexColor("#2E7D32"),
                          spaceBefore=8, spaceAfter=4),
    "part": ParagraphStyle("part", parent=BASE, fontName="Sans-Bold", fontSize=24, leading=30,
                           alignment=TA_CENTER, textColor=BLUE),
    "partsub": ParagraphStyle("partsub", parent=BASE, fontSize=11, leading=16, alignment=TA_CENTER,
                              textColor=GREY),
    "title": ParagraphStyle("title", parent=BASE, fontName="Sans-Bold", fontSize=28, leading=36,
                            alignment=TA_CENTER, textColor=BLUE),
    "dlg": ParagraphStyle("dlg", parent=BASE, leftIndent=12, firstLineIndent=-12, spaceAfter=2.5),
    "ans": ParagraphStyle("ans", parent=BASE, fontSize=8.8, leading=12, spaceAfter=1.5),
}
TOC_STYLES = [
    ParagraphStyle("toc0", parent=BASE, fontName="Sans-Bold", fontSize=10, leading=14,
                   spaceBefore=6, textColor=BLUE),
    ParagraphStyle("toc1", parent=BASE, fontSize=9, leading=12, leftIndent=10, spaceAfter=0),
]


def inline(text):
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", text)
    return sym(text)


def sym(text):
    return "".join(f"<font name='Sym'>{c}</font>" if c in SYMBOLS else c for c in text)


class Doc(BaseDocTemplate):
    def __init__(self, path):
        super().__init__(path, pagesize=A5, leftMargin=14 * mm, rightMargin=14 * mm,
                         topMargin=15 * mm, bottomMargin=16 * mm,
                         title="Simple English: From Beginner to Fluent",
                         author="English Learning Booklet",
                         subject="A complete English course in simple language")
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height, id="f")
        self.addPageTemplates([
            PageTemplate("cover", [frame], onPage=lambda c, d: None),
            PageTemplate("body", [frame], onPageEnd=self.decorate),
        ])
        self.chapter = ""

    def beforeDocument(self):
        self.chapter = ""

    def decorate(self, canv, doc):
        canv.saveState()
        w, h = A5
        canv.setFont("Sans", 7.5)
        canv.setFillColor(GREY)
        canv.drawCentredString(w / 2, 8 * mm, str(doc.page))
        if self.chapter:
            canv.drawString(14 * mm, h - 9 * mm, self.chapter[:70])
        canv.setStrokeColor(colors.HexColor("#BBBBBB"))
        canv.setLineWidth(0.4)
        canv.line(14 * mm, h - 10.5 * mm, w - 14 * mm, h - 10.5 * mm)
        canv.restoreState()

    def afterFlowable(self, flowable):
        level = getattr(flowable, "toc_level", None)
        if level is None:
            return
        text = flowable.getPlainText()
        if level == 1:
            self.chapter = text
        key = f"k{id(flowable)}"
        self.canv.bookmarkPage(key)
        self.canv.addOutlineEntry(text, key, level=level, closed=level > 0)
        self.notify("TOCEntry", (level, text, self.page, key))


def heading(text, style, level=None):
    p = Paragraph(inline(text), S[style])
    if level is not None:
        p.toc_level = level
    return p


def boxed(paragraphs, bg, edge):
    t = Table([[paragraphs]], colWidths=[A5[0] - 28 * mm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 2.5, edge),
        ("LEFTPADDING", (0, 0), (-1, -1), 7), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return [Spacer(1, 2), t, Spacer(1, 5)]


def make_table(rows, width):
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    data = [[Paragraph(inline(c), S["cellh"]) for c in rows[0]]]
    data += [[Paragraph(inline(c), S["cell"]) for c in r] for r in rows[1:]]
    # widen columns that hold longer text
    lengths = [max(len(r[i]) for r in rows) + 6 for i in range(ncols)]
    total = sum(lengths)
    widths = [width * l / total for l in lengths]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#9FB6CD")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3.5), ("RIGHTPADDING", (0, 0), (-1, -1), 3.5),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return [Spacer(1, 3), t, Spacer(1, 6)]


def parse(path, width, answers):
    story, para, table, tips = [], [], [], []
    chapter = None
    ex_title = None
    ex_items = []

    def flush():
        nonlocal para, table, tips
        for text in para:
            story.append(Paragraph(inline(text), S["p"]))
        para = []
        if table:
            story.extend(make_table(table, width))
            table = []
        if tips:
            story.extend(boxed([Paragraph(inline(t), S["tip"]) for t in tips], TIP, TIP_EDGE))
            tips = []

    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n").strip()
        if not line.startswith("|") and table:
            flush()
        if not line.startswith(">") and tips:
            flush()
        if not line:
            flush()
            continue
        if line.startswith("@PART "):
            flush()
            title, _, sub = line[6:].partition("::")
            story += [NextPageTemplate("body"), PageBreak(), Spacer(1, 150),
                      heading(title.strip(), "part", 0), Spacer(1, 12),
                      Paragraph(inline(sub.strip()), S["partsub"]), PageBreak()]
        elif line == "@PAGEBREAK":
            flush()
            story.append(PageBreak())
        elif line.startswith("# "):
            flush()
            chapter = line[2:].strip()
            if story and not isinstance(story[-1], PageBreak):
                story.append(PageBreak())
            story.append(heading(chapter, "h1", 1))
        elif line.startswith("## "):
            flush()
            story += [CondPageBreak(40 * mm), heading(line[3:], "h2")]
        elif line.startswith("### "):
            flush()
            story += [CondPageBreak(25 * mm), heading(line[4:], "h3")]
        elif line.startswith("- "):
            flush()
            story.append(Paragraph(inline(line[2:]), S["bullet"], bulletText="•"))
        elif line.startswith("> "):
            if para:
                flush()
            tips.append(line[2:])
        elif line.startswith("! "):
            flush()
            wrong, _, right = line[2:].partition("=>")
            text = f"<font color='#C62828'>{sym('✗')} {inline(wrong.strip())}</font>&nbsp;&nbsp;&nbsp;" \
                   f"<font color='#2E7D32'>{sym('✓')} {inline(right.strip())}</font>"
            story.append(Paragraph(text, S["bullet"]))
        elif line.startswith("|"):
            if para or tips:
                flush()
            table.append([c.strip() for c in line.strip("|").split("|")])
        elif re.match(r"^[A-Z][A-Za-z]{0,13}( [A-Za-z]{1,10})?: ", line) and not line.startswith("EX:"):
            flush()
            who, _, said = line.partition(": ")
            story.append(Paragraph(f"<b>{inline(who)}:</b> " + inline(said), S["dlg"]))
        elif line.startswith("EX:"):
            flush()
            ex_title = line[3:].strip()
            story += [CondPageBreak(30 * mm), Paragraph(sym("✎") + " Practice: " + inline(ex_title), S["exh"])]
            ex_items = []
            answers.append((chapter, ex_title, ex_items))
        elif re.match(r"^\d+\.\s", line) and "||" in line:
            flush()
            q, _, a = line.partition("||")
            num, _, q = q.partition(".")
            story.append(Paragraph(f"<b>{num}.</b>&nbsp;" + inline(q.strip()), S["ex"]))
            ex_items.append((num, a.strip()))
        else:
            if tips or table:
                flush()
            para.append(line)
    flush()
    return story


def cover():
    return [
        Spacer(1, 95),
        Paragraph("SIMPLE ENGLISH", S["title"]),
        Spacer(1, 6),
        Paragraph("From Beginner to Fluent", ParagraphStyle("st", parent=S["partsub"], fontSize=15,
                                                           leading=20, textColor=BLUE)),
        Spacer(1, 28),
        Paragraph("A complete English course in easy words:<br/>sounds, grammar, all 12 tenses, "
                  "vocabulary,<br/>speaking, listening, reading, writing<br/>and a 90-day fluency plan",
                  S["partsub"]),
        Spacer(1, 40),
        Paragraph("With hundreds of practice exercises and a full answer key", S["partsub"]),
    ]


def build(out):
    doc = Doc(out)
    width = doc.width
    answers = []
    toc = TableOfContents(levelStyles=TOC_STYLES, dotsMinLevel=0)
    story = cover() + [NextPageTemplate("body"), PageBreak(),
                       Paragraph("Contents", S["h1"]), toc]
    for path in sorted(glob.glob(os.path.join(HERE, "content", "*.txt"))):
        story += parse(path, width, answers)

    story += [PageBreak(), heading("Answer Key", "h1", 1),
              Paragraph("Check your answers after you finish each exercise. "
                        "If you made a mistake, go back and read the lesson again.", S["p"])]
    last = None
    for chapter, title, items in answers:
        if not items:
            continue
        if chapter != last:
            story.append(Paragraph(inline(chapter), S["h3"]))
            last = chapter
        body = "  ".join(f"<b>{n}.</b> {inline(a)}" for n, a in items)
        story.append(Paragraph(f"<i>{inline(title)}:</i> {body}", S["ans"]))
    doc.multiBuild(story)
    return doc.page


if __name__ == "__main__":
    out = os.path.join(HERE, "Simple-English-Beginner-to-Fluent.pdf")
    pages = build(out)
    print(f"wrote {out} ({pages} pages)")
