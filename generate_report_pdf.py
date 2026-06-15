"""Generate CS599 final report PDF with bookmarks for navigation pane."""

import os, re
from fpdf import FPDF

REPORT_MD = "docs/CS599_大作业报告.md"
OUTPUT_PDF = "docs/CS599_大作业报告.pdf"
FONT_FILE = "C:/Windows/Fonts/msyh.ttc"
W = 170  # usable width in mm (A4 portrait with 20mm margins)


def clean(text):
    return text.replace("—", "--").replace("‘", "'").replace("’", "'") \
        .replace("“", "\"").replace("”", "\"").replace("–", "-")


class ReportPDF(FPDF):
    def __init__(self):
        super().__init__("P", "mm", "A4")
        self.add_font("C", "", FONT_FILE)
        self.add_font("C", "B", FONT_FILE)
        self.set_auto_page_break(True, 18)
        self.set_left_margin(25)
        self.set_right_margin(20)

    def header(self):
        if self.page_no() > 1:
            self.set_font("C", "", 7)
            self.set_text_color(140, 140, 140)
            self.cell(0, 5, "CS599  |  DevMind  |  方向一：Agentic AI 原生开发", align="C")
            self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("C", "", 7)
        self.set_text_color(140, 140, 140)
        self.cell(0, 10, str(self.page_no()), align="C")

    def write_text(self, text, size=9, bold=False):
        self.set_font("C", "B" if bold else "", size)
        self.set_text_color(51, 51, 51)
        self.multi_cell(W, size * 0.55, clean(text))

    def write_heading(self, title, level):
        if level == 1:
            self.add_page()
            self.start_section(title, level=0)
            self.set_font("C", "B", 15)
            self.set_text_color(22, 33, 62)
            self.set_fill_color(240, 240, 245)
            self.cell(W, 9, "  " + clean(title), fill=True)
            self.ln(12)
        elif level == 2:
            self.start_section(title, level=1)
            self.set_font("C", "B", 12)
            self.set_text_color(15, 52, 96)
            self.cell(W, 7, clean(title))
            self.ln(9)
        elif level == 3:
            self.start_section(title, level=2)
            self.set_font("C", "B", 10.5)
            self.set_text_color(83, 52, 131)
            self.cell(W, 6.5, clean(title))
            self.ln(8)

    def write_code_block(self, lines):
        self.set_fill_color(30, 30, 30)
        self.set_text_color(200, 200, 200)
        self.set_font("C", "", 7.5)
        for cl in lines:
            self.cell(W, 4, cl[:120], fill=True)
            self.ln()
        self.ln(3)

    def write_table(self, rows):
        if not rows:
            return
        num_cols = max(len(r) for r in rows)
        col_w = W / num_cols
        self.set_font("C", "", 8)
        for ri, row in enumerate(rows):
            if ri == 0:
                self.set_fill_color(22, 33, 62)
                self.set_text_color(255, 255, 255)
            elif ri % 2 == 0:
                self.set_fill_color(245, 245, 248)
                self.set_text_color(51, 51, 51)
            else:
                self.set_fill_color(255, 255, 255)
                self.set_text_color(51, 51, 51)
            for cell in row:
                self.cell(col_w, 6, clean(cell[:55]), border=1, fill=True)
            self.ln()
        self.ln(3)


def generate():
    pdf = ReportPDF()
    pdf.set_display_mode(zoom="fullwidth", layout="single")

    with open(REPORT_MD, "r", encoding="utf-8") as f:
        lines = f.readlines()

    # ===== Cover page =====
    pdf.add_page()
    pdf.ln(25)
    pdf.set_font("C", "B", 26)
    pdf.set_text_color(22, 33, 62)
    pdf.cell(W, 12, "CS599 期末大作业报告", align="C")
    pdf.ln(18)
    pdf.set_font("C", "B", 18)
    pdf.set_text_color(15, 52, 96)
    pdf.cell(W, 10, "DevMind", align="C")
    pdf.ln(12)
    pdf.set_font("C", "", 13)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(W, 8, "SDD 驱动的多智能体软件开发助手", align="C")
    pdf.ln(22)
    pdf.set_draw_color(22, 33, 62)
    pdf.line(45, pdf.get_y(), 165, pdf.get_y())
    pdf.ln(12)

    info = [
        ("课程名称", "企业级应用软件设计与开发"),
        ("项目名称", "DevMind - SDD 驱动的多智能体软件开发助手"),
        ("方向", "方向一：Agentic AI 原生开发"),
        ("学号", "-"),
        ("姓名", "王栋章"),
        ("专业", "计算机技术 / 软件工程"),
        ("指导教师", "戚欣"),
        ("提交日期", "2026 年 6 月 22 日"),
    ]
    for label, value in info:
        pdf.set_font("C", "", 11)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(32, 8, label + "：")
        pdf.set_text_color(51, 51, 51)
        pdf.cell(0, 8, clean(value))
        pdf.ln(8)

    # ===== Content =====
    i = 0
    in_code = False
    code_buf = []
    in_table = False
    table_buf = []

    while i < len(lines):
        line = lines[i].rstrip()

        # Code block
        if line.strip().startswith("```"):
            if in_code:
                pdf.write_code_block(code_buf)
                code_buf = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # Table
        if line.strip().startswith("|") and line.strip().endswith("|"):
            in_table = True
            table_buf.append(line)
            i += 1
            continue
        if in_table:
            in_table = False
            rows = []
            for tl in table_buf:
                cells = [c.strip() for c in tl.split("|")[1:-1]]
                if all(re.match(r"^:?-{3,}:?$", c) for c in cells):
                    continue
                rows.append(cells)
            pdf.write_table(rows)
            table_buf = []

        # Heading
        h = re.match(r"^(#{1,6})\s+(.+)$", line)
        if h:
            pdf.write_heading(h.group(2).strip(), len(h.group(1)))
            i += 1
            continue

        # HR
        if line.strip() in ("---", "***", "___"):
            pdf.set_draw_color(210, 210, 210)
            y = pdf.get_y()
            pdf.line(25, y, 195, y)
            pdf.ln(3)
            i += 1
            continue

        # Blockquote
        if line.strip().startswith(">"):
            t = clean(line.strip()[1:].strip())
            pdf.set_font("C", "", 9)
            pdf.set_text_color(100, 100, 100)
            pdf.cell(W, 5, "| " + t)
            pdf.ln()
            i += 1
            continue

        # Bullet / numbered list
        stripped = line.strip()
        if stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("+ "):
            pdf.set_font("C", "", 9)
            pdf.set_text_color(51, 51, 51)
            pdf.cell(W, 5.5, "  • " + clean(stripped[2:]))
            pdf.ln()
            i += 1
            continue

        # Bold standalone line
        bm = re.match(r"^\*\*(.+)\*\*$", stripped)
        if bm:
            pdf.set_font("C", "B", 10)
            pdf.set_text_color(51, 51, 51)
            pdf.cell(W, 6, clean(bm.group(1)))
            pdf.ln()
            i += 1
            continue

        # Empty line
        if not stripped:
            pdf.ln(2)
            i += 1
            continue

        # Normal paragraph
        pdf.write_text(stripped, size=9)
        i += 1

    pdf.output(OUTPUT_PDF)
    kb = os.path.getsize(OUTPUT_PDF) / 1024
    print(f"PDF generated: {OUTPUT_PDF}")
    print(f"Size: {kb:.1f} KB  |  Pages: {pdf.page_no()}")


if __name__ == "__main__":
    generate()
