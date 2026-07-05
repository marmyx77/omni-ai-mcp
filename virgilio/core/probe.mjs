// core/probe.mjs — AUDIT-only. The ONLY place that invokes the 'external' tier (network/creds).
// Emits Reality JSON for the agent. Soft-skips when creds are missing (available:false + reason) ⇒
// the agent writes 'not verifiable', NEVER 'verified'. NEVER in the blocking gate (guaranteed by the
// boundary check in config.mjs).

import { loadConfig } from "./config.mjs";
import { loadAdapters } from "./adapters.mjs";
import { makeCtx } from "./check.mjs";

export async function main({ configPath }) {
  const root = process.cwd();
  const ctx = makeCtx(root);
  let cfg;
  try {
    cfg = loadConfig(configPath, root);
  } catch (e) {
    console.error(`❌ virgilio probe: ${e.message}`);
    return 2;
  }
  const adapters = await loadAdapters(cfg.adapters, ctx);

  const results = [];
  for (const p of cfg.audit?.probes ?? []) {
    const a = adapters[p.adapter];
    if (!a) { results.push({ id: p.id, available: false, reason: `adapter '${p.adapter}' not in config.adapters` }); continue; }
    const r = await a.capability(p.capability, p.query);
    results.push({ id: p.id, adapter: p.adapter, available: r.available, value: r.value, tier: r.tier, evidence: r.evidence, reason: r.reason });
  }
  console.log(JSON.stringify(results, null, 2));
  return 0;
}
