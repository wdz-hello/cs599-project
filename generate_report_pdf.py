"""Generate CS599 final report PDF using Playwright (Chromium) for proper rendering."""

import os
import re
import tempfile
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

REPORT_MD = "docs/CS599_大作业报告.md"
OUTPUT_PDF = "docs/CS599_大作业报告.pdf"

# Cover page info
COVER_INFO = [
    ("课程名称", "企业级应用软件设计与开发"),
    ("项目名称", "DevMind - SDD 驱动的多智能体软件开发助手"),
    ("方向", "方向一：Agentic AI 原生开发"),
    ("学号", "2025302959"),
    ("姓名", "王栋章"),
    ("专业", "计算机技术 / 软件工程"),
    ("指导教师", "戚欣"),
    ("提交日期", "2026 年 6 月 22 日"),
]

# CSS for PDF rendering
CSS = """
@page {
    size: A4;
    margin: 30mm 20mm 25mm 25mm;
}

@page :first {
    margin-top: 20mm;
}

/* Hide header/footer on first page */
@page :first {
    @top-center { content: none !important; }
    @bottom-center { content: none !important; }
}

body {
    font-family: "Microsoft YaHei", "微软雅黑", "PingFang SC", "Hiragino Sans GB", sans-serif;
    font-size: 10pt;
    line-height: 1.6;
    color: #333;
}

/* Running header - only visible after cover page */
.running-header {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    text-align: center;
    font-size: 8pt;
    color: #888;
    padding: 4mm 0;
    display: none;
}

/* Show header only after cover page */
.content-start ~ .running-header,
.running-header.visible {
    display: block;
}

h1 {
    font-size: 18pt;
    color: #16213e;
    border-bottom: 2px solid #16213e;
    padding-bottom: 4px;
    margin-top: 24pt;
    margin-bottom: 12pt;
}

h2 {
    font-size: 14pt;
    color: #0f3460;
    margin-top: 18pt;
    margin-bottom: 8pt;
}

h3 {
    font-size: 11pt;
    color: #533483;
    margin-top: 14pt;
    margin-bottom: 6pt;
}

p {
    margin: 6pt 0;
    text-align: justify;
}

ul, ol {
    margin: 6pt 0;
    padding-left: 24pt;
}

li {
    margin: 3pt 0;
}

code {
    font-family: "Consolas", "Courier New", monospace;
    background: #f4f4f4;
    padding: 1px 4px;
    border-radius: 3px;
    font-size: 9pt;
}

pre {
    background: #1e1e1e;
    color: #d4d4d4;
    padding: 12pt;
    border-radius: 4px;
    overflow-x: auto;
    font-family: "Consolas", "Courier New", monospace;
    font-size: 8.5pt;
    line-height: 1.4;
    margin: 10pt 0;
}

pre code {
    background: none;
    padding: 0;
    color: inherit;
}

table {
    border-collapse: collapse;
    width: 100%;
    margin: 10pt 0;
    font-size: 9pt;
}

th, td {
    border: 1px solid #ccc;
    padding: 4pt 6pt;
    text-align: left;
}

th {
    background: #16213e;
    color: white;
    font-weight: bold;
}

tr:nth-child(even) {
    background: #f5f5f8;
}

blockquote {
    border-left: 3px solid #888;
    margin: 8pt 0;
    padding: 4pt 12pt;
    color: #666;
    font-style: italic;
}

hr {
    border: none;
    border-top: 1px solid #ddd;
    margin: 16pt 0;
}

/* Cover page styles */
.cover-page {
    page-break-after: always;
    text-align: center;
    padding-top: 60pt;
}

/* Running header/footer */
.page-header {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    text-align: center;
    font-size: 8pt;
    color: #888;
    padding: 8pt 0;
    z-index: 1000;
}

.page-footer {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    text-align: center;
    font-size: 8pt;
    color: #888;
    padding: 8pt 0;
    z-index: 1000;
}

.cover-page h1 {
    font-size: 28pt;
    color: #16213e;
    border: none;
    margin-bottom: 8pt;
}

.cover-page .subtitle {
    font-size: 20pt;
    color: #0f3460;
    margin-bottom: 4pt;
}

.cover-page .desc {
    font-size: 14pt;
    color: #666;
    margin-bottom: 30pt;
}

.cover-page .divider {
    width: 60%;
    margin: 0 auto 20pt;
    border: none;
    border-top: 2px solid #16213e;
}

.cover-page .info-table {
    width: 70%;
    margin: 0 auto;
    text-align: left;
    border: none;
}

.cover-page .info-table td {
    border: none;
    padding: 4pt 8pt;
    font-size: 11pt;
}

.cover-page .info-table td:first-child {
    color: #888;
    width: 30%;
    text-align: right;
}
"""

# HTML template
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <title>CS599 期末大作业报告</title>
    <style>{css}</style>
</head>
<body>
{cover_html}
{content_html}
</body>
</html>"""


def generate_cover_html():
    """Generate the cover page HTML."""
    info_rows = ""
    for label, value in COVER_INFO:
        info_rows += f"<tr><td>{label}：</td><td>{value}</td></tr>\n"

    return f"""
<div class="cover-page">
    <h1>CS599 期末大作业报告</h1>
    <div class="subtitle">DevMind</div>
    <div class="desc">SDD 驱动的多智能体软件开发助手</div>
    <hr class="divider">
    <table class="info-table">
        {info_rows}
    </table>
</div>
"""


def strip_cover_section(md_content):
    """Remove everything up to and including the cover page section.

    The markdown starts with:
        # CS599 期末大作业报告
        ---
        ## 封面页
        ... (cover table) ...
        ---
        # 一、选题背景...

    We want to keep only from "# 一、" onwards.
    """
    lines = md_content.split("\n")
    result = []
    skip = True  # Start by skipping everything
    for line in lines:
        stripped = line.strip()
        # Stop skipping when we hit the first real chapter heading
        # (e.g., "# 一、选题背景与设计思想")
        if skip and re.match(r"^#\s+[一二三四五六七八九]", stripped):
            skip = False
            result.append(line)
            continue
        if not skip:
            result.append(line)
    return "\n".join(result)


def md_to_html(md_path):
    """Convert markdown file to HTML with extensions."""
    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Remove the cover page section (we have a proper HTML cover)
    md_content = strip_cover_section(md_content)

    # Use markdown extensions for tables, fenced code
    html_content = markdown.markdown(
        md_content,
        extensions=["tables", "fenced_code"],
    )

    return html_content


def extract_headings(md_path):
    """Extract headings from markdown for bookmarks, skipping code blocks."""
    headings = []
    in_code_block = False
    with open(md_path, "r", encoding="utf-8") as f:
        for line in f:
            stripped = line.strip()
            # Track fenced code blocks
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                continue
            if in_code_block:
                continue
            # Extract headings
            m = re.match(r"^(#{1,3})\s+(.+)$", stripped)
            if m:
                level = len(m.group(1))
                title = m.group(2).strip()
                # Skip cover page and main title headings
                if title in ("封面页", "CS599 期末大作业报告"):
                    continue
                headings.append((level, title))
    return headings


def add_bookmarks(pdf_path, headings):
    """Add bookmarks to PDF using PyMuPDF by searching for heading text."""
    import fitz

    doc = fitz.open(pdf_path)
    toc = []

    for level, title in headings:
        # Search for the heading text in the PDF
        found_page = None
        for page_num in range(doc.page_count):
            page = doc[page_num]
            # Search for the title text on this page
            text_instances = page.search_for(title)
            if text_instances:
                # Found on this page - use 1-based page number
                found_page = page_num + 1
                break

        if found_page:
            toc.append([level, title, found_page])

    if toc:
        doc.set_toc(toc)
        doc.saveIncr()
        print(f"Added {len(toc)} bookmarks to PDF")
    else:
        print("Warning: No bookmarks added (headings not found in PDF)")

    doc.close()


def generate():
    """Generate PDF using Playwright."""
    print("Converting markdown to HTML...")
    content_html = md_to_html(REPORT_MD)
    cover_html = generate_cover_html()

    full_html = HTML_TEMPLATE.format(css=CSS, cover_html=cover_html, content_html=content_html)

    # Write to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".html", delete=False, encoding="utf-8"
    ) as f:
        f.write(full_html)
        html_path = f.name

    try:
        print("Rendering PDF with Playwright...")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            # Load HTML
            page.goto(f"file://{Path(html_path).resolve()}")

            # Wait for fonts to load
            page.wait_for_timeout(1000)

            # Print to PDF
            page.pdf(
                path=OUTPUT_PDF,
                format="A4",
                print_background=True,
                margin={"top": "30mm", "bottom": "25mm", "left": "25mm", "right": "20mm"},
                display_header_footer=True,
                header_template='<div style="width:100%;text-align:center;font-size:8pt;color:#888;font-family:Microsoft YaHei,sans-serif;">CS599 &nbsp;|&nbsp; DevMind &nbsp;|&nbsp; 方向一：Agentic AI 原生开发</div>',
                footer_template='<div style="width:100%;text-align:center;font-size:8pt;color:#888;"><span class="pageNumber"></span></div>',
            )

            browser.close()

        print(f"PDF generated: {OUTPUT_PDF}")
        kb = os.path.getsize(OUTPUT_PDF) / 1024
        print(f"Size: {kb:.1f} KB")

        # Add bookmarks
        print("Adding bookmarks...")
        headings = extract_headings(REPORT_MD)
        add_bookmarks(OUTPUT_PDF, headings)

    finally:
        # Clean up temp HTML
        os.unlink(html_path)


if __name__ == "__main__":
    generate()
