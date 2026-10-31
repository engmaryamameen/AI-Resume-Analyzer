from app.documents.schema import NormalizedDocument
from app.ml.contracts import Passage, format_context


def build_passages(doc: NormalizedDocument) -> list[Passage]:
    """Every résumé block outside the contact header becomes a passage, with the role it sits in as context."""
    kind_of = doc.section_kind_by_id()
    blocks = doc.block_map()
    header_of: dict[str, str] = {}
    for entry in doc.entries:
        entry_header = blocks[entry.header_block_id].text
        for block_id in (entry.header_block_id, *entry.block_ids):
            header_of[block_id] = entry_header
    passages = []
    for block in doc.blocks:
        section = kind_of.get(block.section_id, "other")
        if section == "header":
            continue
        header = header_of.get(block.id) if block.kind != "entry_header" else None
        passages.append(
            Passage(
                id=block.id,
                text=block.text,
                context=format_context(section, header),
                section_kind=section,
            )
        )
    return passages
