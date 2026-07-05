# Playbook — `virgilio init` (lay the foundations)

> This is a **playbook that YOU (the agent) run** with your own tools (Read/Write/Bash), not an app.
> The only binary involved is `bin/cli.mjs` (to read reality and prove the gate). Idempotent:
> don't overwrite what already exists — propose the changes instead.

## 0. Precondition
A git repo. If there's no git, say so: the deploy/git guards degrade to Skip (virgilio stays useful
for counts/phrases/links/status, just without the git-ref part).

## 1. DETECT — what this repo actually IS (not what I'd PREFER)
Inspect the filesystem: is `git` present? which providers ACTUALLY exist (`supabase/`, `vercel.json`,
`.github/workflows/`)? which folders matter (`migrations/`, `functions/`, `src/`)? If `init` is
invoked from the skill-persona, you receive the **preferred stack** as INPUT; otherwise trust only the
filesystem. **Do not** write stack preferences into virgilio.

## 2. PROPOSE the per-fact SSOT map + the entry chain
From the existing docs plus the detect step, propose: an owner per fact (counts → one doc; status →
one doc; domain → one SSOT doc) and the entry chain (`CLAUDE.md`/`AGENTS.md` → status doc → domain
doc). Ask for confirmation ONLY on the ambiguous branches (proportionality: don't ask about the obvious).

## 3. SCAFFOLD (idempotent, IF NOT EXISTS) — textual substitution of the `{{placeholder}}`s
Copy from `templates/`, substituting `{{prodBranch}}`, `{{prodRef}}`, `{{ownerDocs}}`, `{{statusVocabulary}}`:
- `docs/DOC_GOVERNANCE.md` ← `templates/DOC_GOVERNANCE.template.md` (rulebook §0-9, incl. proxy-drift).
- `virgilio.config.json` ← start from `templates/virgilio.config.example.json`, adapt `adapters`,
  `reality.counts`, `guards`, `statusDocs`, `historical*` to the real repo.
- CI step ← `templates/ci-step.template.yml` (checkout + `git fetch --no-tags --depth=1 origin
  {{prodBranch}}` + `node virgilio/bin/cli.mjs check`). **Without the fetch, stale-deploy degrades to Skip.**
- `AGENTS.md`/`CLAUDE.md` stanza ← `templates/agents-stanza.template.md`.
- npm script `"docs:check": "node virgilio/bin/cli.mjs check"`.

## 4. SEED the markers with the REAL counts (never from memory)
Run `node bin/cli.mjs report --config virgilio.config.json` → it gives you the REAL counts as JSON.
Write the `<!--fact:KEY-->N<!--/fact-->` markers in the owner doc with those numbers. (Never estimate them.)

## 5. PROVE-IT-BITES + green on a clean repo
- `node bin/cli.mjs bite` → if the gate you just scaffolded does NOT bite on an injected violation,
  **do not ship it** (a blind gate is worse than no gate at all).
- `node bin/cli.mjs check --config virgilio.config.json` → MUST be green on the clean repo.

## 6. OUTPUT
Summarize: what was created, which adapters are active, which tiers are NOT available in CI (with the
action needed to provision them, e.g. the `git fetch`), and write the first handoff entry
(`templates/handoff-entry.template.md`).
