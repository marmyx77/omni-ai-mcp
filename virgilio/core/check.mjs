// core/check.mjs — the BLOCKING gate. A deterministic, read-only pipeline, ZERO network (only
// filesystem + git-ref). Exports runChecks() (in-process, for bite) and main() (for the CLI).

import { execSync, execFileSync } from "node:child_process";
import { loadConfig, validateWiring } from "./config.mjs";
import { loadAdapters } from "./adapters.mjs";
import { buildCorpus } from "./corpus.mjs";
import { formatFinding, formatSkip } from "./findings.mjs";

import * as counts from "./checks/counts.mjs";
import * as factDedup from "./checks/factDedup.mjs";
import * as guards from "./checks/guards.mjs";
import * as forbiddenPhrases from "./checks/forbiddenPhrases.mjs";
import * as links from "./checks/links.mjs";
import * as docStatus from "./checks/docStatus.mjs";

const CHECKS = { counts, factDedup, guards, forbiddenPhrases, links, docStatus };

// ctx.exec NEVER throws: it converts the error into {code,stdout,stderr}. Adapters turn that into a Reality.
export function makeCtx(root) {
  const isCI = !!(process.env.CI && process.env.CI !== "false");
  return {
    root,
    env: process.env,
    envName: isCI ? "ci" : "local",
    isCI,
    log: (...a) => console.error(...a),
    exec(cmd, opts = {}) {
      try {
        const stdout = execSync(cmd, { cwd: opts.cwd ?? root, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
        return { code: 0, stdout, stderr: "" };
      } catch (e) {
        return { code: e.status ?? 1, stdout: e.stdout?.toString() ?? "", stderr: e.stderr?.toString() ?? String(e.message || "") };
      }
    },
    // execFile: no shell → no quoting, argv-based (portable on Windows, no injection).
    execFile(file, args, opts = {}) {
      try {
        const stdout = execFileSync(file, args, { cwd: opts.cwd ?? root, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
        return { code: 0, stdout, stderr: "" };
      } catch (e) {
        return { code: e.status ?? 1, stdout: e.stdout?.toString() ?? "", stderr: e.stderr?.toString() ?? String(e.message || "") };
      }
    },
  };
}

// Runs every class against (root, cfg). No process.exit: bite can call this against hermetic fixtures.
export async function runChecks({ root, cfg, ctx }) {
  ctx = ctx ?? makeCtx(root);
  const adapters = await loadAdapters(cfg.adapters, ctx);
  validateWiring(cfg, adapters);
  const corpus = buildCorpus(cfg, root);
  const findings = [], skips = [];
  for (const mod of Object.values(CHECKS)) {
    const res = await mod.run(cfg, adapters, corpus, ctx);
    findings.push(...(res.findings ?? []));
    skips.push(...(res.skips ?? []));
  }
  return { findings, skips, adapters, corpus };
}

export async function main({ configPath }) {
  const root = process.cwd();
  let out;
  try {
    const ctx = makeCtx(root);
    const cfg = loadConfig(configPath, root);
    out = await runChecks({ root, cfg, ctx });
  } catch (e) {
    console.error(`❌ virgilio: ${e.isConfigError || e.isEnvError ? e.message : e.stack || e.message}`);
    return 2;
  }
  const { findings, skips } = out;

  // Skips are ALWAYS printed and kept distinct: a green-with-skip is NOT a full green.
  for (const s of skips) console.error(formatSkip(s));

  if (findings.length) {
    console.error(`\n❌ virgilio: ${findings.length} doc↔reality mismatches:`);
    for (const f of findings) console.error("   - " + formatFinding(f));
    console.error("\nRules/config: DOC_GOVERNANCE.md · virgilio.config.json. Every finding carries the evidence (command) to verify it by hand.");
    return 1;
  }
  const note = skips.length ? ` · ${skips.length} SKIP (reality classes NOT observed here — see above, green-with-skip ≠ full-green)` : "";
  console.log(`✅ virgilio OK — ${Object.keys(CHECKS).length} classes green${note}.`);
  return 0;
}
