# SheTech Pathways (Static Website)

This folder contains a **modern, static portfolio landing page** for showcasing STEM careers and the **high school → college → career** pathway to each. Each career card includes a **QR code** that links directly to its career page.

## Open the site

- Open `index.html` in your browser.
- Use the navigation or scroll to **Career portfolio**.

## QR codes (important)

QR codes must point to a **publicly hosted** URL to work when scanned from a phone.

- If you’re viewing the site as local files (like `file:///...`), QR codes can’t know your public address.
- When the site is hosted (or served locally over `http://`), QR codes can be generated correctly and will work from the landing page + `qr-sheet.html` + career pages.

## Printable QR sheet

- Open `qr-sheet.html`
- Print from your browser

## Edit careers

- Landing page career cards are in `index.html` (search for `data-career`).
- Career pages are in `careers/`:
  - `careers/software-engineer.html`
  - `careers/data-scientist.html`
  - `careers/cybersecurity-analyst.html`
  - `careers/ux-ui-designer.html`
  - `careers/electrical-engineer.html`
  - `careers/biomedical-engineer.html`
  - `careers/environmental-scientist.html`
  - `careers/ai-ml-engineer.html`

## Import career details from Google Docs

If you have a public Google Drive folder of career docs where **the doc title matches the career title**, you can import that content into the corresponding career pages:

```bash
python tools/import_drive_docs.py
```

This will:
- Add/replace a **Career Details** section in each matching `careers/*.html` page
- Download images into `assets/doc-images/` and rewrite the pages to use local image files
- Generate `doc-media.js` so the landing-page career cards can use the **first image** from each Google Doc

## Branding

- Brand colors are defined in `styles.css`:
  - Navy: `#010193`
  - Cyan: `#00a6ce`
  - Magenta: `#bd1c81`
- Logos are referenced from `Design/`.

