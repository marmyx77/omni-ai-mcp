// counts — the <!--fact:KEY-->N<!--/fact--> marker in the owner doc vs. an adapter's Reality<number>.
// Generalizes the seed's 3 hardcoded lines (migrations/edge-fn/le-*) into a config-driven check.

import { readFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { finding, skip } from "../findings.mjs";

export async function run(cfg, adapters, corpus, ctx) {
  const findings = [], skips = [];
  for (const c of cfg.reality?.counts ?? []) {
    const ownerAbs = join(ctx.root, c.owner);
    if (!existsSync(ownerAbs)) {
      // owner renamed/missing ⇒ an explicit Finding, NEVER a crash (a red-team fix)
      findings.push(finding({
        checkId: "counts", file: c.owner, claim: `owner of fact:${c.fact}`, reality: "file doesn't exist",
        message: `owner doc '${c.owner}' for fact:${c.fact} doesn't exist (the count's single source)`, ruleRef: "counts",
      }));
      continue;
    }
    const r = await adapters[c.adapter].capability(c.capability, c.query);
    if (!r.available) { skips.push(skip({ checkId: `counts:${c.fact}`, tier: r.tier, reason: r.reason })); continue; }

    const text = readFileSync(ownerAbs, "utf8");
    const m = text.match(new RegExp(`<!--fact:${escapeRe(c.fact)}-->(\\d+)<!--/fact-->`));
    if (!m) {
      findings.push(finding({
        checkId: "counts", file: c.owner, claim: `fact:${c.fact} marker`, reality: String(r.value),
        message: `marker <!--fact:${c.fact}--> is MISSING from the owner`, evidence: r.evidence, ruleRef: "counts",
      }));
      continue;
    }
    if (Number(m[1]) !== r.value) {
      findings.push(finding({
        checkId: "counts", file: c.owner, claim: `fact:${c.fact}=${m[1]}`, reality: String(r.value),
        message: `fact:${c.fact} declares ${m[1]} but reality is ${r.value} → update the marker (SSOT)`,
        evidence: r.evidence, ruleRef: "counts",
      }));
    }
  }
  return { findings, skips };
}

const escapeRe = (s) => String(s).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
