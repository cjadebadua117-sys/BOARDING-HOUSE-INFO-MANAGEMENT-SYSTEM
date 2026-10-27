import re
from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn

DOC = r"C:\Users\Admin\Desktop\FinalProject_Badua_Summary.docx"
doc = Document(DOC)

blocks = []
for child in doc.element.body.iterchildren():
    if child.tag == qn("w:p"):
        blocks.append(Paragraph(child, doc))
    elif child.tag == qn("w:tbl"):
        blocks.append(Table(child, doc))

ok = lambda b: "PASS" if b else "**FAIL**"
results = []

# 1. chapters present
chapters = [p.text.strip() for p in blocks
            if isinstance(p, Paragraph) and re.fullmatch(r"CHAPTER \d+", p.text.strip())]
results.append(("Chapter headings 1-8 present",
                chapters == ["CHAPTER %d" % i for i in range(1, 9)], chapters))

# 2. cover names all four members
cover_parts = []
for b in blocks[:20]:
    if isinstance(b, Paragraph):
        cover_parts.append(b.text)
    else:
        for row in b.rows:
            cover_parts.extend(c.text for c in row.cells)
cover_text = "\n".join(cover_parts)
members = ["Badua, Christian Jade B.", "Bayubay, Jerome O.",
           "Layco, Mac Gabrielle L.", "Valdriz, Noemi G."]
results.append(("Cover lists all four members",
                all(m in cover_text for m in members), None))
results.append(("Cover lists section + instructor",
                "BSIS 3B" in cover_text and "Vincent Haber" in cover_text, None))

# 3. figures embedded with captions
images = sum(len(r._r.findall(".//" + qn("a:blip"))) for r in
             doc.inline_shapes) if False else len(doc.inline_shapes)
caps = [p.text.strip() for p in blocks if isinstance(p, Paragraph)
        and p.text.strip().startswith("Figure ")]
results.append(("Embedded figures", images >= 5, "images=%d" % images))
results.append(("Figure captions", len(caps) >= 5, caps))

# 4. test cases table: headers + >=5 rows
tc = None
for t in doc.tables:
    hdr = [c.text.strip() for c in t.rows[0].cells]
    if hdr[:1] == ["#"] and "Expected Result" in hdr:
        tc = t
results.append(("Test-case table found", tc is not None, None))
if tc:
    hdr = [c.text.strip() for c in tc.rows[0].cells]
    results.append(("Test header is Input/Expected/Actual/Result",
                    hdr == ["#", "Input / Action", "Expected Result",
                            "Actual Result", "Result"], hdr))
    body = tc.rows[1:]
    results.append(("At least 5 test cases", len(body) >= 5, len(body)))
    results.append(("Every case states PASS",
                    all(r.cells[4].text.strip() == "PASS" for r in body), None))

# 5. required sections
all_parts = []
for b in blocks:
    if isinstance(b, Paragraph):
        all_parts.append(b.text)
    else:
        for row in b.rows:
            all_parts.extend(c.text for c in row.cells)
alls = "\n".join(all_parts)
alls_lc = alls.lower()
required = {
    "Updated Level 0 context diagram": "Figure 1. Updated Level 0 Context Diagram",
    "Updated Level 1 DFD": "Figure 2. Updated Level 1 Data Flow Diagram",
    "Updated ERD": "Figure 3. Updated Entity Relationship Diagram",
    "Module B DFD": "Module B Data Flow Diagram",
    "Module B ERD": "Module B Entity Relationship Diagram",
    "Changes + why": "Changes Made to the Midterm Design and Why",
    "Implementation plan": "Implementation Plan",
    "Conversion method": "Conversion Plan",
    "Training": "User Training",
    "Support & maintenance": "Support and Maintenance",
    "Results vs objectives": "Results Against the Midterm Objectives",
    "References": "Reference List",
}
for label, needle in required.items():
    results.append((label, needle.lower() in alls_lc, None))

# 6. references section non-empty.
# Found by position, not by style: the bullets are drawn as literal characters
# so the bibliography does not depend on Word's list numbering.
ref_paras = [p.text.strip() for p in blocks if isinstance(p, Paragraph)]
heading = next((i for i, t in enumerate(ref_paras) if t.strip() == "Reference List"), None)
refs = []
if heading is not None:
    for t in ref_paras[heading + 1:]:
        if not t or t.startswith("CHAPTER"):
            continue
        refs.append(t)
results.append(("Reference list has entries", len(refs) >= 5, len(refs)))
results.append(("Every reference cites a year",
                all("(" in r and ")" in r for r in refs), None))
results.append(("No veterinary refs leaked",
                "American Animal Hospital" not in alls and "veterinary" not in alls.lower(),
                None))

# 7. fonts
n = doc.styles["Normal"]
results.append(("Body font Times New Roman 12",
                n.font.name == "Times New Roman" and n.font.size.pt == 12,
                "%s %s" % (n.font.name, n.font.size.pt)))

print("%-45s %-10s %s" % ("CHECK", "RESULT", "DETAIL"))
print("-" * 95)
fails = 0
for label, passed, detail in results:
    if not passed:
        fails += 1
    print("%-45s %-10s %s" % (label, ok(passed), detail if detail else ""))
print("-" * 95)
print("FAILURES:", fails)
