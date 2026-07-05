// forbiddenPhrases — a reality-coupled blocklist: phrases that turn FALSE the moment a fact changes,
// exempt in historical zones / behind an allow-marker / ~~struck-through~~ (via corpus.liveLine).
// BESPOKE and not delegable to Vale: coupled to a FACT (reason/since) + a historical-zone exemption
// anchored to git/headings. Re-evaluation happens in the audit §9 when the fact changes.

import { readFileSync } from "node:fs";
import { finding } from "../findings.mjs";

export async function run(cfg, adapters, corpus, ctx) {
  const findings = [];
  const compiled = (cfg.forbiddenPhrases ?? []).map((p) => ({
    re: new RegExp(p.pattern, p.flags ?? "i"), reason: p.reason ?? "", pat: p.pattern, since: p.since,
  }));
  if (!compiled.length) return { findings, skips: [] };

  for (const abs of corpus.mdFiles) {
    const rel = corpus.relOf(abs);
    readFileSync(abs, "utf8").split("\n").forEach((raw, i) => {
      const line = corpus.liveLine(rel, i + 1, raw);
      if (line == null) return;
      for (const p of compiled) {
        if (p.re.test(line)) {
          findings.push(finding({
            checkId: "forbiddenPhrase", file: rel, line: i + 1, claim: `/${p.pat}/`, reality: "stale phrase",
            message: `banned phrase /${p.pat}/ — ${p.reason}`, ruleRef: p.since ? `since ${p.since}` : "forbiddenPhrase",
          }));
        }
      }
    });
  }
  return { findings, skips: [] };
}
