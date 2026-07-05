// core/config.mjs — fail-fast boundary: loads the config, validates shape + WIRING BEFORE touching
// reality. Hand-rolled validation (zero-dep): not a full JSON Schema, just the required fields/types
// that matter. NO kind-matrix (cut): the one wiring invariant is "gate-legal tier" + capability exists.

import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

export function loadConfig(configPath, root) {
  const abs = resolve(root, configPath);
  if (!existsSync(abs)) fail(`config not found: ${configPath}`);
  let cfg;
  try {
    cfg = JSON.parse(readFileSync(abs, "utf8"));
  } catch (e) {
    fail(`config is not valid JSON (${configPath}): ${e.message}`);
  }
  validateShape(cfg);
  return cfg;
}

function validateShape(cfg) {
  for (const k of ["adapters", "docsGlobs"]) if (!(k in cfg)) fail(`missing required key: '${k}'`);
  mustArray(cfg.adapters, "adapters");
  mustArray(cfg.docsGlobs, "docsGlobs");
  if ("factKeys" in cfg) mustArray(cfg.factKeys, "factKeys");
  if ("statusDocs" in cfg) mustArray(cfg.statusDocs, "statusDocs");
  if ("statusVocabulary" in cfg) mustArray(cfg.statusVocabulary, "statusVocabulary");
  if ("historicalPaths" in cfg) mustArray(cfg.historicalPaths, "historicalPaths");
  if ("historicalSections" in cfg) {
    mustArray(cfg.historicalSections, "historicalSections");
    for (const s of cfg.historicalSections) {
      if (!s || typeof s.file !== "string") fail("historicalSections[].file is required (string)");
      if (typeof s.fromHeadingRegex !== "string" || !s.fromHeadingRegex.trim()) fail(`historicalSections['${s.file}'].fromHeadingRegex is required (non-empty regex) — an empty regex would open the entire file as historical (a false negative)`);
    }
  }
  if ("guards" in cfg) {
    mustArray(cfg.guards, "guards");
    for (const g of cfg.guards) {
      if (!g.id || !g.when || !g.forbidClaims) fail(`malformed guard (needs id/when/forbidClaims): ${JSON.stringify(g).slice(0, 90)}`);
      if (g.polarity && g.polarity !== "doc-behind") fail(`guard '${g.id}': in v0 only polarity 'doc-behind' is supported (doc-ahead is deferred to the audit §9)`);
      if (!g.when.adapter || !g.when.capability) fail(`guard '${g.id}': when.adapter/when.capability are required`);
    }
  }
  for (const c of cfg.reality?.counts ?? []) {
    if (!c.fact || !c.owner || !c.adapter || !c.capability) fail(`reality.counts: fact/owner/adapter/capability are required (${JSON.stringify(c).slice(0, 90)})`);
  }
}

// Wiring: every check that consumes an adapter must point to an EXISTING capability on a
// GATE-LEGAL tier (filesystem|git-ref). A gate wired to 'external' dies right here (probes belong in audit).
export function validateWiring(cfg, adapters) {
  const refs = [];
  for (const c of cfg.reality?.counts ?? []) refs.push({ where: `reality.counts[${c.fact}]`, adapter: c.adapter, capability: c.capability, gate: true });
  for (const g of cfg.guards ?? []) refs.push({ where: `guard[${g.id}].when`, adapter: g.when.adapter, capability: g.when.capability, gate: true });
  for (const p of cfg.audit?.probes ?? []) refs.push({ where: `audit.probes[${p.id}]`, adapter: p.adapter, capability: p.capability, gate: false });

  for (const r of refs) {
    const a = adapters[r.adapter];
    if (!a) fail(`${r.where}: adapter '${r.adapter}' not loaded — add it to config.adapters`);
    const meta = a.manifest.capabilities[r.capability];
    if (!meta) fail(`${r.where}: capability '${r.capability}' doesn't exist on adapter '${r.adapter}'`);
    if (r.gate && meta.tier === "external") {
      fail(`${r.where}: a GATE check cannot use a tier-'external' capability ('${r.adapter}.${r.capability}') — external probes belong only in audit.probes`);
    }
  }
}

function mustArray(v, name) {
  if (!Array.isArray(v)) fail(`'${name}' must be an array`);
}
function fail(msg) {
  const e = new Error(`invalid config: ${msg}`);
  e.isConfigError = true;
  throw e;
}
