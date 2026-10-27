import fitz

PDF = r"C:\Users\Admin\Desktop\FinalProject_Badua_Summary.pdf"
doc = fitz.open(PDF)
print("pages:", doc.page_count)
print("page size:", doc[0].rect)

for i, page in enumerate(doc, 1):
    text = page.get_text().strip()
    imgs = page.get_images(full=True)
    # detect content outside the 0.8in / 0.7in margins (1in = 72pt)
    left, right = 0.8 * 72, page.rect.width - 0.8 * 72
    over = []
    for b in page.get_text("blocks"):
        x0, y0, x1, y1 = b[:4]
        if x1 > right + 6 or x0 < left - 6:
            over.append((round(x0), round(x1), b[4][:45].replace("\n", " ")))
    first = text.split("\n")[0][:60] if text else "(EMPTY)"
    print(f"\n--- p{i}: imgs={len(imgs)} chars={len(text)} overflow={len(over)} | {first}")
    for o in over[:4]:
        print("      OVERFLOW:", o)

# where are the images
print("\n=== IMAGE PLACEMENT ===")
for i, page in enumerate(doc, 1):
    for im in page.get_images(full=True):
        for r in page.get_image_rects(im[0]):
            print(f"p{i}: {round(r.width)}x{round(r.height)}pt at y={round(r.y0)}")
