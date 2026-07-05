// adapters/supabase.mjs — tier 'external' (AUDIT-ONLY, NEVER in the blocking gate).
// Generalizes the seed's check-column-leaks: proves that a sensitive column is RLS-denied (42501)
// on the REAL prod ref via PostgREST. url/anonKey come from the target repo's ENV (never hardcoded
// here → stack-agnostic + no secrets). The anon key is public but must NOT be committed: pass it via env.

import { existsSync } from "node:fs";
import { join } from "node:path";
import { reality, SKIP } from "../core/reality.mjs";

export const manifest = {
  id: "supabase",
  requiredIn: [],
  capabilities: { probeColumnDenied: { tier: "external" } },
};

export function detect(ctx) {
  const applies = existsSync(join(ctx.root, "supabase"));
  return { applies, evidence: applies ? "supabase/ folder present" : "no supabase/ folder" };
}

export function availability() {
  // The adapter is loadable; TRUE availability (creds+network) is decided by the capability (soft-skip).
  return reality({ available: true, value: true, tier: "external", evidence: "supabase adapter (probe on-demand)" });
}

export const capabilities = {
  // { urlEnv, keyEnv, table, columns } — creds from the target's ENV. Expected: an HTTP response with code 42501 = RLS-denied.
  async probeColumnDenied(query, ctx) {
    const url = ctx.env[query.urlEnv];
    const key = ctx.env[query.keyEnv];
    if (!url || !key) {
      return SKIP("external", `creds missing (${query.urlEnv}/${query.keyEnv} not set) → 'not verifiable', never 'verified'`);
    }
    const col = (query.columns ?? []).join(",") || "*";
    const endpoint = `${url.replace(/\/$/, "")}/rest/v1/${query.table}?select=${encodeURIComponent(col)}&limit=1`;
    try {
      const res = await fetch(endpoint, { headers: { apikey: key, Authorization: `Bearer ${key}` } });
      const body = await res.text();
      const has42501 = /"code"\s*:\s*"42501"/.test(body);
      const ev = (t) => `GET ${query.table}?select=${col} → HTTP ${res.status} ${t}`;
      // The AUTHORITATIVE signal for "column denied by RLS/grant" is code 42501.
      if (has42501) return reality({ available: true, value: true, tier: "external", evidence: ev("(42501 / denied)") });
      // 401 = the anon key is invalid/expired: auth failed, NOT a column denial → inconclusive.
      if (res.status === 401) return SKIP("external", `HTTP 401: anon key invalid/expired (${query.keyEnv}) → RLS not assertable, never 'verified'`);
      // 403 without 42501: a non-column denial (e.g. row-level RLS) → inconclusive.
      if (res.status === 403) return SKIP("external", "HTTP 403 without 42501: a non-column denial, inconclusive");
      if (res.status === 200) {
        const t = body.trim();
        const hasRows = t !== "" && t !== "[]" && t !== "null";
        // 200 with rows = the column is readable ⇒ LEAK. 200 with [] = row-RLS/empty table ⇒ inconclusive.
        if (hasRows) return reality({ available: true, value: false, tier: "external", evidence: ev("with rows (READABLE — leak!)") });
        return SKIP("external", "HTTP 200 with an empty body ([]): row-RLS or an empty table, column leak not assertable");
      }
      return SKIP("external", `HTTP ${res.status}: unexpected response, inconclusive`);
    } catch (e) {
      return SKIP("external", `network probe failed: ${String(e?.message || e).slice(0, 140)}`);
    }
  },
};
