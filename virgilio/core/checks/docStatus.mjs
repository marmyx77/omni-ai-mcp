// docStatus — declared plan/status docs carry a machine-readable line
//   <!-- doc-status: <closed vocabulary> | updated: YYYY-MM-DD -->
// Status prose drifts; only the exit code holds up. Pure form compliance (no external Reality).

import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { finding } from "../findings.mjs";

const DOC_STATUS = /<!--\s*doc-status:\s*([A-Za-z0-9-]+)\s*\|\s*updated:\s*(\d{4}-\d{2}-\d{2})\s*-->/;

export async function run(cfg, adapters, corpus, ctx) {
  const findings = [];
  const vocab = new Set(cfg.statusVocabulary ?? []);

  for (const rel of cfg.statusDocs ?? []) {
    const abs = join(ctx.root, rel);
    if (!existsSync(abs)) {
      findings.push(finding({ checkId: "docStatus", file: rel, claim: "declared status doc", reality: "file missing", message: `statusDocs declares '${rel}' but the file doesn't exist`, ruleRef: "docStatus" }));
      continue;
    }
    const m = readFileSync(abs, "utf8").match(DOC_STATUS);
    if (!m) {
      findings.push(finding({ checkId: "docStatus", file: rel, claim: "doc-status line", reality: "missing", message: `missing the line '<!-- doc-status: <vocab> | updated: YYYY-MM-DD -->'`, ruleRef: "docStatus" }));
      continue;
    }
    if (vocab.size && !vocab.has(m[1])) {
      findings.push(finding({ checkId: "docStatus", file: rel, claim: `doc-status: ${m[1]}`, reality: "outside the vocabulary", message: `doc-status '${m[1]}' is outside the closed vocabulary [${[...vocab].join(", ")}]`, ruleRef: "docStatus" }));
    }
  }
  return { findings, skips: [] };
}
