/* SheTech Pathways: landing + QR utilities */

const STORAGE_KEY = "shetech_pathways_base_url";
const LEGACY_QR_HELP_COPY = "Set your public site URL on the landing page to generate scannable QR codes.";
const UPDATED_QR_HELP_COPY = "Host this site (so QR codes open the correct pages when scanned).";

function getCareersData() {
  const data = window.SHT_CAREERS;
  if (!Array.isArray(data)) return [];
  return data.filter((x) => x && typeof x.title === "string" && typeof x.slug === "string");
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function chooseIndefiniteArticle(title) {
  const t = String(title || "").trim();
  if (!t) return "a";

  // Extract first token (letters/digits).
  const first = (t.match(/^[A-Za-z0-9]+/) || [""])[0];
  const upper = first.toUpperCase();

  // Common STEM acronyms pronounced with a leading "you" sound -> "a"
  const aAcronyms = new Set(["UX", "UI", "EU"]);
  if (aAcronyms.has(upper)) return "a";

  // Acronyms often spoken as letters: choose based on first-letter sound.
  // Letters with vowel sound when spoken: A, E, F, H, I, L, M, N, O, R, S, X
  const vowelSoundLetters = new Set(["A", "E", "F", "H", "I", "L", "M", "N", "O", "R", "S", "X"]);
  const isAcronym = /^[A-Z0-9]+$/.test(first) && /[A-Z]/.test(first) && first.length <= 4;
  if (isAcronym) return vowelSoundLetters.has(upper[0]) ? "an" : "a";

  // Words: simple vowel check.
  return /^[AEIOU]/i.test(first) ? "an" : "a";
}

function normalizeBaseUrl(input) {
  const value = (input || "").trim().replace(/\/+$/, "");
  if (!value) return "";
  try {
    const url = new URL(value);
    // Preserve subpaths for hosting under a folder (e.g. GitHub Pages /repo).
    const path = url.pathname.replace(/\/+$/, "");
    return url.origin + (path && path !== "/" ? path : "");
  } catch {
    return "";
  }
}

function inferBaseUrl() {
  // If hosted (http/https), use origin; if opened via file://, there is no reliable public base URL.
  const origin = window.location.origin;
  if (!origin || origin === "null") return "";
  try {
    // Use the current directory as base so subfolder hosting works.
    const base = new URL("./", window.location.href);
    const path = base.pathname.replace(/\/+$/, "");
    return base.origin + (path && path !== "/" ? path : "");
  } catch {
    return origin;
  }
}

function getBaseUrl() {
  const saved = normalizeBaseUrl(localStorage.getItem(STORAGE_KEY) || "");
  if (saved) return saved;
  return inferBaseUrl();
}

function setBaseUrl(value) {
  const normalized = normalizeBaseUrl(value);
  if (normalized) localStorage.setItem(STORAGE_KEY, normalized);
  else localStorage.removeItem(STORAGE_KEY);
  return normalized;
}

function buildAbsoluteUrl(baseUrl, path) {
  try {
    // If path is already absolute, preserve it.
    const maybe = new URL(path);
    return maybe.toString();
  } catch {
    // Continue.
  }

  if (!baseUrl) return "";
  try {
    return new URL(path, baseUrl + "/").toString();
  } catch {
    return "";
  }
}

function qrImageUrlFor(targetUrl) {
  // Uses a public QR image generator. If you need offline QR generation, we can swap this.
  const encoded = encodeURIComponent(targetUrl);
  return `https://api.qrserver.com/v1/create-qr-code/?size=180x180&margin=12&data=${encoded}`;
}

function unsplashSourceUrl(query) {
  // Placeholder images. Replace with local photos later if desired.
  const q = (query || "").trim();
  const safe = q ? encodeURI(q) : "woman,stem";
  return `https://source.unsplash.com/1200x800/?${safe}`;
}

function getDocHeroImageSrc(slug) {
  try {
    const map = window.SHT_DOC_MEDIA;
    if (!map || typeof map !== "object") return "";
    const entry = map[slug];
    const src = entry && typeof entry.heroImageSrc === "string" ? entry.heroImageSrc : "";
    return src || "";
  } catch {
    return "";
  }
}

function wireCareerHeroImages() {
  const heroWrap = document.querySelector("[data-career-hero][data-slug]");
  if (!heroWrap) return;
  const slug = heroWrap.getAttribute("data-slug") || "";
  const img = heroWrap.querySelector("img");
  if (!slug || !img) return;

  const src = getDocHeroImageSrc(slug);
  if (!src) return;

  // On detail pages we're typically in /careers/, so prefix root-relative "./" paths.
  const resolved = src.startsWith("./") ? `../${src.slice(2)}` : src;
  img.src = resolved;
  heroWrap.hidden = false;
}

function listItems(items, maxItems) {
  const arr = Array.isArray(items) ? items.filter(Boolean) : [];
  const slice = typeof maxItems === "number" ? arr.slice(0, maxItems) : arr;
  if (slice.length === 0) return `<li class="muted">(Add items)</li>`;
  return slice.map((x) => `<li>${escapeHtml(x)}</li>`).join("");
}

function getOneLineDescription(career) {
  const custom = career && typeof career.description === "string" ? career.description.trim() : "";
  if (custom) return custom;
  const title = career && typeof career.title === "string" ? career.title.trim() : "STEM career";
  return `Learn what a ${title} does and explore the pathway to get there.`;
}

function renderCareersGrid() {
  const grid = document.getElementById("careerGrid");
  if (!grid || grid.getAttribute("data-render-careers") !== "true") return;

  const careers = getCareersData().slice().sort((a, b) => {
    const ta = String(a?.title || "").toLocaleLowerCase();
    const tb = String(b?.title || "").toLocaleLowerCase();
    return ta.localeCompare(tb, undefined, { numeric: true, sensitivity: "base" });
  });
  if (careers.length === 0) return;

  grid.innerHTML = careers
    .map((c) => {
      const title = c.title || "";
      const slug = c.slug || "";
      const href = `./careers/${encodeURIComponent(slug)}.html`;
      const qrPath = `./careers/${slug}.html`;
      const imgQuery = c.imageQuery || "woman,stem";
      const imgAlt = `Photo representing a woman in the ${title} career`;
      const desc = getOneLineDescription(c);
      const article = chooseIndefiniteArticle(title);
      const docHero = getDocHeroImageSrc(slug);
      const imgSrc = docHero || unsplashSourceUrl(imgQuery);

      return `
<article class="poster-card" data-career data-category="${escapeHtml(c.category || "technology")}" data-title="${escapeHtml(title)}">
  <div class="poster-head">
    <div class="poster-head-small">Launch Your Future as ${article === "an" ? "an" : "a"}</div>
    <h3 class="poster-head-title">${escapeHtml(title)}</h3>
  </div>

  <div class="poster-photo">
    <img class="poster-photo-img" src="${escapeHtml(imgSrc)}" alt="${escapeHtml(imgAlt)}" loading="lazy" decoding="async" />
  </div>

  <p class="poster-desc">${escapeHtml(desc)}</p>

  <div class="poster-bottom">
    <div class="poster-qr">
      <img alt="QR code for ${escapeHtml(title)} pathway" width="180" height="180" data-qr data-path="${escapeHtml(qrPath)}" />
    </div>
    <div class="poster-scan">
      <div class="poster-actions">
        <a class="poster-open" href="${href}">Open pathway</a>
        <button class="poster-copy" type="button" data-copy-link data-path="${escapeHtml(qrPath)}">Copy link</button>
      </div>
    </div>
    <img class="poster-logo" src="./Design/shetech%20logo%20fuchsia%20(1).png" alt="SheTech" loading="lazy" />
  </div>
</article>`;
    })
    .join("\n");
}

function renderQrSheet() {
  const grid = document.getElementById("qrSheetGrid");
  if (!grid || grid.getAttribute("data-render-qr-sheet") !== "true") return;

  const careers = getCareersData();
  if (careers.length === 0) return;

  grid.innerHTML = careers
    .map((c) => {
      const title = c.title || "";
      const slug = c.slug || "";
      const href = `./careers/${encodeURIComponent(slug)}.html`;
      const qrPath = `./careers/${slug}.html`;
      return `
<div class="qr-sheet-item">
  <div class="qr-sheet-title">${escapeHtml(title)}</div>
  <img class="qr-sheet-qr" alt="QR code for ${escapeHtml(title)} pathway" width="220" height="220" data-qr data-path="${escapeHtml(qrPath)}" />
  <a class="qr-sheet-open no-print" href="${href}">Open</a>
</div>`;
    })
    .join("\n");
}

function updateQrImages() {
  const baseUrl = getBaseUrl();
  const imgs = document.querySelectorAll("[data-qr]");
  imgs.forEach((img) => {
    const path = img.getAttribute("data-path") || "";
    const target = buildAbsoluteUrl(baseUrl, path);
    if (!target) {
      img.removeAttribute("src");
      img.setAttribute(
        "alt",
        (img.getAttribute("alt") || "QR code") +
          " (host this site to generate a scannable QR code)"
      );
      img.style.background = "rgba(255,255,255,.10)";
      img.style.padding = "16px";
      return;
    }

    img.style.background = "white";
    img.style.padding = "10px";
    img.src = qrImageUrlFor(target);
  });
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

function updateLegacyQrHelpCopy() {
  const nodes = document.querySelectorAll("p");
  nodes.forEach((p) => {
    if ((p.textContent || "").trim() === LEGACY_QR_HELP_COPY) {
      p.textContent = UPDATED_QR_HELP_COPY;
    }
  });
}

function wireCopyLinks() {
  document.addEventListener("click", async (e) => {
    const btn = e.target && e.target.closest && e.target.closest("[data-copy-link]");
    if (!btn) return;

    const baseUrl = getBaseUrl();
    const path = btn.getAttribute("data-path") || "";
    const target = buildAbsoluteUrl(baseUrl, path);
    const copyValue = target || path;

    const ok = await copyText(copyValue);
    const prev = btn.textContent;
    btn.textContent = ok ? "Copied!" : "Copy failed";
    btn.setAttribute("aria-live", "polite");
    setTimeout(() => (btn.textContent = prev), 1100);
  });
}

function wireFilters() {
  const search = document.getElementById("careerSearch");
  const category = document.getElementById("careerCategory");
  const noResults = document.getElementById("noResults");
  const items = Array.from(document.querySelectorAll("[data-career]"));

  if (!search || !category || items.length === 0) return;

  function apply() {
    const q = (search.value || "").trim().toLowerCase();
    const cat = category.value || "all";
    let shown = 0;

    items.forEach((el) => {
      const title = (el.getAttribute("data-title") || "").toLowerCase();
      const elCat = (el.getAttribute("data-category") || "").toLowerCase();
      const matchesQ = !q || title.includes(q);
      const matchesC = cat === "all" || elCat === cat;
      const visible = matchesQ && matchesC;
      el.style.display = visible ? "" : "none";
      if (visible) shown += 1;
    });

    if (noResults) noResults.hidden = shown !== 0;
  }

  search.addEventListener("input", apply);
  category.addEventListener("change", apply);
  apply();
}

function wireBaseUrlConfig() {
  const input = document.getElementById("siteBaseUrl");
  const save = document.getElementById("saveBaseUrl");
  const reset = document.getElementById("resetBaseUrl");
  const status = document.getElementById("baseUrlStatus");
  if (!input || !save || !reset || !status) return;

  const current = getBaseUrl();
  input.value = localStorage.getItem(STORAGE_KEY) ? current : "";

  function renderStatus() {
    const active = getBaseUrl();
    const saved = localStorage.getItem(STORAGE_KEY) ? "Saved" : "Auto";
    if (!active) {
      status.textContent =
        "QR codes will appear after you set a public site URL (use this when the site is hosted).";
      return;
    }
    status.textContent = `${saved} base URL: ${active}`;
  }

  save.addEventListener("click", () => {
    const normalized = setBaseUrl(input.value);
    if (!normalized) {
      status.textContent = "That doesn’t look like a valid URL. Example: https://yourdomain.com";
      return;
    }
    renderStatus();
    updateQrImages();
  });

  reset.addEventListener("click", () => {
    localStorage.removeItem(STORAGE_KEY);
    input.value = "";
    renderStatus();
    updateQrImages();
  });

  renderStatus();
}

function init() {
  // Render Excel-driven UI (only if the page opts in via data-render-* attributes).
  renderCareersGrid();
  renderQrSheet();

  wireCareerHeroImages();
  updateLegacyQrHelpCopy();

  wireBaseUrlConfig();
  wireFilters();
  wireCopyLinks();
  updateQrImages();
}

document.addEventListener("DOMContentLoaded", init);

