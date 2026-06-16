import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape


W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"

OFFICE_DOCUMENT_REL_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument"
)
COMMENTS_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
)
DOCUMENT_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_zip_package(path: Path, files: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content)


def read_zip_text(docx_path: Path, member: str) -> str:
    with zipfile.ZipFile(docx_path, "r") as archive:
        return archive.read(member).decode("utf-8")


def zip_members(docx_path: Path) -> set[str]:
    with zipfile.ZipFile(docx_path, "r") as archive:
        return set(archive.namelist())


def direct_paragraphs(document_path: Path) -> list[ET.Element]:
    tree = ET.parse(document_path)
    root = tree.getroot()
    body = root.find(f".//{{{W_NS}}}body")
    assert body is not None
    return body.findall(f"{{{W_NS}}}p")


def paragraph_xml(document_path: Path, index: int) -> str:
    return ET.tostring(direct_paragraphs(document_path)[index], encoding="unicode")


def word_document_xml(paragraphs: list[str]) -> str:
    body = "\n".join(
        f'    <w:p><w:r><w:t xml:space="preserve">{text}</w:t></w:r></w:p>'
        for text in paragraphs
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<w:document xmlns:w="{W_NS}">\n'
        "  <w:body>\n"
        f"{body}\n"
        "  </w:body>\n"
        "</w:document>\n"
    )


def write_minimal_docx(path: Path, paragraphs: list[str]) -> None:
    write_zip_package(path, {"word/document.xml": word_document_xml(paragraphs)})


def write_docx_with_body(
    docx_path: Path,
    body_xml: str,
    comments: list[dict] | None = None,
) -> None:
    content_types = [
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '<Default Extension="xml" ContentType="application/xml"/>',
        f'<Override PartName="/word/document.xml" ContentType="{DOCUMENT_CONTENT_TYPE}"/>',
    ]
    files = {
        "_rels/.rels": (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<Relationships xmlns="{PKG_REL_NS}">\n'
            f'  <Relationship Id="rId1" Type="{OFFICE_DOCUMENT_REL_TYPE}" '
            'Target="word/document.xml"/>\n'
            "</Relationships>\n"
        ),
        "word/document.xml": (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<w:document xmlns:w="{W_NS}">\n'
            "  <w:body>\n"
            f"{body_xml}\n"
            "  </w:body>\n"
            "</w:document>\n"
        ),
    }

    if comments is not None:
        content_types.append(
            f'<Override PartName="/word/comments.xml" ContentType="{COMMENTS_CONTENT_TYPE}"/>'
        )
        comment_xml = []
        for comment in comments:
            author = escape(comment["author"], {'"': "&quot;"})
            text = escape(comment["text"])
            initials = escape(comment.get("initials", ""), {'"': "&quot;"})
            date = escape(
                comment.get("date", "2026-04-16T00:00:00Z"),
                {'"': "&quot;"},
            )
            cid = escape(str(comment["id"]), {'"': "&quot;"})
            comment_xml.append(
                f'  <w:comment w:id="{cid}" w:author="{author}" '
                f'w:initials="{initials}" w:date="{date}">'
                f"<w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
                "</w:comment>"
            )
        files["word/comments.xml"] = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<w:comments xmlns:w="{W_NS}">\n'
            f'{"".join(comment_xml)}\n'
            "</w:comments>\n"
        )

    files["[Content_Types].xml"] = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<Types xmlns="{CONTENT_TYPES_NS}">\n'
        f'  {"".join(content_types)}\n'
        "</Types>\n"
    )
    write_zip_package(docx_path, files)


def write_minimal_unpacked_docx_package(unpacked_dir: Path) -> None:
    write_file(
        unpacked_dir / "word" / "document.xml",
        f"""<?xml version="1.0" encoding="UTF-8"?>
<w:document xmlns:w="{W_NS}">
  <w:body>
    <w:p>
      <w:r><w:t>Clause text for comments.</w:t></w:r>
    </w:p>
  </w:body>
</w:document>
""",
    )
    write_file(
        unpacked_dir / "word" / "comments.xml",
        f"""<?xml version="1.0" encoding="UTF-8"?>
<w:comments xmlns:w="{W_NS}">
</w:comments>
""",
    )
    write_file(
        unpacked_dir / "word" / "_rels" / "document.xml.rels",
        f"""<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="{PKG_REL_NS}">
  <Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"
    Target="styles.xml"/>
</Relationships>
""",
    )
    write_file(
        unpacked_dir / "[Content_Types].xml",
        f"""<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="{CONTENT_TYPES_NS}">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="{DOCUMENT_CONTENT_TYPE}"/>
</Types>
""",
    )
