// factDedup — per-fact SSOT: every fact:KEY lives in exactly ONE owner file + a key declared in factKeys.
// Pure corpus structure (no adapter involved). Case-sensitive: illustrative KEY/CHIAVE don't collide.

import { readFileSync } from "node:fs";
import { finding } from "../findings.mjs";

const MARKER = /<!--fact:([a-z0-9-]+)-->/g;

export async function run(cfg, adapters, corpus, ctx) {
  const findings = [];
  const declared = new Set(cfg.factKeys ?? []);
  const keyFiles = {}; // key -> Set(rel)

  for (const abs of corpus.mdFiles) {
    const rel = corpus.relOf(abs);
    readFileSync(abs, "utf8").split("\n").forEach((raw, i) => {
      if (corpus.isHistoricalLine(rel, i + 1) || corpus.allowMarkers.some((mk) => raw.includes(mk))) return;
      const re = new RegExp(MARKER.source, "g");
      let m;
      while ((m = re.exec(raw))) {
        const key = m[1];
        (keyFiles[key] ??= new Set()).add(rel);
        if (declared.size && !declared.has(key)) {
          findings.push(finding({
            checkId: "factDedup", file: rel, line: i + 1, claim: `fact:${key}`, reality: "key not declared",
            message: `fact-marker key not declared: '${key}' → declare it in factKeys or remove it`, ruleRef: "factDedup",
          }));
        }
      }
    });
  }

  for (const [key, set] of Object.entries(keyFiles)) {
    if (set.size > 1) {
      findings.push(finding({
        checkId: "factDedup", claim: `fact:${key}`, reality: `in ${set.size} files`,
        message: `fact:${key} appears in ${set.size} files (${[...set].join(", ")}) — a fact lives in exactly ONE owner; elsewhere, LINK to it (per-fact SSOT)`,
        ruleRef: "factDedup",
      }));
    }
  }
  return { findings, skips: [] };
}
