// adapters/git.mjs — tier 'git-ref' (CI-reproducible IF the ref has been fetched). The basis for guards.
// Uses ctx.execFile (argv, NO shell) → no quoting, portable (Windows too), no injection.
// Every capability converts {code} into a Reality deterministically: never throws, never coerces.

import { existsSync } from "node:fs";
import { join } from "node:path";
import { reality, SKIP } from "../core/reality.mjs";

export const manifest = {
  id: "git",
  requiredIn: ["ci"], // in CI git MUST exist: its absence is a CI misconfig, not a doc to fix
  capabilities: {
    isTracked: { tier: "git-ref" },
    existsOnRef: { tier: "git-ref" },
    resolveRef: { tier: "git-ref" },
    logSince: { tier: "git-ref" },
  },
};

export function detect(ctx) {
  const applies = existsSync(join(ctx.root, ".git"));
  return { applies, evidence: applies ? ".git present" : ".git absent" };
}

export function availability(ctx) {
  if (!existsSync(join(ctx.root, ".git"))) return SKIP("git-ref", "git unavailable (.git absent)");
  const r = ctx.execFile("git", ["rev-parse", "--is-inside-work-tree"], { cwd: ctx.root });
  if (r.code !== 0) return SKIP("git-ref", "git not usable in this directory");
  return reality({ available: true, value: true, tier: "git-ref", evidence: "git rev-parse --is-inside-work-tree" });
}

export const capabilities = {
  // { paths: ["src/feature/"] } → true if AT LEAST one is tracked
  isTracked(query, ctx) {
    const paths = query.paths ?? [];
    if (paths.length === 0) return SKIP("git-ref", "isTracked requires at least one path (an empty query.paths would risk a vacuous match against ALL files)");
    const r = ctx.execFile("git", ["ls-files", "--", ...paths], { cwd: ctx.root });
    if (r.code !== 0) return SKIP("git-ref", `git ls-files failed: ${oneline(r.stderr)}`);
    const tracked = r.stdout.trim().length > 0;
    return reality({ available: true, value: tracked, tier: "git-ref", evidence: `git ls-files -- ${paths.join(" ")} → ${tracked ? "tracked" : "absent"}` });
  },

  // { ref: "origin/main", path: "src/x.ts" } → true if the path exists in the ref's tree
  existsOnRef(query, ctx) {
    const ref = resolveRefSpelling(query.ref, ctx);
    if (!ref.available) return ref; // Skip propagated: ref not resolvable (e.g. a shallow clone without a fetch)
    const r = ctx.execFile("git", ["cat-file", "-e", `${ref.value}:${query.path}`], { cwd: ctx.root });
    const present = r.code === 0; // code 0 = present; code!=0 with a valid ref = path absent (NOT a Skip)
    return reality({ available: true, value: present, tier: "git-ref", evidence: `git cat-file -e ${ref.value}:${query.path} → ${present ? "present" : "absent"}` });
  },

  resolveRef(query, ctx) {
    return resolveRefSpelling(query.ref, ctx);
  },

  // audit: { rev: "v1.0..HEAD" } → a list of "sha subject" commits
  logSince(query, ctx) {
    const rev = query.rev ?? "HEAD";
    const r = ctx.execFile("git", ["log", "--oneline", "--no-color", rev], { cwd: ctx.root });
    if (r.code !== 0) return SKIP("git-ref", `git log failed: ${oneline(r.stderr)}`);
    const commits = r.stdout.trim().split("\n").filter(Boolean);
    return reality({ available: true, value: commits, tier: "git-ref", evidence: `git log --oneline ${rev} → ${commits.length} commits` });
  },
};

// Resolves ONLY remote-tracking spellings (a prod-ref is remote). NO fallback to the bare local name:
// resolving a colliding LOCAL branch/tag when the remote is unresolvable would give a false negative (I1).
// If no remote spelling resolves → Skip.
function resolveRefSpelling(ref, ctx) {
  const spellings = ref.includes("/")
    ? [`refs/remotes/${ref}`, ref] // e.g. refs/remotes/origin/main, origin/main
    : [`refs/remotes/origin/${ref}`, `origin/${ref}`]; // bare name → interpreted as remote origin/<ref>
  for (const s of spellings) {
    const r = ctx.execFile("git", ["rev-parse", "--verify", "--quiet", `${s}^{commit}`], { cwd: ctx.root });
    if (r.code === 0) return reality({ available: true, value: s, tier: "git-ref", evidence: `git rev-parse ${s} resolved` });
  }
  return SKIP("git-ref", `ref '${ref}' not resolvable as remote-tracking (need 'git fetch origin ${ref.includes("/") ? ref.split("/").pop() : ref}'?)`);
}

const oneline = (s) => String(s || "").split("\n")[0].slice(0, 200);
