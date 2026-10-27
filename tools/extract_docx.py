import sys
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph

def iter_block_items(parent):
    from docx.oxml.ns import qn
    body = parent.element.body
    for child in body.iterchildren():
        if child.tag == qn('w:p'):
            yield Paragraph(child, parent)
        elif child.tag == qn('w:tbl'):
            yield Table(child, parent)

path = sys.argv[1]
doc = Document(path)
n = 0
for block in iter_block_items(doc):
    if isinstance(block, Paragraph):
        txt = block.text.strip()
        if not txt:
            continue
        n += 1
        try:
            stylename = block.style.name
        except Exception:
            stylename = "None"
        print(f"[P|{stylename}] {txt}")
    else:
        n += 1
        print("[TABLE]")
        for row in block.rows:
            cells = [c.text.strip().replace("\n", " / ") for c in row.cells]
            print("  | " + " || ".join(cells))
print(f"\n=== TOTAL BLOCKS: {n} ===")
