"""
Import public Google Docs from a shared Drive folder into local career pages.

How it works:
- Scrapes the public Drive folder HTML for (docTitle, docId) pairs.
- Loads careers from careers-data.js and matches by exact title.
- Exports each Google Doc as HTML and extracts/cleans the body content.
- Injects the cleaned HTML into careers/<slug>.html inside a "Career details" section.

This is safe to re-run. Only careers with matching docs are updated.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import html as html_lib
import json
import re
import sys
import urllib.request
from bs4 import BeautifulSoup
import base64
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CAREERS_DIR = ROOT / "careers"
DATA_JS = ROOT / "careers-data.js"
ASSETS_DIR = ROOT / "assets" / "doc-images"
DOC_MEDIA_JS = ROOT / "doc-media.js"


DRIVE_FOLDER_URL = "https://drive.google.com/drive/folders/1qEclhK1GyA88y9GfJQKiPc-YqqxTVXkh?usp=sharing"


@dataclass(frozen=True)
class Career:
    title: str
    slug: str
    category: str
    description: str
    high_school: list[str]
    college: list[str]
    career: list[str]
    resources: list[str]


def read_text(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8", "ignore")


def parse_careers_data() -> list[Career]:
    raw = DATA_JS.read_text(encoding="utf-8")
    # Be tolerant of leading whitespace/BOM
    raw = raw.lstrip("\ufeff \t\r\n")
    raw = re.sub(r"^window\.SHT_CAREERS\s*=\s*", "", raw).strip()
    if raw.endswith(";"):
        raw = raw[:-1]
    data = json.loads(raw)
    out: list[Career] = []
    for c in data:
        out.append(
            Career(
                title=str(c.get("title", "")).strip(),
                slug=str(c.get("slug", "")).strip(),
                category=str(c.get("category", "")).strip(),
                description=str(c.get("description", "")).strip(),
                high_school=list(c.get("highSchool", []) or []),
                college=list(c.get("college", []) or []),
                career=list(c.get("career", []) or []),
                resources=list(c.get("resources", []) or []),
            )
        )
    return out


def extract_doc_ids_from_folder(folder_html: str) -> dict[str, str]:
    """
    Extract (title -> docId) from the public Drive folder HTML.
    This relies on embedded data structures that include:
      "<docId>"],null,null,null,"application/vnd.google-apps.document", ... [[["<Title>",null,true]]]
    """
    text = html_lib.unescape(folder_html)
    found: dict[str, str] = {}

    # Find docId anchors
    id_pat = re.compile(
        r'"(?P<id>[A-Za-z0-9_-]{20,})"],null,null,null,"application/vnd\.google-apps\.document"',
        re.MULTILINE,
    )
    # Title marker appears near the doc entry
    title_pat = re.compile(r'\[\[\["(?P<title>[^"]+)",null,true\]\]\]', re.MULTILINE)

    for m in id_pat.finditer(text):
        doc_id = m.group("id").strip()
        if not doc_id:
            continue
        chunk = text[m.end() : m.end() + 3000]
        tm = title_pat.search(chunk)
        if not tm:
            continue
        title = tm.group("title").strip()
        if title and title not in found:
            found[title] = doc_id

    return found


def export_doc_html(doc_id: str) -> str:
    # Public export URL
    url = f"https://docs.google.com/document/d/{doc_id}/export?format=html"
    return read_text(url)


def _save_image_from_src(img_src: str, out_path: Path) -> bool:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists() and out_path.stat().st_size > 0:
        return True

    if img_src.startswith("data:image/"):
        # data:image/jpeg;base64,...
        try:
            header, b64 = img_src.split(",", 1)
            data = base64.b64decode(b64)
            out_path.write_bytes(data)
            return True
        except Exception:
            return False

    # http(s) image
    try:
        req = urllib.request.Request(
            img_src,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            out_path.write_bytes(resp.read())
        return True
    except Exception:
        return False


def _ext_from_src(img_src: str) -> str:
    if img_src.startswith("data:image/"):
        m = re.match(r"data:image/([a-zA-Z0-9.+-]+);base64", img_src)
        if m:
            t = m.group(1).lower()
            if "jpeg" in t or t == "jpg":
                return "jpg"
            if "png" in t:
                return "png"
            if "webp" in t:
                return "webp"
        return "img"
    try:
        path = urlparse(img_src).path
        ext = Path(path).suffix.lower().lstrip(".")
        return ext or "img"
    except Exception:
        return "img"


def clean_google_doc_html(exported_html: str, *, slug: str) -> tuple[str, str | None]:
    """
    Returns (cleaned_inner_html, hero_image_src_for_landing_or_none).
    Also downloads images locally and rewrites <img src> to ../assets/doc-images/<file>.
    """
    soup = BeautifulSoup(exported_html, "html.parser")
    body = soup.body
    if body is None:
        return ("", None)

    # Remove scripts/styles and other noise
    for el in body.find_all(["script", "style", "noscript"]):
        el.decompose()

    # Find the main content container if possible
    main = None
    for cand in body.find_all(["div", "article", "section"], recursive=False):
        if cand.get_text(strip=True):
            main = cand
            break
    if main is None:
        main = body

    # Download images locally + rewrite src
    hero_root_src: str | None = None
    img_idx = 0
    for img in main.find_all("img"):
        src = img.get("src") or ""
        if not src:
            continue
        img_idx += 1
        ext = _ext_from_src(src)
        filename = f"{slug}-{img_idx}.{ext}"
        out_path = ASSETS_DIR / filename
        ok = _save_image_from_src(src, out_path)
        if not ok:
            continue
        # landing-page path (root-relative)
        if hero_root_src is None:
            hero_root_src = f"./assets/doc-images/{filename}"
        # career-page path (one directory deeper)
        img["src"] = f"../assets/doc-images/{filename}"

    # Strip excessive attributes and normalize images
    for tag in main.find_all(True):
        # Keep href/src/alt
        keep = {"href", "src", "alt"}
        attrs = dict(tag.attrs)
        tag.attrs = {k: v for k, v in attrs.items() if k in keep}
        if tag.name == "img":
            tag.attrs.setdefault("loading", "lazy")
            tag.attrs.setdefault("decoding", "async")

    # Drop empty paragraphs
    for p in main.find_all("p"):
        if not p.get_text(strip=True) and not p.find("img"):
            p.decompose()

    # Return inner HTML (not including <body>)
        return ("".join(str(x) for x in main.contents).strip(), hero_root_src)


def inject_into_career_page(existing: str, title: str, details_html: str) -> str:
    """
    Replace (or insert) a section with id="careerDetails" inside the main content area.
    """
    soup = BeautifulSoup(existing, "html.parser")
    main = soup.find("main")
    if main is None:
        return existing

    container = soup.new_tag("section")
    container["class"] = "panel"
    container["id"] = "careerDetails"

    h2 = soup.new_tag("h2")
    h2.string = "Career Details"
    container.append(h2)

    wrap = soup.new_tag("div")
    wrap["class"] = "gdoc"
    wrap.append(BeautifulSoup(details_html, "html.parser"))
    container.append(wrap)

    # Remove any existing details section
    old = soup.find(id="careerDetails")
    if old is not None:
        old.replace_with(container)
    else:
        # Insert after the first panel in the main column if possible
        first_panel = main.select_one(".content-grid > div .panel")
        if first_panel is not None:
            first_panel.insert_after(container)
        else:
            main.append(container)

    # Ensure the title exists somewhere for correctness (not required, but helpful)
    # We do not modify the header wording here to avoid overriding user edits.
    return str(soup)


def _norm_heading(s: str) -> str:
    s = s.strip().lower()
    # remove emoji and punctuation-ish chars by keeping alnum/spaces
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


SECTION_ORDER = [
    "pathway snapshot",
    "women who lead the way",
    "day in the life",
    "mini-activity: try this!",
    "careers & resources",
    "you belong here",
]


def split_doc_into_sections(cleaned_inner_html: str) -> dict[str, str]:
    """
    Split cleaned Google Doc HTML into sections keyed by canonical heading.
    We look for headings matching:
      Women Who Lead the Way, Day in the Life, Mini-Activity, Opportunities, You Belong Here
    """
    soup = BeautifulSoup(f"<div>{cleaned_inner_html}</div>", "html.parser")
    root = soup.div
    if root is None:
        return {}

    targets = {k: k for k in SECTION_ORDER}
    # allow minor variants
    targets.update(
        {
            "mini activity try this": "mini-activity: try this!",
            "mini activity try this!": "mini-activity: try this!",
            "mini activity": "mini-activity: try this!",
            "mini activity try this ": "mini-activity: try this!",
            "mini activity try this  ": "mini-activity: try this!",
            "mini activity try this": "mini-activity: try this!",
            "careers and resources": "careers & resources",
            "careers resources": "careers & resources",
            "opportunities resources": "careers & resources",
            "opportunities and resources": "careers & resources",
            "opportunities & resources": "careers & resources",
        }
    )

    sections: dict[str, list[str]] = {}
    current_key: str | None = None

    for node in list(root.children):
        if not getattr(node, "name", None):
            continue
        # Use Heading 2 as the section delimiter per the docs.
        if node.name == "h2":
            text = node.get_text(" ", strip=True)
            norm = _norm_heading(text)
            if norm in targets:
                current_key = targets[norm]
                sections.setdefault(current_key, [])
                continue
        if current_key:
            sections[current_key].append(str(node))

    # join
    out: dict[str, str] = {}
    for k in SECTION_ORDER:
        if k in sections:
            out[k] = "".join(sections[k]).strip()
    return out


def build_doc_panels_html(section_map: dict[str, str]) -> str:
    """
    Create panel HTML blocks in the desired order.
    Also applies special table styling for 'Day in the Life'.
    """
    if not section_map:
        return ""

    out = []
    title_case = {
        "pathway snapshot": "Pathway Snapshot",
        "women who lead the way": "Women Who Lead the Way",
        "day in the life": "Day in the Life",
        "mini-activity: try this!": "Mini-Activity: Try This!",
        "careers & resources": "Careers & Resources",
        "you belong here": "You Belong Here",
    }

    for key in SECTION_ORDER:
        inner = section_map.get(key, "").strip()
        if not inner:
            continue
        soup = BeautifulSoup(f"<div>{inner}</div>", "html.parser")
        if key == "day in the life":
            for table in soup.find_all("table"):
                existing = table.get("class") or []
                table["class"] = list(dict.fromkeys(existing + ["sht-table", "sht-table-day"]))
        if key == "pathway snapshot":
            for table in soup.find_all("table"):
                existing = table.get("class") or []
                table["class"] = list(dict.fromkeys(existing + ["sht-table", "sht-table-pathway"]))
        panel = f'<section class="panel doc-panel" data-doc-section="{key.replace(" ","-")}"><h2>{title_case[key]}</h2><div class="gdoc">{str(soup.div)[5:-6] if soup.div else inner}</div></section>'
        out.append(panel)
    return "\n".join(out)


def main() -> int:
    if not DATA_JS.exists():
        print(f"Missing {DATA_JS}", file=sys.stderr)
        return 2

    careers = parse_careers_data()
    folder_html = read_text(DRIVE_FOLDER_URL)
    title_to_id = extract_doc_ids_from_folder(folder_html)

    # Some Docs may have slightly different titles than the Excel careers.
    # Add lightweight aliasing here so "file title matches career" can tolerate minor variations.
    explicit_aliases: dict[str, str] = {
        "Graphic Designer": "Graphics Designer",
        # Current XLSX uses "Tech Choreographer"
        "Choreographer with Tech": "Tech Choreographer",
    }

    def norm(s: str) -> str:
        s = s.strip().lower()
        s = re.sub(r"&", "and", s)
        s = re.sub(r"[^a-z0-9]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        # normalize plurals for designer(s)
        s = s.replace("graphics designer", "graphic designer")
        return s

    # Build a docId lookup by career title (with alias/normalization)
    doc_id_for_career: dict[str, str] = {}
    career_by_norm: dict[str, str] = {norm(c.title): c.title for c in careers}

    for doc_title, doc_id in title_to_id.items():
        mapped = explicit_aliases.get(doc_title, doc_title)
        n = norm(mapped)
        target = career_by_norm.get(n)
        if target and target not in doc_id_for_career:
            doc_id_for_career[target] = doc_id

    matched = 0
    updated = 0
    unmatched_docs: list[str] = []
    media: dict[str, dict[str, str]] = {}

    for c in careers:
        doc_id = doc_id_for_career.get(c.title)
        if not doc_id:
            continue
        matched += 1

        page_path = CAREERS_DIR / f"{c.slug}.html"
        if not page_path.exists():
            continue

        exported = export_doc_html(doc_id)
        cleaned, hero_src = clean_google_doc_html(exported, slug=c.slug)
        if not cleaned:
            continue

        section_map = split_doc_into_sections(cleaned)
        panels_html = build_doc_panels_html(section_map)

        existing = page_path.read_text(encoding="utf-8")
        # Prefer injecting into the dedicated container if present
        soup = BeautifulSoup(existing, "html.parser")
        doc_sections = soup.find(id="docSections")
        if doc_sections is not None:
            doc_sections.clear()
            if panels_html:
                doc_sections.append(BeautifulSoup(panels_html, "html.parser"))
            else:
                # fallback to a single panel
                new_html_str = inject_into_career_page(existing, c.title, cleaned)
                soup = BeautifulSoup(new_html_str, "html.parser")
        else:
            # fallback to old behavior
            new_html_str = inject_into_career_page(existing, c.title, cleaned)
            soup = BeautifulSoup(new_html_str, "html.parser")

        new_html = str(soup)
        page_path.write_text(new_html, encoding="utf-8")
        updated += 1
        if hero_src:
            media[c.slug] = {"heroImageSrc": hero_src, "docId": doc_id, "title": c.title}

    # Report docs that didn't match any career title (usually naming mismatch)
    career_titles = {c.title for c in careers}
    for t in sorted(title_to_id.keys()):
        mapped = explicit_aliases.get(t, t)
        if mapped not in career_titles and norm(mapped) not in career_by_norm:
            unmatched_docs.append(t)

    print(f"Docs found in Drive folder: {len(title_to_id)}")
    print(f"Careers matched by title: {matched}")
    print(f"Career pages updated: {updated}")
    if unmatched_docs:
        print("Docs with no matching career title:")
        for t in unmatched_docs:
            print(f" - {t}")

    # Write doc-media.js for landing-page cards
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    DOC_MEDIA_JS.write_text(
        "window.SHT_DOC_MEDIA = " + json.dumps(media, indent=2) + ";\n",
        encoding="utf-8",
    )
    print(f"Wrote doc media map: {DOC_MEDIA_JS} ({len(media)} careers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

