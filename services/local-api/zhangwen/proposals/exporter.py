"""Proposal export helpers using Python standard library only."""

from __future__ import annotations

from html import escape as xml_escape
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

from zhangwen.proposals.models import ProposalVersion


def render_markdown(
    proposal: ProposalVersion, *, document_title: str = "项目立项书"
) -> bytes:
    lines = [
        f"# {document_title} v{proposal.version}",
        "",
        f"- 方案版本：v{proposal.solutionVersion}",
        f"- 状态：{proposal.status.value}",
        f"- 创建时间：{proposal.createdAt}",
        "",
        "| 立项项 | 执行内容 |",
        "|---|---|",
    ]
    for section in proposal.sections:
        lines.append(
            f"| {_markdown_cell(section.title)} | {_markdown_cell(section.content)} |"
        )
    lines.append("")
    return "\n".join(lines).encode("utf-8")


def render_docx(
    proposal: ProposalVersion, *, document_title: str = "项目立项书"
) -> bytes:
    body = [
        _paragraph(f"{document_title} v{proposal.version}", style="Title"),
        _paragraph(f"方案版本：v{proposal.solutionVersion}"),
        _paragraph(f"状态：{proposal.status.value}"),
        _proposal_table(proposal),
    ]
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{''.join(body)}<w:sectPr/></w:body></w:document>"
    )
    output = BytesIO()
    with ZipFile(output, "w", ZIP_DEFLATED) as docx:
        docx.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            "</Types>",
        )
        docx.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            "</Relationships>",
        )
        docx.writestr("word/document.xml", document)
    return output.getvalue()


def render_pdf(
    proposal: ProposalVersion, *, document_title: str = "Project Proposal"
) -> bytes:
    text = [f"{document_title} v{proposal.version}", f"Solution v{proposal.solutionVersion}"]
    text.extend(section.title for section in proposal.sections)
    stream_lines = ["BT", "/F1 12 Tf", "72 760 Td"]
    for line in text[:28]:
        safe = line.encode("ascii", "ignore").decode("ascii") or "Proposal"
        stream_lines.append(f"({safe}) Tj")
        stream_lines.append("0 -18 Td")
    stream_lines.append("ET")
    stream = "\n".join(stream_lines).encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = BytesIO()
    output.write(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(output.tell())
        output.write(f"{index} 0 obj\n".encode("ascii"))
        output.write(obj)
        output.write(b"\nendobj\n")
    xref_offset = output.tell()
    output.write(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    output.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.write(f"{offset:010d} 00000 n \n".encode("ascii"))
    output.write(
        f"trailer << /Root 1 0 R /Size {len(objects) + 1} >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("ascii")
    )
    return output.getvalue()


def _paragraph(text: str, style: str | None = None) -> str:
    style_xml = f"<w:pPr><w:pStyle w:val=\"{style}\"/></w:pPr>" if style else ""
    return f"<w:p>{style_xml}<w:r><w:t>{xml_escape(text)}</w:t></w:r></w:p>"


def _proposal_table(proposal: ProposalVersion) -> str:
    rows = [_table_row("立项项", "执行内容", header=True)]
    rows.extend(
        _table_row(section.title, section.content)
        for section in proposal.sections
    )
    borders = (
        "<w:tblPr><w:tblBorders>"
        '<w:top w:val="single" w:sz="4" w:color="B7C2D0"/>'
        '<w:left w:val="single" w:sz="4" w:color="B7C2D0"/>'
        '<w:bottom w:val="single" w:sz="4" w:color="B7C2D0"/>'
        '<w:right w:val="single" w:sz="4" w:color="B7C2D0"/>'
        '<w:insideH w:val="single" w:sz="4" w:color="D8DEE8"/>'
        '<w:insideV w:val="single" w:sz="4" w:color="D8DEE8"/>'
        "</w:tblBorders></w:tblPr>"
    )
    return f"<w:tbl>{borders}{''.join(rows)}</w:tbl>"


def _table_row(label: str, content: str, *, header: bool = False) -> str:
    row_props = "<w:trPr><w:tblHeader/></w:trPr>" if header else ""
    return (
        f"<w:tr>{row_props}"
        f"{_table_cell(label, bold=header, width=2200)}"
        f"{_table_cell(content, bold=header, width=6800)}"
        "</w:tr>"
    )


def _table_cell(text: str, *, bold: bool, width: int) -> str:
    runs: list[str] = []
    for index, line in enumerate(text.splitlines() or [""]):
        if index:
            runs.append("<w:r><w:br/></w:r>")
        run_props = "<w:rPr><w:b/></w:rPr>" if bold else ""
        runs.append(f"<w:r>{run_props}<w:t>{xml_escape(line)}</w:t></w:r>")
    return (
        f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/></w:tcPr>'
        f"<w:p>{''.join(runs)}</w:p></w:tc>"
    )


def _markdown_cell(text: str) -> str:
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r\n", "<br>").replace("\n", "<br>")
