"""The policy wording and the claims manual, split into their numbered sections."""

import re
from typing import Literal

from backend.db import DATA
from backend.models import Section, SectionSummary

Document = Literal["policy-wording", "claims-manual"]
FILES: dict[Document, str] = {
    "policy-wording": "policy_wording.md",
    "claims-manual": "claims_manual.md",
}
HEADING = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)
TOPIC = re.compile(r"^(?:- )?\*\*(.+?)[.:]\*\*", re.MULTILINE)


def sections(document: Document) -> list[Section]:
    """Split a document at its numbered headings, such as "## 7. Emergency Medical"."""
    text = (DATA / FILES[document]).read_text(encoding="utf-8")
    parts = HEADING.split(text)[1:]
    return [
        Section(document=document, number=int(number), title=title, text=body.strip())
        for number, title, body in zip(
            parts[::3], parts[1::3], parts[2::3], strict=True
        )
    ]


def contents(document: Document) -> list[SectionSummary]:
    """List a document's sections with the topics each one covers."""
    return [
        SectionSummary(
            number=section.number,
            title=section.title,
            topics=TOPIC.findall(section.text),
        )
        for section in sections(document)
    ]
