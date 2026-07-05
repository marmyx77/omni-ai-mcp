// links — relative INTRA-repo markdown links that must resolve. Scoped to ROOT: a target outside
// ROOT (a sibling repo) exists locally but NOT in CI ⇒ skipped (never a CI-vs-local false positive).
// Markdown-aware just enough to not redden on valid docs: drops the link's title, skips ```/~~~
// fenced blocks and `inline-code` spans, respects historical zones/allow-marker/~~struck-through~~
// (liveLine), and ignores non-path schemes (http/mailto/tel/data/#). EXTERNAL reachability → lychee (non-blocking).

import { readFileSync, existsSync } from "node:fs";
import { resolve, dirname, relative } from "node:path";
import { finding } from "../findings.mjs";

const LINK = /\[[^\]]*\]\(([^)]+)\)/g;

export async function run(cfg, adapters, corpus, ctx) {
  if (cfg.links?.checkRelativeIntraRepo === false) return { findings: [], skips: [] };
  const findings = [];

  for (const abs of corpus.mdFiles) {
    const rel = corpus.relOf(abs);
    if (corpus.isHistoricalFile(rel)) continue; // immutable snapshots: we don't rewrite them for a link
    let inFence = false;
    readFileSync(abs, "utf8").split("\n").forEach((raw, i) => {
      if (/^\s*(```|~~~)/.test(raw)) { inFence = !inFence; return; } // toggle code block
      if (inFence) return;
      const line = corpus.liveLine(rel, i + 1, raw);
      if (line == null) return;
      const noCode = line.replace(/`[^`]*`/g, ""); // links inside `inline-code` are examples, not real links
      const re = new RegExp(LINK.source, "g");
      let m;
      while ((m = re.exec(noCode))) {
        let t = m[1].trim().split(/\s+/)[0]; // drop the optional title: [x](./p.md "Title")
        if (/^(https?:|mailto:|tel:|data:|ftp:|#)/i.test(t)) continue;
        t = t.split("#")[0].split("?")[0].trim();
        if (!t || /^\.{3,}$/.test(t)) continue; // empty or an "..." ellipsis
        const target = resolve(dirname(abs), t);
        if (relative(ctx.root, target).startsWith("..")) continue; // outside ROOT = another repo
        if (!existsSync(target)) {
          findings.push(finding({
            checkId: "links", file: rel, line: i + 1, claim: `link → ${m[1]}`, reality: "target doesn't exist",
            message: `broken internal link → ${m[1]} (target doesn't exist)`, ruleRef: "links",
          }));
        }
      }
    });
  }
  return { findings, skips: [] };
}
