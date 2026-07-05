// core/adapters.mjs — the adapter loader.
// Loads ONLY the names in cfg.adapters, validated against path traversal (kebab-case), from the
// package's adapters/ dir. Wraps every capability so it ALWAYS returns a Reality (a throw → Skip, never a crash).

import { reality, SKIP, TIERS } from "./reality.mjs";

const ADAPTERS_DIR = new URL("../adapters/", import.meta.url);

export async function loadAdapters(names, ctx) {
  const loaded = {};
  for (const name of names) {
    if (!/^[a-z0-9-]+$/.test(name)) throw new Error(`adapter '${name}': invalid name (expected ^[a-z0-9-]+$)`);
    let mod;
    try {
      mod = await import(new URL(`./${name}.mjs`, ADAPTERS_DIR).href);
    } catch (e) {
      throw new Error(`adapter '${name}' not loadable from adapters/${name}.mjs: ${e?.message || e}`);
    }
    validateManifest(name, mod);

    const avail = assertReality(mod.availability(ctx), `${name}.availability`);
    if (!avail.available && (mod.manifest.requiredIn ?? []).includes(ctx.envName)) {
      // git missing IN CI = a CI misconfig, not a doc to fix → HARD-fail
      const e = new Error(`adapter '${name}' required in env '${ctx.envName}' but unavailable: ${avail.reason}`);
      e.isEnvError = true;
      throw e;
    }

    loaded[name] = {
      manifest: mod.manifest,
      detect: mod.detect,
      available: avail.available,
      availabilityReality: avail,
      async capability(capName, query) {
        const meta = mod.manifest.capabilities[capName];
        if (!meta) throw new Error(`adapter '${name}': capability '${capName}' doesn't exist`);
        if (!avail.available) return SKIP(meta.tier, `adapter '${name}' unavailable: ${avail.reason}`);
        try {
          return assertReality(await mod.capabilities[capName](query ?? {}, ctx), `${name}.${capName}`);
        } catch (e) {
          return SKIP(meta.tier, `${name}.${capName} threw: ${String(e?.message || e).slice(0, 160)}`);
        }
      },
    };
  }
  return loaded;
}

function validateManifest(name, mod) {
  const m = mod.manifest;
  if (!m || m.id !== name) throw new Error(`adapter '${name}': manifest.id missing or ≠ '${name}'`);
  if (typeof mod.detect !== "function" || typeof mod.availability !== "function") {
    throw new Error(`adapter '${name}': needs detect() and availability()`);
  }
  if (!m.capabilities || typeof m.capabilities !== "object") throw new Error(`adapter '${name}': manifest.capabilities missing`);
  for (const [cap, meta] of Object.entries(m.capabilities)) {
    if (!TIERS.includes(meta.tier)) throw new Error(`adapter '${name}': capability '${cap}' has invalid tier '${meta.tier}'`);
    if (typeof mod.capabilities?.[cap] !== "function") throw new Error(`adapter '${name}': capability '${cap}' declared but not implemented`);
  }
}

function assertReality(r, who) {
  if (!r || typeof r.available !== "boolean" || !TIERS.includes(r.tier)) {
    throw new Error(`${who}: did not return a valid Reality (available:boolean + tier)`);
  }
  return r;
}
