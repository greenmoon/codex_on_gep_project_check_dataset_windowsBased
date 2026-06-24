from pathlib import Path
import textwrap


SOURCE = Path("A1886_GEP_algorithm_summary_v01.md")
OUTPUT = Path("A1886_GEP_algorithm_summary_v01.pdf")


def escape_pdf_text(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
    )


def markdown_to_lines(text: str):
    lines = []
    in_code = False
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.strip().startswith("```"):
            in_code = not in_code
            continue
        if not in_code:
            if line.startswith("# "):
                line = line[2:].upper()
                lines.append("")
            elif line.startswith("## "):
                line = line[3:]
                lines.append("")
            elif line.startswith("- "):
                line = "  - " + line[2:]
            elif line and line[0].isdigit() and ". " in line[:4]:
                line = "  " + line
            line = line.replace("`", "")
        lines.append(line)
    return lines


def wrap_lines(lines, width=88):
    wrapped = []
    for line in lines:
        if not line:
            wrapped.append("")
            continue
        indent = len(line) - len(line.lstrip(" "))
        subsequent = " " * indent
        pieces = textwrap.wrap(
            line,
            width=width,
            subsequent_indent=subsequent,
            replace_whitespace=False,
            drop_whitespace=True,
        )
        wrapped.extend(pieces or [""])
    return wrapped


def paginate(lines, lines_per_page=46):
    pages = []
    page = []
    for line in lines:
        page.append(line)
        if len(page) >= lines_per_page:
            pages.append(page)
            page = []
    if page:
        pages.append(page)
    return pages


def build_pdf(pages):
    objects = []

    def add_object(body: str) -> int:
        objects.append(body)
        return len(objects)

    font_id = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")
    page_ids = []

    for page_num, page_lines in enumerate(pages, 1):
        stream_lines = ["BT", "/F1 10 Tf", "50 785 Td", "14 TL"]
        for i, line in enumerate(page_lines):
            if i:
                stream_lines.append("T*")
            stream_lines.append(f"({escape_pdf_text(line)}) Tj")
        stream_lines.append("T*")
        stream_lines.append(f"(Page {page_num} of {len(pages)}) Tj")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines)
        content_id = add_object(
            f"<< /Length {len(stream.encode('latin-1'))} >>\nstream\n{stream}\nendstream"
        )
        page_id = add_object(
            f"<< /Type /Page /Parent 0 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        )
        page_ids.append(page_id)

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    pages_id = add_object(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>")
    catalog_id = add_object(f"<< /Type /Catalog /Pages {pages_id} 0 R >>")

    patched = []
    for obj in objects:
        patched.append(obj.replace("/Parent 0 0 R", f"/Parent {pages_id} 0 R"))

    output = bytearray()
    output.extend(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(patched, 1):
        offsets.append(len(output))
        output.extend(f"{idx} 0 obj\n{obj}\nendobj\n".encode("latin-1"))

    xref_offset = len(output)
    output.extend(f"xref\n0 {len(patched) + 1}\n".encode("latin-1"))
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    output.extend(
        f"trailer\n<< /Size {len(patched) + 1} /Root {catalog_id} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n".encode("latin-1")
    )
    return output


def main():
    text = SOURCE.read_text(encoding="utf-8")
    lines = wrap_lines(markdown_to_lines(text))
    pages = paginate(lines)
    OUTPUT.write_bytes(build_pdf(pages))
    print(f"Wrote {OUTPUT} ({len(pages)} pages)")


if __name__ == "__main__":
    main()
