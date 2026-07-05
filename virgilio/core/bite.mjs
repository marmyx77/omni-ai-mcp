// core/bite.mjs — PROVE-IT-BITES: the meta-check for correctness. Every check class gets
// mutation-tested against a HERMETIC fixture (never the real repo): it applies a known violation and
// ASSERTS that the gate turns red (findings>0), plus the NEGATIVES (clean / historical zone /
// allow-marker / ~~struck-through~~ must NOT turn red). A check that never bites = a permanent false
// negative ⇒ the bite fails.
//
// KEY FIX (red-team): guards depend on GIT REALITY, not on the file's content. A plain 'copy' without
// .git would make them degrade to Skip (a false pass). So the git fixtures are hermetic: `git init` +
// a commit of the tracked path + `git update-ref refs/remotes/origin/main <sha>`, so isTracked/existsOnRef
// see the expected reality regardless of the environment's fetch state.

import { mkdtempSync, writeFileSync, mkdirSync, rmSync, readFileSync, readdirSync, existsSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { execSync } from "node:child_process";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { runChecks, makeCtx } from "./check.mjs";

const w = (dir, rel, content) => {
  const p = join(dir, rel);
  mkdirSync(dirname(p), { recursive: true });
  writeFileSync(p, content);
};
const sh = (dir, cmd) => execSync(cmd, { cwd: dir, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
function gitHermetic(dir, originMain = true) {
  sh(dir, "git init -q");
  sh(dir, "git config user.email bite@virgilio.test");
  sh(dir, "git config user.name bite");
  sh(dir, "git add -A");
  sh(dir, "git commit -q -m fixture --no-gpg-sign");
  if (originMain) sh(dir, `git update-ref refs/remotes/origin/main ${sh(dir, "git rev-parse HEAD").trim()}`);
}

// Each fixture: build(dir)->cfg (writes the files, returns the config) + expect.
const FIXTURES = [
  // ── counts ──
  { id: "counts-drift", needsGit: false, expect: { finding: true, checkId: "counts" },
    build(dir) {
      for (const f of ["a", "b", "c"]) w(dir, `things/${f}.sql`, "-- x");
      w(dir, "docs/ARCH.md", "Migrations: <!--fact:things-->2<!--/fact-->.\n"); // declares 2, reality is 3
      return cfg({ factKeys: ["things"], reality: { counts: [count("things", "docs/ARCH.md", { glob: "things/*.sql" })] } });
    } },
  { id: "counts-clean", needsGit: false, expect: { finding: false },
    build(dir) {
      for (const f of ["a", "b", "c"]) w(dir, `things/${f}.sql`, "-- x");
      w(dir, "docs/ARCH.md", "Migrations: <!--fact:things-->3<!--/fact-->.\n");
      return cfg({ factKeys: ["things"], reality: { counts: [count("things", "docs/ARCH.md", { glob: "things/*.sql" })] } });
    } },
  { id: "counts-owner-missing", needsGit: false, expect: { finding: true, checkId: "counts" },
    build(dir) {
      w(dir, "things/a.sql", "-- x");
      w(dir, "docs/OTHER.md", "no marker here\n"); // the declared owner does NOT exist → a Finding, not a crash
      return cfg({ factKeys: ["things"], reality: { counts: [count("things", "docs/GONE.md", { glob: "things/*.sql" })] } });
    } },

  // ── factDedup ──
  { id: "factDedup-dup", needsGit: false, expect: { finding: true, checkId: "factDedup" },
    build(dir) {
      w(dir, "docs/A.md", "<!--fact:things-->1<!--/fact-->\n");
      w(dir, "docs/B.md", "<!--fact:things-->1<!--/fact-->\n"); // same key in 2 files
      return cfg({ factKeys: ["things"] });
    } },
  { id: "factDedup-undeclared", needsGit: false, expect: { finding: true, checkId: "factDedup" },
    build(dir) {
      w(dir, "docs/A.md", "<!--fact:ghost-->1<!--/fact-->\n"); // undeclared key
      return cfg({ factKeys: ["things"] });
    } },

  // ── guards (HERMETIC GIT) ──
  { id: "guard-stale-git", needsGit: true, expect: { finding: true, checkId: "guard:stale-git" },
    build(dir) {
      w(dir, "src/feature.ts", "export const x = 1;\n");
      w(dir, "docs/STATUS.md", "The feature module is untracked, not yet committed.\n");
      return cfg({ guards: [guardTracked("stale-git", ["src/"], "\\buntracked\\b", "untracked", "the artifacts are git-tracked")] });
    } },
  { id: "guard-stale-deploy", needsGit: true, expect: { finding: true, checkId: "guard:stale-deploy" },
    build(dir) {
      w(dir, "src/feature.ts", "export const x = 1;\n");
      w(dir, "docs/STATUS.md", "The feature is not in prod: it lives only on e2e.\n");
      return cfg({ guards: [guardOnRef("stale-deploy", "src/feature.ts", "not\\s+in\\s+prod", "not in prod", "the artifact IS on origin/main (⇒ deploy)")] });
    } },
  // NEG: the exemption works AND the git premise MUST be fired (noGuardSkip) — a NEG that passes only
  // because the guard degraded to Skip would prove NOTHING (a false negative from the harness itself).
  { id: "guard-stale-git-NEG-historical", needsGit: true, expect: { finding: false, noGuardSkip: true },
    build(dir) {
      w(dir, "src/feature.ts", "export const x = 1;\n");
      w(dir, "docs/archive/OLD.md", "Back then the module was untracked.\n"); // historical zone → exempt
      return cfg({ guards: [guardTracked("stale-git", ["src/"], "\\buntracked\\b", "untracked", "tracked")], historicalPaths: ["docs/archive/"] });
    } },
  { id: "guard-stale-git-NEG-allowmarker", needsGit: true, expect: { finding: false, noGuardSkip: true },
    build(dir) {
      w(dir, "src/feature.ts", "export const x = 1;\n");
      w(dir, "docs/RULE.md", "The guard forbids the word 'untracked'. <!-- virgilio:allow-status-mention -->\n");
      return cfg({ guards: [guardTracked("stale-git", ["src/"], "\\buntracked\\b", "untracked", "tracked")] });
    } },
  { id: "guard-stale-git-NEG-struck", needsGit: true, expect: { finding: false, noGuardSkip: true },
    build(dir) {
      w(dir, "src/feature.ts", "export const x = 1;\n");
      w(dir, "docs/STATUS.md", "~~The module is untracked~~ → now tracked.\n"); // ~~struck-through~~ = resolved
      return cfg({ guards: [guardTracked("stale-git", ["src/"], "\\buntracked\\b", "untracked", "tracked")] });
    } },
  // an unresolvable ref (no origin/main) ⇒ the guard SKIPS (never a false negative from a colliding local ref)
  { id: "guard-ref-unresolvable-skip", needsGit: true, noOriginMain: true, expect: { finding: false, skipIncludes: "guard:stale-deploy" },
    build(dir) {
      w(dir, "src/feature.ts", "export const x = 1;\n");
      w(dir, "docs/STATUS.md", "The feature is not in prod.\n"); // the claim would be there, but the premise isn't observable
      return cfg({ guards: [guardOnRef("stale-deploy", "src/feature.ts", "not\\s+in\\s+prod", "not in prod", "x")] });
    } },

  // ── forbiddenPhrases ──
  { id: "forbidden-live", needsGit: false, expect: { finding: true, checkId: "forbiddenPhrase" },
    build(dir) {
      w(dir, "docs/X.md", "The work lives on branch feat/live-e2e.\n");
      return cfg({ forbiddenPhrases: [{ pattern: "branch feat/.*e2e", flags: "i", reason: "merged into main", since: "2026-07-04" }] });
    } },
  { id: "forbidden-NEG-historical", needsGit: false, expect: { finding: false },
    build(dir) {
      w(dir, "docs/archive/H.md", "Back then it was on branch feat/live-e2e.\n");
      return cfg({ forbiddenPhrases: [{ pattern: "branch feat/.*e2e", flags: "i", reason: "merged" }], historicalPaths: ["docs/archive/"] });
    } },

  // ── links ──
  { id: "links-broken", needsGit: false, expect: { finding: true, checkId: "links" },
    build(dir) {
      w(dir, "docs/X.md", "See [missing](./MISSING.md).\n");
      return cfg({});
    } },
  { id: "links-NEG-sibling", needsGit: false, expect: { finding: false },
    build(dir) {
      w(dir, "docs/X.md", "See [other repo](../../other-repo/x.md) and [ext](https://x.dev).\n");
      return cfg({});
    } },

  // ── docStatus ──
  { id: "docStatus-missing", needsGit: false, expect: { finding: true, checkId: "docStatus" },
    build(dir) {
      w(dir, "docs/S.md", "# Plan\nno status line.\n");
      return cfg({ statusDocs: ["docs/S.md"], statusVocabulary: ["draft", "prod-deployed"] });
    } },
  { id: "docStatus-valid", needsGit: false, expect: { finding: false },
    build(dir) {
      w(dir, "docs/S.md", "# Plan\n<!-- doc-status: draft | updated: 2026-07-04 -->\n");
      return cfg({ statusDocs: ["docs/S.md"], statusVocabulary: ["draft", "prod-deployed"] });
    } },

  // ── boundary: gate wired to a tier-external capability ⇒ config error (exit 2) ──
  { id: "wiring-external-in-gate", needsGit: false, expect: { configError: true },
    build(dir) {
      w(dir, "docs/X.md", "x\n");
      return cfg({
        adapters: ["filesystem", "supabase"],
        guards: [{ id: "bad", polarity: "doc-behind", when: { adapter: "supabase", capability: "probeColumnDenied", query: {}, equals: true }, forbidClaims: [{ pattern: "x" }] }],
      });
    } },

  // ── I4 coverage added after the code review ──
  { id: "counts-marker-missing", needsGit: false, expect: { finding: true, checkId: "counts" },
    build(dir) {
      w(dir, "things/a.sql", "-- x");
      w(dir, "docs/ARCH.md", "No marker here.\n"); // the owner EXISTS but without <!--fact:things-->
      return cfg({ factKeys: ["things"], reality: { counts: [count("things", "docs/ARCH.md", { glob: "things/*.sql" })] } });
    } },
  { id: "docStatus-out-of-vocab", needsGit: false, expect: { finding: true, checkId: "docStatus" },
    build(dir) {
      w(dir, "docs/S.md", "# Plan\n<!-- doc-status: shipped | updated: 2026-07-04 -->\n"); // 'shipped' ∉ vocab
      return cfg({ statusDocs: ["docs/S.md"], statusVocabulary: ["draft", "prod-deployed"] });
    } },
  { id: "counts-glob-recursive", needsGit: false, expect: { finding: false }, // recursive = exactly 3
    build(dir) {
      w(dir, "db/a.sql", "-- x"); w(dir, "db/nested/b.sql", "-- x"); w(dir, "db/nested/deep/c.sql", "-- x");
      w(dir, "docs/ARCH.md", "Migrations: <!--fact:mig-->3<!--/fact-->.\n"); // if the glob weren't recursive it would count 1 → a finding
      return cfg({ factKeys: ["mig"], reality: { counts: [count("mig", "docs/ARCH.md", { glob: "db/**/*.sql" })] } });
    } },
  { id: "forbidden-historical-TOC-decoy", needsGit: false, expect: { finding: true, checkId: "forbiddenPhrase" },
    build(dir) {
      w(dir, "docs/S.md", "Table of contents: see Handoff log below.\n\n## Section\nUse branch feat/x-e2e here.\n\n## Handoff log\nhistorical.\n");
      // line 1 (the TOC) must NOT open the historical zone: only the real '## Handoff log' heading does.
      return cfg({ forbiddenPhrases: [{ pattern: "branch feat/.*e2e", flags: "i", reason: "stale" }], historicalSections: [{ file: "docs/S.md", fromHeadingRegex: "Handoff log" }] });
    } },
  { id: "links-titled-resolves", needsGit: false, expect: { finding: false },
    build(dir) {
      w(dir, "docs/GUIDE.md", "# g\n");
      w(dir, "docs/X.md", "See [the guide](./GUIDE.md \"The Guide\").\n"); // the title must be dropped → resolves
      return cfg({});
    } },
  { id: "links-code-fence-ignored", needsGit: false, expect: { finding: false },
    build(dir) {
      w(dir, "docs/X.md", "Example syntax:\n```\n[page](./MISSING.md)\n```\n"); // a link inside a fence = an example
      return cfg({});
    } },
];

// ── config helpers ──
function cfg(extra) {
  const base = { adapters: ["filesystem"], docsGlobs: ["docs/**/*.md"] };
  // fixtures with guards use the git adapter → include it (unless explicitly overridden)
  if (extra.guards && !extra.adapters) base.adapters = ["filesystem", "git"];
  return { ...base, ...extra };
}
function count(fact, owner, query) {
  return { fact, owner, adapter: "filesystem", capability: "count", query };
}
function guardTracked(id, paths, pattern, label, message) {
  return { id, polarity: "doc-behind", when: { adapter: "git", capability: "isTracked", query: { paths }, equals: true }, forbidClaims: [{ pattern, flags: "i", label }], message };
}
function guardOnRef(id, path, pattern, label, message) {
  return { id, polarity: "doc-behind", when: { adapter: "git", capability: "existsOnRef", query: { ref: "origin/main", path }, equals: true }, forbidClaims: [{ pattern, flags: "i", label }], message };
}

async function runFixture(fx) {
  const dir = mkdtempSync(join(tmpdir(), `virgilio-bite-${fx.id}-`));
  try {
    const cfgObj = fx.build(dir);
    if (fx.needsGit) gitHermetic(dir, !fx.noOriginMain);
    const ctx = makeCtx(dir);
    let findings = [], skips = [], threw = null;
    try {
      ({ findings, skips } = await runChecks({ root: dir, cfg: cfgObj, ctx }));
    } catch (e) {
      threw = e;
    }
    return assertExpect(fx, findings, skips, threw);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

function assertExpect(fx, findings, skips, threw) {
  const e = fx.expect;
  if (e.configError) {
    if (threw && threw.isConfigError) return ok(fx, "expected config error");
    return bad(fx, `expected a config error, got ${threw ? threw.message : `${findings.length} findings`}`);
  }
  if (threw) return bad(fx, `unexpected throw: ${threw.message}`);

  // assertions on Skips (an unexpected green-with-skip means the exemption was never actually proven)
  if (e.skipIncludes && !skips.some((s) => s.checkId.startsWith(e.skipIncludes))) {
    return bad(fx, `expected a Skip with checkId '${e.skipIncludes}*', saw: ${skips.map((s) => s.checkId).join(",") || "none"}`);
  }
  if (e.noGuardSkip) {
    const gs = skips.filter((s) => s.checkId.startsWith("guard:"));
    if (gs.length) return bad(fx, `NEG guard degraded to Skip (premise NOT fired: ${gs.map((s) => s.reason).join("; ")}) — the exemption is NOT proven`);
  }

  const n = findings.length;
  if (e.finding === true) {
    if (n === 0) return bad(fx, "expected AT LEAST one finding (the gate does NOT bite) — a false negative");
    if (e.checkId && !findings.some((f) => f.checkId.startsWith(e.checkId))) {
      return bad(fx, `findings exist but none from check '${e.checkId}' (saw: ${[...new Set(findings.map((f) => f.checkId))].join(",")})`);
    }
    return ok(fx, `${n} finding${n === 1 ? "" : "s"} (bites)`);
  }
  if (n > 0) return bad(fx, `expected ZERO findings (a false positive), got ${n}: ${findings.map((f) => f.message).join(" | ")}`);
  return ok(fx, `no findings${e.noGuardSkip ? " + premise fired" : ""}${e.skipIncludes ? " + expected skip" : ""}`);
}
const ok = (fx, msg) => ({ id: fx.id, pass: true, msg });
const bad = (fx, msg) => ({ id: fx.id, pass: false, msg });

// ── Incremental bite (diff-based mutation runs) ─────────────────────────────
// Full mutation runs are the gold standard but O(fixtures) per invocation; on
// unchanged gate sources they re-prove what the last run already proved. So:
// hash every source file that determines gate behavior; when nothing changed
// and the cache says all fixtures were green, short-circuit. When only a
// per-check source changed, run just that check's fixture group (conservative:
// any change to shared core files triggers a full run). CI or `--all` always
// forces the full run — the cache is a local iteration speedup, never the
// source of truth (proxy-drift doctrine applies to the cache too).
const SKILL_ROOT = fileURLToPath(new URL("..", import.meta.url));
const CACHE_PATH = join(SKILL_ROOT, ".bite-cache.json");
// fixture-id prefix → the one source file that group exercises beyond shared core
const GROUP_SOURCES = {
  counts: "core/checks/counts.mjs",
  factDedup: "core/checks/factDedup.mjs",
  guard: "core/checks/guards.mjs",
  forbidden: "core/checks/forbiddenPhrases.mjs",
  links: "core/checks/links.mjs",
  docStatus: "core/checks/docStatus.mjs",
};
const fixtureGroup = (id) => id.split("-")[0];

function digestGateSources() {
  const digests = {};
  for (const dir of ["core", "core/checks", "adapters", "bin"]) {
    const abs = join(SKILL_ROOT, dir);
    if (!existsSync(abs)) continue;
    for (const f of readdirSync(abs).sort()) {
      if (!f.endsWith(".mjs")) continue;
      const rel = `${dir}/${f}`;
      digests[rel] = createHash("sha256").update(readFileSync(join(SKILL_ROOT, rel))).digest("hex");
    }
  }
  return digests;
}
function loadCache() {
  try { return JSON.parse(readFileSync(CACHE_PATH, "utf8")); } catch { return null; }
}
function selectFixtures(changed) {
  const perCheck = new Set(Object.values(GROUP_SOURCES));
  if (changed.some((f) => !perCheck.has(f))) return { fixtures: FIXTURES, reason: "shared core changed" };
  const groups = new Set(
    Object.entries(GROUP_SOURCES).filter(([, src]) => changed.includes(src)).map(([g]) => g)
  );
  return {
    fixtures: FIXTURES.filter((fx) => groups.has(fixtureGroup(fx.id))),
    reason: `changed check(s): ${[...groups].join(", ")}`,
  };
}

export async function main() {
  const runAll = process.argv.includes("--all") || process.env.VIRGILIO_BITE_ALL === "1" || process.env.CI === "true";
  const files = digestGateSources();
  const cache = runAll ? null : loadCache();

  let toRun = FIXTURES;
  let cachedGreen = [];
  if (cache && cache.version === 1 && cache.files) {
    const changed = Object.keys(files).filter((f) => cache.files[f] !== files[f])
      .concat(Object.keys(cache.files).filter((f) => !(f in files)));
    const allGreenInCache = FIXTURES.every((fx) => cache.results?.[fx.id] === true);
    if (changed.length === 0 && allGreenInCache) {
      console.log(`✅ virgilio bite — cache hit: gate sources unchanged since ${cache.timestamp}, all ${FIXTURES.length} fixtures already green. Use --all for a full run.`);
      return 0;
    }
    const sel = changed.length > 0 ? selectFixtures(changed) : { fixtures: [], reason: "no source changes" };
    if (sel.fixtures.length < FIXTURES.length) {
      // run the selected groups + anything not green in cache (conservative)
      const selected = new Set(sel.fixtures.map((fx) => fx.id));
      toRun = FIXTURES.filter((fx) => selected.has(fx.id) || cache.results?.[fx.id] !== true);
      cachedGreen = FIXTURES.filter((fx) => !toRun.includes(fx));
      console.error(`bite: incremental (${sel.reason}) — running ${toRun.length}/${FIXTURES.length}, ${cachedGreen.length} green from cache`);
    }
  }

  const results = [];
  for (const fx of toRun) results.push(await runFixture(fx));
  const failed = results.filter((r) => !r.pass);
  for (const r of results) console.error(`${r.pass ? "✓" : "✗"} bite[${r.id}] — ${r.msg}`);

  // persist the cache only on a fully green run; drop it on failure so the next
  // invocation re-proves everything from scratch
  if (!failed.length) {
    const merged = {};
    for (const fx of cachedGreen) merged[fx.id] = true;
    for (const r of results) merged[r.id] = true;
    try {
      writeFileSync(CACHE_PATH, JSON.stringify({ version: 1, files, results: merged, timestamp: new Date().toISOString() }, null, 2));
    } catch { /* cache is best-effort */ }
  } else {
    try { rmSync(CACHE_PATH, { force: true }); } catch { /* best-effort */ }
  }

  if (failed.length) {
    console.error(`\n❌ virgilio bite: ${failed.length}/${results.length} fixtures did NOT bite as expected.`);
    return 1;
  }
  const cachedNote = cachedGreen.length ? ` (+${cachedGreen.length} green from cache)` : "";
  console.log(`✅ virgilio bite — ${results.length} fixtures, all bite as expected (positives + negatives)${cachedNote}.`);
  return 0;
}
