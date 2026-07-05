// guards — POLARITY-aware staleness tied to git-ref. In v0 only 'doc-behind' (the doc is lagging
// behind reality: it says "untracked"/"not in prod" while the artifact IS tracked / on the prod-ref).
// The premise (when) is re-evaluated via the adapter: if reality isn't observable ⇒ a loud Skip,
// never a false negative. If the premise's path is no longer tracked while true was expected ⇒ warn
// (config-staleness: the guard is silently dying).

import { readFileSync } from "node:fs";
import { finding, skip } from "../findings.mjs";

export async function run(cfg, adapters, corpus, ctx) {
  const findings = [], skips = [];
  for (const g of cfg.guards ?? []) {
    const r = await adapters[g.when.adapter].capability(g.when.capability, g.when.query);
    if (!r.available) { skips.push(skip({ checkId: `guard:${g.id}`, tier: r.tier, reason: r.reason })); continue; }
    if (typeof r.value !== "boolean") {
      // a non-boolean capability (resolveRef→string, logSince→array) used as a premise would leave
      // the guard silently inert (r.value !== true always) → a loud Skip, never a false negative.
      skips.push(skip({ checkId: `guard:${g.id}`, tier: r.tier, reason: `non-boolean premise: capability '${g.when.capability}' returns ${Array.isArray(r.value) ? "array" : typeof r.value} → unsuitable for a guard (use isTracked/existsOnRef)` }));
      continue;
    }

    const expected = g.when.equals ?? true;
    if (r.value !== expected) {
      // the premise is NOT satisfied: no claim to block. But if true was expected and reality is
      // false, the guard is potentially DEAD (renamed path) → a config-staleness warning.
      if (expected === true && r.value === false) {
        skips.push(skip({ checkId: `guard:${g.id}`, tier: r.tier, reason: `the 'when' premise is now FALSE (${r.evidence}) — guard inactive: renamed path, or stale config?` }));
      }
      continue;
    }

    const patterns = g.forbidClaims.map((p) => ({ re: new RegExp(p.pattern, p.flags ?? "i"), label: p.label ?? p.pattern }));
    const scopeRe = g.scope?.contextPattern ? new RegExp(g.scope.contextPattern, "i") : null;

    for (const abs of corpus.mdFiles) {
      const rel = corpus.relOf(abs);
      readFileSync(abs, "utf8").split("\n").forEach((raw, i) => {
        const line = corpus.liveLine(rel, i + 1, raw);
        if (line == null) return;
        if (scopeRe && !scopeRe.test(line)) return;
        for (const { re, label } of patterns) {
          if (re.test(line)) {
            findings.push(finding({
              checkId: `guard:${g.id}`, file: rel, line: i + 1, claim: `"${label}"`, reality: r.evidence,
              message: g.message ? `claims "${label}" but ${g.message}` : `claims "${label}" but git reality contradicts it`,
              evidence: r.evidence, ruleRef: `guard:${g.id}`,
            }));
            break;
          }
        }
      });
    }
  }
  return { findings, skips };
}
