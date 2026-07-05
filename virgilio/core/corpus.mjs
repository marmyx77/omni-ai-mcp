// core/corpus.mjs — markdown inventory + historical zones + liveLine.
//
// liveLine is the anti-false-positive primitive shared by the prose checks (guards, forbiddenPhrases):
// a line is NOT a live claim if (a) it's in a historical zone (an archived path, or an append-only
// section like "Handoff log" that records what was true back then), (b) it carries an allow-marker
// (documents the rule by citing the banned phrases), or (c) it's entirely ~~struck-through~~ (a
// resolved claim). This way the rulebook that DOCUMENTS the gate doesn't auto-fail.

import { readFileSync, readdirSync, existsSync, statSync } from "node:fs";
import { join, relative } from "node:path";

// allowMarker as a LIST. The CORE's default is only virgilio's own marker (stack-agnostic): a repo
// already governed under a different marker (e.g. the awevents seed's 'docs-check:...') adds it to
// its own config (cfg.allowMarker) — that backward-compat lives in the project that needs it, not in
// the core. SUBSTRING match.
const DEFAULT_ALLOW_MARKERS = ["virgilio:allow-status-mention"];

function normalizeAllowMarkers(v) {
  const extra = v == null ? [] : Array.isArray(v) ? v : [v];
  return Array.from(new Set([...extra, ...DEFAULT_ALLOW_MARKERS]));
}

const norm = (p) => p.split("\\").join("/");

export function buildCorpus(cfg, root) {
  const globs = cfg.docsGlobs ?? ["docs/**/*.md", "CLAUDE.md", "README.md"];
  const mdFiles = collectMarkdown(root, globs);
  const relOf = (abs) => norm(relative(root, abs));
  const allowMarkers = normalizeAllowMarkers(cfg.allowMarker);

  const historicalPaths = (cfg.historicalPaths ?? []).map(norm);
  const historicalStart = {}; // rel -> lineNo (1-based) from which the section becomes historical
  for (const sec of cfg.historicalSections ?? []) {
    const rel = norm(sec.file);
    const p = join(root, sec.file);
    if (!existsSync(p) || !sec.fromHeadingRegex) continue; // no regex → don't open any zone
    const re = new RegExp(sec.fromHeadingRegex);
    // Anchored to a HEADING line (starts with #): a match on a TOC/prose line must NOT open the
    // historical zone too early (which would suppress live claims further down → false negative).
    const idx = readFileSync(p, "utf8").split("\n").findIndex((l) => /^#{1,6}\s/.test(l) && re.test(l));
    if (idx >= 0) historicalStart[rel] = idx + 1;
  }

  const isHistoricalFile = (rel) => historicalPaths.some((h) => rel.startsWith(h));
  const isHistoricalLine = (rel, lineNo) =>
    isHistoricalFile(rel) || (historicalStart[rel] != null && lineNo >= historicalStart[rel]);

  const liveLine = (rel, lineNo, raw) => {
    if (isHistoricalLine(rel, lineNo)) return null;
    if (allowMarkers.some((m) => raw.includes(m))) return null;
    return raw.replace(/~~[^~]*~~/g, ""); // strikethrough = resolved → stripped
  };

  return { mdFiles, relOf, isHistoricalFile, isHistoricalLine, liveLine, allowMarkers };
}

// Walk supporting "<dir>/**/*.md" (recursive), "<dir>/*.md" (top level ONLY), and literal paths.
// Skips node_modules/.git/dotdirs: a root glob ('**/*.md') must not drag in vendored markdown.
function collectMarkdown(root, globs) {
  const out = new Set();
  for (const g of globs) {
    if (g.includes("*")) {
      const recursive = g.includes("**");
      const base = g.split("*")[0].replace(/\/+$/, "");
      const dir = base ? join(root, base) : root;
      if (existsSync(dir) && statSync(dir).isDirectory()) walkMd(dir, out, recursive);
    } else {
      const p = join(root, g);
      if (existsSync(p) && p.endsWith(".md")) out.add(p);
    }
  }
  return [...out];
}

function walkMd(dir, out, recursive) {
  for (const d of readdirSync(dir, { withFileTypes: true })) {
    const p = join(dir, d.name);
    if (d.isDirectory()) {
      if (recursive && d.name !== "node_modules" && d.name !== ".git" && !d.name.startsWith(".")) walkMd(p, out, recursive);
    } else if (d.name.endsWith(".md")) out.add(p);
  }
}
