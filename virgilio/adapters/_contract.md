# virgilio's adapter/probe contract

An **adapter** is a file at `adapters/<id>.mjs`. It binds a **question about reality** to a way of
observing it. It's the only layer that touches git / the filesystem / the network — the core doesn't
know *what* reality is, only *how to compare it* against doc declarations.

An adapter is loaded **only** if `<id>` is in `config.adapters`, and **only** from the package's
`adapters/` folder (the name is validated against `^[a-z0-9-]+$`: no arbitrary paths from config).

## Exports

```js
export const manifest = {
  id: "git",                 // must match the file name
  requiredIn: ["ci"],        // envs where UNAVAILABILITY is a HARD fail (misconfig, not a doc issue); elsewhere soft-skip
  capabilities: {            // each capability declares ONLY the tier (no 'kind': cut for proportionality)
    isTracked:   { tier: "git-ref" },
    existsOnRef: { tier: "git-ref" },
  },
};

export function detect(ctx) { return { applies: boolean, evidence: string }; }   // for the init playbook
export function availability(ctx) { return Reality<boolean>; }                   // is the adapter usable here?
export const capabilities = { <name>: (query, ctx) => Reality<T> };              // each capability = one question
```

## `tier` — the one classification that matters (load-bearing)

| tier | meaning | where it can be invoked |
|---|---|---|
| `filesystem` | reality of the committed filesystem (counts, file existence) | **gate** (`check`) |
| `git-ref` | git reality, re-observable IF the ref is available in CI | **gate** (`check`) |
| `external` | network/creds (real-deploy probe) — NOT deterministic, NOT CI-reproducible | **audit only** (`probe`) |

**Non-negotiable rule**: the blocking gate invokes only `filesystem`+`git-ref`; the `external` tier is
invoked **only** by `probe.mjs` (audit). `config.mjs` enforces this at the boundary: a gate wired to an
`external` capability exits 1 before it ever touches reality.

## `Reality<T>` (core/reality.mjs) — the anti-false-verdict

```
{ available: boolean,   // false ⇒ INDETERMINATE: the caller MUST emit a Skip, never coerce to pass/fail
  value: T | null,      // meaningful only if available===true (forced to null otherwise)
  tier, evidence,       // evidence = the EXACT command/observation (audit-grade, falsifiable by hand)
  reason }              // REQUIRED when available===false ('git unavailable', 'creds missing')
```

`ctx = { root, exec(cmd,opts)->{code,stdout,stderr} (NEVER throws), env, envName('ci'|'local'), log }`.
Capabilities convert exec's `{code}` into a `Reality` deterministically. They never throw (the loader
wraps them anyway: a throw becomes a Skip, never a gate crash).

## The adapters' golden rule

- Every capability is **deterministic given** (a committed repo + available refs).
- The adapter **detects** what the repo IS (`detect`); it doesn't hold stack **preferences** (those
  live in your persona/preferences skill). `git.detect = existsSync('.git')`, not "the user prefers git".
- A `provider` adapter (e.g. `supabase`) may name its **own** provider, never a specific ref/tenant
  (those come from the target repo's `config`/`env`). The portability grep-gate verifies this.
