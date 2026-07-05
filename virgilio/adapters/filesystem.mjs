// adapters/filesystem.mjs — tier 'filesystem' (always available, even in CI). Zero network.
// Generalizes the seed's migrations/edge-functions count into a query-driven check.

import { readdirSync, existsSync, statSync } from "node:fs";
import { join } from "node:path";
import { reality, SKIP } from "../core/reality.mjs";

export const manifest = {
  id: "filesystem",
  requiredIn: [],
  capabilities: { count: { tier: "filesystem" } },
};

export function detect() {
  return { applies: true, evidence: "filesystem always available" };
}

export function availability() {
  return reality({ available: true, value: true, tier: "filesystem", evidence: "fs" });
}

export const capabilities = {
  // query: { glob: "db/migrations/*.sql" }  or  { glob: "db/**/*.sql" } (recursive)
  //        { dirs: "functions/*", exclude: ["_shared"], namePattern: "^le-" } → counts subfolders
  count(query, ctx) {
    const { root } = ctx;
    if (query.glob) return countGlob(root, query.glob);
    if (query.dirs) {
      const base = query.dirs.replace(/\/\*+$/, "").replace(/\/+$/, "");
      const dir = base ? join(root, base) : root;
      const exclude = new Set(query.exclude ?? []);
      const nameRe = query.namePattern ? new RegExp(query.namePattern) : null; // generic filter on the dir name
      if (!existsSync(dir) || !statSync(dir).isDirectory()) {
        return reality({ available: true, value: 0, tier: "filesystem", evidence: `count(dirs=${query.dirs})=0 (dir missing)` });
      }
      const n = readdirSync(dir, { withFileTypes: true })
        .filter((d) => d.isDirectory() && !exclude.has(d.name) && (!nameRe || nameRe.test(d.name))).length;
      const ex = query.exclude?.length ? ` excl ${query.exclude.join(",")}` : "";
      const np = query.namePattern ? ` name~${query.namePattern}` : "";
      return reality({ available: true, value: n, tier: "filesystem", evidence: `count(dirs=${query.dirs}${ex}${np})=${n}` });
    }
    return SKIP("filesystem", "query.count requires 'glob' or 'dirs'");
  },
};

// A real glob: "<dir>/<filePattern>" (non-recursive) or "<dir>/**/<filePattern>" (recursive).
// filePattern supports '*'→[^/]* and '?'→[^/], with '.' taken literally. A '*' in an intermediate PATH
// segment (e.g. 'a/*/b') is NOT supported → loud SKIP (never a silently wrong count).
function countGlob(root, glob) {
  const norm = glob.replace(/\\/g, "/");
  const lastSlash = norm.lastIndexOf("/");
  const dirPart = lastSlash >= 0 ? norm.slice(0, lastSlash) : "";
  const filePart = lastSlash >= 0 ? norm.slice(lastSlash + 1) : norm;
  if (!filePart || filePart.includes("**")) return SKIP("filesystem", `glob '${glob}': '**' is only allowed as a path segment, not inside the file name`);

  let recursive = false;
  let baseDir = dirPart;
  if (dirPart === "**") { recursive = true; baseDir = ""; }
  else if (dirPart.endsWith("/**")) { recursive = true; baseDir = dirPart.slice(0, -3); }
  if (baseDir.includes("*")) return SKIP("filesystem", `glob '${glob}': '*' in an intermediate path segment isn't supported (use '<dir>/**/<file>' or '<dir>/<file>')`);

  const fileRe = fileGlobToRegex(filePart);
  const absBase = baseDir ? join(root, baseDir) : root;
  if (!existsSync(absBase) || !statSync(absBase).isDirectory()) {
    return reality({ available: true, value: 0, tier: "filesystem", evidence: `count(glob=${glob})=0 (dir '${baseDir}' missing)` });
  }
  let n = 0;
  const walk = (dir) => {
    for (const d of readdirSync(dir, { withFileTypes: true })) {
      if (d.isDirectory()) {
        if (recursive && d.name !== "node_modules" && d.name !== ".git" && !d.name.startsWith(".")) walk(join(dir, d.name));
      } else if (fileRe.test(d.name)) n++;
    }
  };
  walk(absBase);
  return reality({ available: true, value: n, tier: "filesystem", evidence: `count(glob=${glob})=${n}${recursive ? " (recursive)" : ""}` });
}

function fileGlobToRegex(fp) {
  const esc = fp.replace(/[.+^${}()|[\]\\]/g, "\\$&").replace(/\*/g, "[^/]*").replace(/\?/g, "[^/]");
  return new RegExp("^" + esc + "$");
}
