// core/report.mjs — read-only: EMITS the configured reality as JSON.
// The system knew how to COMPARE but not how to STATE reality: this closes that gap (a red-team fix).
// Uses: init seeds the markers with REAL counts (never from memory); audit (a)/(c) uses it as evidence.

import { loadConfig, validateWiring } from "./config.mjs";
import { loadAdapters } from "./adapters.mjs";
import { makeCtx } from "./check.mjs";

export async function main({ configPath }) {
  const root = process.cwd();
  const ctx = makeCtx(root);
  let cfg;
  try {
    cfg = loadConfig(configPath, root);
  } catch (e) {
    console.error(`❌ virgilio report: ${e.message}`);
    return 2;
  }
  const adapters = await loadAdapters(cfg.adapters, ctx);
  validateWiring(cfg, adapters);

  const out = { counts: [], guards: [] };
  for (const c of cfg.reality?.counts ?? []) {
    const r = await adapters[c.adapter].capability(c.capability, c.query);
    out.counts.push({ fact: c.fact, owner: c.owner, available: r.available, value: r.value, evidence: r.evidence, reason: r.reason });
  }
  for (const g of cfg.guards ?? []) {
    const r = await adapters[g.when.adapter].capability(g.when.capability, g.when.query);
    out.guards.push({ id: g.id, available: r.available, value: r.value, evidence: r.evidence, reason: r.reason });
  }
  console.log(JSON.stringify(out, null, 2));
  return 0;
}
