from __future__ import annotations

import math
import os
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "report_assets"
OUTPUT = ROOT / "Music_Recommendation_Big_Data_Case_Study_Report.docx"

RED = "A61B1B"
LIGHT_RED = "F7E6E6"
PALE_RED = "FCF4F4"
BLACK = "000000"
WHITE = "FFFFFF"
GRAY = "666666"
LIGHT_GRAY = "D9D9D9"
PIL_RED = f"#{RED}"
PIL_PALE_RED = f"#{PALE_RED}"
PIL_BLACK = f"#{BLACK}"
PIL_WHITE = f"#{WHITE}"
PIL_GRAY = "#666666"
PIL_LIGHT_GRAY = f"#{LIGHT_GRAY}"


def font_path(name: str) -> str | None:
    candidates = [
        Path("C:/Windows/Fonts") / name,
        Path("C:/Windows/Fonts") / name.replace(".ttf", ".TTF"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def pil_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = font_path("timesbd.ttf" if bold else "times.ttf") or font_path("arialbd.ttf" if bold else "arial.ttf")
    return ImageFont.truetype(path, size) if path else ImageFont.load_default()


def wrap_lines(draw: ImageDraw.ImageDraw, text: str, font, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textbbox((0, 0), trial, font=font)[2] <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def draw_box(draw: ImageDraw.ImageDraw, xy, title: str, body: str, fill: str = PIL_PALE_RED, outline: str = PIL_RED) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=18, fill=fill, outline=outline, width=4)
    title_font = pil_font(30, True)
    body_font = pil_font(24)
    draw.text((x1 + 22, y1 + 18), title, fill=PIL_RED, font=title_font)
    lines = wrap_lines(draw, body, body_font, x2 - x1 - 44)
    y = y1 + 64
    for line in lines:
        draw.text((x1 + 22, y), line, fill=PIL_BLACK, font=body_font)
        y += 32


def arrow(draw: ImageDraw.ImageDraw, start, end, color: str = PIL_RED, width: int = 5) -> None:
    draw.line([start, end], fill=color, width=width)
    x1, y1 = start
    x2, y2 = end
    angle = math.atan2(y2 - y1, x2 - x1)
    length = 18
    left = (x2 - length * math.cos(angle - math.pi / 6), y2 - length * math.sin(angle - math.pi / 6))
    right = (x2 - length * math.cos(angle + math.pi / 6), y2 - length * math.sin(angle + math.pi / 6))
    draw.polygon([end, left, right], fill=color)


def make_architecture_diagram() -> Path:
    ASSETS.mkdir(exist_ok=True)
    image = Image.new("RGB", (1800, 980), PIL_WHITE)
    draw = ImageDraw.Draw(image)
    title_font = pil_font(38, True)
    small = pil_font(22)
    draw.text((50, 28), "Figure 2  Distributed System Architecture", fill=PIL_RED, font=title_font)
    draw.text((50, 78), "Docker Compose demonstration with HDFS replication factor 3", fill=PIL_GRAY, font=small)

    draw_box(draw, (50, 190, 420, 390), "Last.fm 1K", "Raw TSV events and user profiles")
    draw_box(draw, (50, 550, 420, 760), "Preparation", "Streaming parser, SQLite aggregation, integer ID mapping, metadata catalog")

    draw_box(draw, (540, 160, 1180, 420), "HDFS Cluster", "h-primary NameNode plus h-worker1, h-worker2 and h-worker3 DataNodes\nReplication factor: 3")
    draw_box(draw, (540, 540, 1180, 760), "Distributed Processing", "Apache Mahout item-based CF\nApache Spark batch and streaming jobs")

    draw_box(draw, (1310, 160, 1740, 390), "Serving Layer", "FastAPI recommendation API\nMongoDB event and analytics store")
    draw_box(draw, (1310, 550, 1740, 760), "User Interface", "Streamlit dashboard\nRecommendations, catalog, health and live statistics")

    arrow(draw, (420, 290), (540, 290))
    arrow(draw, (235, 390), (235, 550))
    arrow(draw, (420, 655), (540, 655))
    arrow(draw, (860, 420), (860, 540))
    arrow(draw, (1180, 290), (1310, 290))
    arrow(draw, (1525, 390), (1525, 550))
    arrow(draw, (1180, 650), (1310, 650))

    footer = "Data preparation creates compact Mahout input and human-readable song metadata."
    draw.text((50, 870), footer, fill=PIL_GRAY, font=small)
    path = ASSETS / "architecture_diagram.png"
    image.save(path)
    return path


def make_methodology_diagram() -> Path:
    image = Image.new("RGB", (1600, 470), PIL_WHITE)
    draw = ImageDraw.Draw(image)
    title_font = pil_font(34, True)
    box_font = pil_font(24, True)
    body_font = pil_font(21)
    draw.text((44, 24), "Figure 1  Methodology Workflow", fill=PIL_RED, font=title_font)
    labels = [
        ("1  Ingest", "Read Last.fm TSV"),
        ("2  Prepare", "Aggregate and map IDs"),
        ("3  Store", "HDFS with RF 3"),
        ("4  Learn", "Mahout item CF"),
        ("5  Serve", "API and dashboard"),
    ]
    x = 35
    for index, (title, body) in enumerate(labels):
        x1, x2 = x, x + 260
        draw.rounded_rectangle((x1, 155, x2, 335), radius=16, fill=PIL_PALE_RED, outline=PIL_RED, width=4)
        draw.text((x1 + 18, 180), title, fill=PIL_RED, font=box_font)
        for i, line in enumerate(wrap_lines(draw, body, body_font, 220)):
            draw.text((x1 + 18, 235 + i * 30), line, fill=PIL_BLACK, font=body_font)
        if index < len(labels) - 1:
            arrow(draw, (x2 + 8, 245), (x2 + 48, 245), width=4)
        x += 305
    path = ASSETS / "methodology_workflow.png"
    image.save(path)
    return path


def make_scale_chart() -> Path:
    image = Image.new("RGB", (1500, 850), PIL_WHITE)
    draw = ImageDraw.Draw(image)
    title_font = pil_font(36, True)
    label_font = pil_font(25, True)
    value_font = pil_font(22)
    draw.text((60, 34), "Figure 3  Project Data Scale", fill=PIL_RED, font=title_font)
    draw.text((60, 82), "Logarithmic scale used to show both millions and hundreds clearly", fill=PIL_GRAY, font=value_font)

    data = [
        ("Raw events", 19150868),
        ("Aggregated interactions", 4620928),
        ("Unique tracks", 1505202),
        ("Users", 992),
        ("Users with recommendations", 874),
    ]
    left, right = 420, 1400
    top, bottom = 170, 730
    max_log = math.log10(20_000_000)
    for tick in [1, 10, 100, 1000, 10000, 100000, 1000000, 10000000]:
        x = left + int((math.log10(tick) / max_log) * (right - left))
        draw.line((x, top - 8, x, bottom), fill=PIL_LIGHT_GRAY, width=2)
        label = f"{tick:,}" if tick < 1_000_000 else f"{tick // 1_000_000}M"
        draw.text((x - 18, bottom + 18), label, fill=PIL_GRAY, font=value_font)

    row_h = 95
    for idx, (label, value) in enumerate(data):
        y = top + idx * row_h + 20
        draw.text((60, y), label, fill=PIL_BLACK, font=label_font)
        x2 = left + int((math.log10(value) / max_log) * (right - left))
        draw.rounded_rectangle((left, y + 2, x2, y + 42), radius=10, fill=PIL_RED)
        formatted = f"{value:,}"
        draw.text((min(x2 + 15, 1240), y + 2), formatted, fill=PIL_BLACK, font=value_font)
    draw.text((left, bottom + 58), "Count (log scale)", fill=PIL_GRAY, font=value_font)
    path = ASSETS / "data_scale_chart.png"
    image.save(path)
    return path


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_borders(cell, color: str = LIGHT_GRAY, size: str = "6") -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    borders = tc_pr.first_child_found_in("w:tcBorders")
    if borders is None:
        borders = OxmlElement("w:tcBorders")
        tc_pr.append(borders)
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        tag = "w:" + edge
        element = borders.find(qn(tag))
        if element is None:
            element = OxmlElement(tag)
            borders.append(element)
        element.set(qn("w:val"), "single")
        element.set(qn("w:sz"), size)
        element.set(qn("w:space"), "0")
        element.set(qn("w:color"), color)


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120) -> None:
    tc = cell._tc
    tc_pr = tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for margin, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{margin}"))
        if node is None:
            node = OxmlElement(f"w:{margin}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_run_font(run, size=12, color=BLACK, bold=False, italic=False, name="Times New Roman") -> None:
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    run.font.size = Pt(size)
    run.font.color.rgb = RGBColor.from_string(color)
    run.bold = bold
    run.italic = italic


def format_paragraph(paragraph, space_after=6, line_spacing=1.15) -> None:
    paragraph.paragraph_format.space_after = Pt(space_after)
    paragraph.paragraph_format.line_spacing = line_spacing


def add_text(doc: Document, text: str, bold_lead: str | None = None, align=None) -> None:
    p = doc.add_paragraph()
    if align:
        p.alignment = align
    format_paragraph(p, space_after=7, line_spacing=1.15)
    if bold_lead and text.startswith(bold_lead):
        r = p.add_run(bold_lead)
        set_run_font(r, bold=True)
        r = p.add_run(text[len(bold_lead):])
        set_run_font(r)
    else:
        r = p.add_run(text)
        set_run_font(r)


def add_bullet(doc: Document, text: str) -> None:
    p = doc.add_paragraph(style="List Bullet")
    format_paragraph(p, space_after=3, line_spacing=1.08)
    r = p.add_run(text)
    set_run_font(r)


def add_heading(doc: Document, number: str, title: str, level: int = 1) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.keep_with_next = True
    p.paragraph_format.space_before = Pt(12 if level == 1 else 7)
    p.paragraph_format.space_after = Pt(5)
    label = f"{number}. {title}" if number else title
    r = p.add_run(label)
    set_run_font(r, size=14 if level == 1 else 14, color=RED, bold=True)


def add_caption(doc: Document, text: str) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    format_paragraph(p, space_after=8, line_spacing=1.0)
    r = p.add_run(text)
    set_run_font(r, size=11, color=GRAY, italic=True)


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    header = table.rows[0]
    header._tr.get_or_add_trPr().append(OxmlElement("w:tblHeader"))
    for i, value in enumerate(headers):
        cell = header.cells[i]
        if widths:
            cell.width = Inches(widths[i])
        cell.text = ""
        set_cell_shading(cell, RED)
        set_cell_borders(cell)
        set_cell_margins(cell)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        format_paragraph(p, space_after=0, line_spacing=1.0)
        r = p.add_run(value)
        set_run_font(r, size=11, color=WHITE, bold=True)
    for row_index, row in enumerate(rows):
        cells = table.add_row().cells
        for col_index, value in enumerate(row):
            cell = cells[col_index]
            if widths:
                cell.width = Inches(widths[col_index])
            cell.text = ""
            set_cell_shading(cell, WHITE if row_index % 2 == 0 else PALE_RED)
            set_cell_borders(cell)
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT if col_index == 0 or len(value) > 35 else WD_ALIGN_PARAGRAPH.CENTER
            format_paragraph(p, space_after=0, line_spacing=1.05)
            r = p.add_run(str(value))
            set_run_font(r, size=10.5, color=BLACK)
    doc.add_paragraph().paragraph_format.space_after = Pt(2)


def add_image(doc: Document, path: Path, width: float) -> None:
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.keep_with_next = True
    run = p.add_run()
    run.add_picture(str(path), width=Inches(width))


def add_code(doc: Document, code: str) -> None:
    for line in code.strip("\n").splitlines():
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Inches(0.3)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        r = p.add_run(line)
        set_run_font(r, size=10, color="333333", name="Consolas")


def add_page_number(paragraph) -> None:
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("Page ")
    set_run_font(run, size=10, color=GRAY)
    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = "PAGE"
    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char1)
    run._r.append(instr_text)
    run._r.append(fld_char2)


def configure_document(doc: Document) -> None:
    section = doc.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.65)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)
    section.header_distance = Inches(0.3)
    section.footer_distance = Inches(0.3)

    normal = doc.styles["Normal"]
    normal.font.name = "Times New Roman"
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
    normal.font.size = Pt(12)
    normal.font.color.rgb = RGBColor.from_string(BLACK)
    normal.paragraph_format.space_after = Pt(7)
    normal.paragraph_format.line_spacing = 1.15

    for style_name in ("Title", "Subtitle"):
        style = doc.styles[style_name]
        style.font.name = "Times New Roman"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        style.font.color.rgb = RGBColor.from_string(RED)
    doc.styles["Title"].font.size = Pt(16)
    doc.styles["Title"].font.bold = True
    doc.styles["Subtitle"].font.size = Pt(14)
    doc.styles["Subtitle"].font.color.rgb = RGBColor.from_string(RED)

    if "Report Header" not in [s.name for s in doc.styles]:
        style = doc.styles.add_style("Report Header", WD_STYLE_TYPE.PARAGRAPH)
        style.font.name = "Times New Roman"
        style._element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        style.font.size = Pt(10)
        style.font.color.rgb = RGBColor.from_string(RED)
    header = section.header.paragraphs[0]
    header.style = "Report Header"
    header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    header.text = "Scalable Music Recommendation System"
    for run in header.runs:
        set_run_font(run, size=10, color=RED)
    footer = section.footer.paragraphs[0]
    add_page_number(footer)


def create_report() -> Path:
    architecture = make_architecture_diagram()
    methodology = make_methodology_diagram()
    scale_chart = make_scale_chart()

    doc = Document()
    configure_document(doc)

    # Cover page
    p = doc.add_paragraph(style="Title")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(105)
    p.paragraph_format.space_after = Pt(18)
    r = p.add_run("Scalable Music Recommendation System Using Big Data Technologies")
    set_run_font(r, size=16, color=RED, bold=True)

    p = doc.add_paragraph(style="Subtitle")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(65)
    r = p.add_run("Case Study Report")
    set_run_font(r, size=14, color=RED, bold=True)

    for line in [
        "Prepared by Kresha Shah",
        "PRN 24070126512",
        "Big Data Analytics Project",
        "October 2026",
    ]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(7)
        r = p.add_run(line)
        set_run_font(r, size=12, color=BLACK, bold=line.startswith("Prepared"))

    doc.add_page_break()

    add_heading(doc, "", "Contents")
    contents = [
        "1. Title of Case Study",
        "2. Problem Statement and Objectives",
        "3. Background and Introduction",
        "4. Dataset Description",
        "5. Methodology",
        "6. System Architecture and Workflow",
        "7. Big Data Tools and Technologies Used",
        "8. Implementation Queries and Algorithms",
        "9. Analysis and Results",
        "10. Visualization and Graphs",
        "11. Conclusion",
        "12. References",
    ]
    for item in contents:
        add_bullet(doc, item)
    doc.add_page_break()

    add_heading(doc, "1", "Title of Case Study")
    add_text(doc, "Scalable Music Recommendation System Using Big Data Technologies")
    add_text(doc, "The case study presents a scalable music recommendation pipeline that converts a large Last.fm listening-history dataset into personalized item-based recommendations. The solution combines distributed storage, batch recommendation generation, metadata enrichment, API delivery, a dashboard, and a streaming analytics layer.")

    add_heading(doc, "2", "Problem Statement and Objectives")
    add_text(doc, "Music platforms collect large volumes of listening events. A useful recommendation system must process these events efficiently, preserve meaningful track metadata, and return recommendations in a form that a user can understand. A system that exposes only numeric item IDs is technically functional but not suitable for a user-facing demonstration. This project addresses both the scalability problem and the presentation problem.")
    add_text(doc, "The main objectives are:")
    for item in [
        "Prepare the Last.fm 1K event log without loading the complete raw file into memory.",
        "Aggregate repeated listens into user-track interaction counts and create stable integer IDs for Mahout.",
        "Design an HDFS cluster with three DataNodes and replication factor 3 for the target distributed deployment.",
        "Generate top-10 personalized recommendations using Apache Mahout item-based collaborative filtering with log-likelihood similarity.",
        "Use real artist and track-name metadata for content similarity and hybrid ranking without inventing genre or mood labels.",
        "Join recommendation IDs with artist and track metadata so that the application displays meaningful music names.",
        "Expose recommendations through FastAPI and present analytics and system status through Streamlit.",
    ]:
        add_bullet(doc, item)

    add_heading(doc, "3", "Background and Introduction")
    add_text(doc, "The project uses the Last.fm 1K dataset, which contains listening events collected through the Last.fm API for nearly one thousand users. Each event includes a user, timestamp, artist identifier, artist name, track identifier, and track name. Such data is naturally suited to collaborative filtering because a user’s repeated listening behavior provides implicit feedback about the tracks they prefer.")
    add_text(doc, "The system follows a batch-first recommendation design. A preparation script converts the raw event stream into compact interaction and metadata files. Apache Mahout processes the user-item interaction matrix and produces recommendations. The application layer loads the recommendation output and enriches numeric item IDs with human-readable metadata. Apache Spark is also included for batch, medallion-style, and structured streaming analytics so the project demonstrates both recommendation processing and broader Big Data processing concepts.")
    add_text(doc, "The final design separates storage, computation, serving, and presentation. This separation makes it possible to scale the processing layer independently from the user interface and to explain the role of each Big Data tool during project evaluation.")

    add_heading(doc, "4", "Dataset Description")
    add_text(doc, "The primary source is the Last.fm 1K dataset version 1.0. The raw event file is tab-separated and contains one listening event per line. The accompanying profile file contains user gender, age, country, and signup date when available. The dataset is provided for non-commercial use under the terms described by Last.fm.")
    add_table(doc, ["File or output", "Important fields", "Purpose"], [
        ["Raw event TSV", "user, timestamp, artist MBID, artist name, track MBID, track name", "Source listening history"],
        ["User profile TSV", "user, gender, age, country, signup", "Optional user profile context"],
        ["train_triplets.txt", "user key, track key, play count", "Readable aggregated interaction file"],
        ["mahout_input.csv", "integer user ID, integer item ID, count", "Mahout recommendation input"],
        ["song_metadata.csv", "item ID, artist, track, MBIDs, plays, listeners", "Human-readable catalog enrichment"],
    ], widths=[1.55, 2.75, 2.65])
    add_text(doc, "The raw file contains 19,150,868 events and 992 unique users. The preparation process retained all valid events and produced 4,620,928 aggregated user-track interactions across 1,505,202 unique tracks. The conversion was intentionally implemented as a streaming process backed by SQLite so the 2.5 GB source file did not need to be held in memory.")

    add_heading(doc, "5", "Methodology")
    add_image(doc, methodology, 6.6)
    add_caption(doc, "Figure 1  Methodology workflow from raw events to recommendations")
    add_text(doc, "The methodology is organized into seven stages:")
    add_table(doc, ["Stage", "Activity", "Produced artifact"], [
        ["1. Ingest", "Read the raw tab-separated event log line by line.", "Validated raw event stream"],
        ["2. Aggregate", "Count repeated listens for every user and track pair.", "4,620,928 compact interactions"],
        ["3. Map", "Assign stable integer IDs to users and tracks.", "User and song mapping files"],
        ["4. Enrich", "Preserve artist, track, MBID, play and listener metadata.", "Song catalog"],
        ["5. Store", "Place Mahout input and outputs in HDFS paths.", "Distributed data layout"],
        ["6. Recommend", "Run Mahout item-based collaborative filtering.", "Top-10 recommendations"],
        ["7. Serve", "Load results through FastAPI and display them in Streamlit.", "Interactive application"],
    ], widths=[1.15, 3.6, 2.2])
    add_text(doc, "The project also includes a Spark Structured Streaming path for JSON events. The streaming process validates event schemas, computes live statistics, and writes Bronze, Silver, and Gold Parquet outputs. This provides a real-time analytics extension to the offline recommendation workflow.")

    add_heading(doc, "6", "System Architecture and Workflow")
    add_image(doc, architecture, 6.65)
    add_caption(doc, "Figure 2  Target distributed architecture with three HDFS replica locations")
    add_text(doc, "The target Docker Compose topology contains a NameNode, a YARN ResourceManager, three HDFS DataNodes, three YARN NodeManagers, a Spark master, three Spark workers, MongoDB, FastAPI, and Streamlit. The DataNodes are h-worker1, h-worker2, and h-worker3. The HDFS configuration sets the default replication factor to 3 so a block can be stored on all three worker nodes.")
    add_text(doc, "For a local college demonstration, these nodes are separate Docker containers on one physical computer. This demonstrates distributed roles and replica configuration, but it does not provide hardware-level fault isolation. A production cloud version could place the master role on one virtual machine and the three DataNodes on three separate worker virtual machines. Creating three additional complete application stacks is unnecessary; only the worker services are added for the HDFS and Spark cluster.")
    add_text(doc, "The normal workflow is: Last.fm data is prepared locally, the Mahout input is uploaded to HDFS, Mahout generates recommendations, recommendation output is copied to the application output directory, FastAPI loads the output and metadata, and Streamlit calls the API to display recommendations and operational statistics.")

    add_heading(doc, "7", "Big Data Tools and Technologies Used")
    add_table(doc, ["Technology", "Role in the project", "Reason for use"], [
        ["Docker Compose", "Defines reproducible services and cluster roles.", "Makes the local distributed demonstration repeatable."],
        ["Hadoop HDFS", "Stores input and output files across DataNodes.", "Provides distributed storage and configurable replication."],
        ["YARN", "Provides cluster resource-management roles.", "Represents the standard Hadoop execution layer."],
        ["Apache Mahout 0.13.0", "Runs item-based collaborative filtering.", "Scales recommendation generation using a mature Big Data algorithm."],
        ["Apache Spark 3.5.9", "Batch, medallion, and streaming analytics.", "Supports scalable transformations and live event processing."],
        ["Python and SQLite", "Streams, aggregates, and maps source events.", "Avoids loading the raw dataset into memory."],
        ["FastAPI", "Provides REST endpoints for recommendations and catalog data.", "Offers a lightweight typed serving layer."],
        ["Streamlit", "Provides the interactive dashboard.", "Makes results easy to inspect during a demonstration."],
        ["MongoDB", "Stores application events and analytics statistics.", "Provides document-oriented persistence for operational data."],
    ], widths=[1.5, 3.0, 2.45])

    add_heading(doc, "8", "Implementation Queries and Algorithms")
    add_heading(doc, "8.1", "Data Preparation Algorithm", level=2)
    add_text(doc, "The preparation script uses a streaming parser and SQLite upserts. The logical operation is equivalent to the following query:")
    add_code(doc, "INSERT INTO interactions(user_key, track_key, play_count)\nVALUES (?, ?, ?)\nON CONFLICT(user_key, track_key)\nDO UPDATE SET play_count = play_count + excluded.play_count;")
    add_text(doc, "After aggregation, users and tracks are ordered and assigned integer IDs. Mahout receives rows in the form user ID, item ID, play count. The metadata catalog retains the original artist and track names, allowing the API to translate recommendation IDs back into readable results.")
    add_heading(doc, "8.2", "Recommendation Algorithm", level=2)
    add_text(doc, "Apache Mahout runs item-based collaborative filtering. It compares items using log-likelihood similarity derived from co-occurrence patterns in user histories. For each user, items already consumed are considered and a ranked list of unseen items is produced. The configured recommendation count is 10 items per user.")
    add_text(doc, "The content-based path uses the available Last.fm artist and track-name metadata. It tokenizes the text fields, finds candidate tracks sharing artist or title terms, and scores them with a normalized content similarity. Hybrid ranking uses normalized Mahout score, content similarity when metadata is available, and popularity. If metadata is unavailable, the service documents and uses behavioral co-occurrence as a fallback.")
    add_code(doc, "mahout recommenditembased \\\n+  --input /music/lastfm/mahout/input/mahout_input.csv \\\n+  --output /music/lastfm/mahout/output \\\n+  --similarityClassname SIMILARITY_LOGLIKELIHOOD \\\n+  --numRecommendations 10")
    add_heading(doc, "8.3", "Application Endpoints", level=2)
    add_table(doc, ["Endpoint", "Function"], [
        ["GET /health", "Reports service status, catalog size, interaction count and recommendation coverage."],
        ["GET /recommend/{user_id}", "Returns personalized recommendations with track and artist metadata."],
        ["GET /similar/{song_id}", "Returns similar items from the recommendation service."],
        ["GET /songs/{song_id}", "Returns catalog metadata for one item."],
        ["GET /user/{user_id}/history", "Returns a user listening history view."],
        ["GET /live/stats", "Returns streaming activity and live processing statistics."],
    ], widths=[2.2, 4.75])

    add_heading(doc, "9", "Analysis and Results")
    add_text(doc, "The preparation and recommendation stages produced the following measured results:")
    add_table(doc, ["Metric", "Result", "Interpretation"], [
        ["Raw listening events", "19,150,868", "Scale of the original Last.fm event log"],
        ["Valid events retained", "19,150,868", "No invalid rows were removed during conversion"],
        ["Unique users", "992", "User population represented in the interactions"],
        ["Unique tracks", "1,505,202", "Catalog size after MBID/name-based identity resolution"],
        ["Aggregated interactions", "4,620,928", "Compact user-track play-count matrix"],
        ["Mahout recommendation records", "874 users", "Users for whom the batch produced recommendations"],
        ["Recommendations per user", "10", "Configured top-N result size"],
        ["Mahout output file", "135,133 bytes", "Generated part-r-00000 recommendation output"],
    ], widths=[2.25, 1.55, 3.15])
    add_text(doc, "The batch job completed successfully with Apache Mahout and processed 4,620,928 interaction records. The API smoke test reported 1,505,202 catalog items, 4,620,928 interactions, and 874 users with active recommendation output. A sample request for internal user 3143 returned readable metadata instead of only numeric IDs.")
    add_table(doc, ["Item ID", "Track", "Artist", "Score"], [
        ["165560", "Just In The Nick Of Rhyme", "Common", "66.52203"],
        ["341196", "Africa", "D'Angelo", "66.52203"],
        ["317548", "Ako", "Fela Ransome Kuti & Nigeria 70", "66.52203"],
    ], widths=[1.0, 2.55, 2.65, 0.75])
    add_caption(doc, "Table 1  Example enriched recommendations returned for internal user 3143")
    add_table(doc, ["Validation", "Status", "Evidence"], [
        ["Python unit tests", "Passed", "32 tests defined; targeted parser, content and event-flow tests passed"],
        ["Python compilation", "Passed", "backend and scripts compile successfully"],
        ["Compose syntax", "Passed", "docker compose config completed successfully"],
        ["API health smoke test", "Passed", "Health response returned dataset and catalog counts"],
        ["Content and event-flow unit checks", "Passed", "Metadata recommendations and Spark input publication covered by tests"],
        ["Three-DataNode runtime check", "Configured", "h-worker1, h-worker2 and h-worker3 defined; verify after cluster startup"],
    ], widths=[2.1, 1.2, 3.65])

    add_heading(doc, "10", "Visualization and Graphs")
    add_image(doc, scale_chart, 6.65)
    add_caption(doc, "Figure 3  Relative scale of the prepared dataset and recommendation coverage")
    add_text(doc, "The chart shows why a Big Data workflow is appropriate. The raw event log contains more than nineteen million records, while the prepared interaction matrix remains several million rows and the track catalog exceeds one million items. The recommendation output covers 874 users, which is a substantial portion of the 992-user population. The dashboard complements the chart by exposing recommendation results, catalog metadata, health information, and live streaming statistics.")
    add_text(doc, "For a final demonstration, the dashboard should be shown with a user ID lookup, readable track and artist names, the system health panel, and the live statistics view. The HDFS web interface and YARN ResourceManager interface can be used as supporting evidence that the distributed roles are running when Docker Desktop is resumed.")

    add_heading(doc, "11", "Conclusion")
    add_text(doc, "This case study demonstrates a complete Big Data music recommendation workflow. A large Last.fm event log is streamed, validated, aggregated, mapped to integer identifiers, stored for distributed processing, and transformed into personalized recommendations. Mahout provides the recommendation algorithm, HDFS provides the distributed storage model, Spark provides the batch and streaming analytics layer, FastAPI provides typed services, and Streamlit provides an accessible demonstration interface.")
    add_text(doc, "The most important improvement for the cluster design is the three-DataNode configuration with HDFS replication factor 3. The configuration has been added to Docker Compose, and the final operational step is to start the cluster and run an HDFS replication verification command. Because all local containers share one physical host, the setup demonstrates distributed roles and data replication rather than independent hardware failure recovery. A cloud deployment can preserve the same logical architecture by placing the master and worker roles on separate virtual machines.")
    add_text(doc, "The project therefore meets the core academic goals of scalable data preparation, collaborative filtering, distributed storage design, metadata-aware serving, and interactive analytics. Future work could add offline evaluation metrics such as precision@K and recall@K, improve cold-start handling for new users, and deploy the worker nodes on separate cloud virtual machines.")

    add_heading(doc, "12", "References")
    references = [
        "Last.fm Dataset. lastfm-dataset-1K README, Version 1.0, March 2010. Local project copy: dataset/lastfm-dataset-1K/README.txt.",
        "Last.fm API Terms of Service. https://www.last.fm/api/tos",
        "Apache Hadoop. HDFS Architecture and User Documentation. https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-hdfs/HDFSTutorial.html",
        "Apache Mahout. Mahout 0.13.0 Documentation. https://mahout.apache.org/docs/0.13.0/",
        "Apache Spark. Spark 3.5.9 Documentation. https://spark.apache.org/docs/3.5.9/",
        "FastAPI Documentation. https://fastapi.tiangolo.com/",
        "Streamlit Documentation. https://docs.streamlit.io/",
        "MongoDB Documentation. https://www.mongodb.com/docs/",
        "Docker Compose Documentation. https://docs.docker.com/compose/",
    ]
    for ref in references:
        add_bullet(doc, ref)
    add_text(doc, "Report preparation note: measured values in this report were taken from the project output files and validation runs. The three-DataNode topology is configured in docker-compose.yml; live verification should be performed after Docker Desktop is resumed.", bold_lead="Report preparation note:")

    doc.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(create_report())
