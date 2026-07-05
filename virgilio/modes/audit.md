# Playbook — `virgilio audit` (semantic §9: keep the docs honest against reality)

> A playbook that YOU (the agent) run. It's the NON-replaceable counterweight to **proxy-drift**: a
> green gate only says that no KNOWN class of drift has fired, not that the docs are true. Here you
> check against REALITY (git/deploy), **not** against other docs.

## Step 0 — the known gate
`node bin/cli.mjs check --config virgilio.config.json`. Green? Good: the known classes are in order.
But keep going — the value of the audit is finding the NEW classes of drift.

## The three axes (each with EVIDENCE, zero numbers from memory)

**(a) STATUS vs. the period's COMMITS.** Compare the status docs («CURRENT STATUS»/handoff) against
`git log <last-tag..HEAD>` (Bash). Is what's declared *done* actually in that period's commits?

**(b) PLANS vs. REAL DEPLOY.** For every phase marked `[IN PROD]`/`[DONE]`:
- is it really on `origin/main`? (`git cat-file -e origin/main:<path>`, or `node bin/cli.mjs report`);
- and is it confirmed on the **REAL prod ref**? → `node bin/cli.mjs probe --config virgilio.config.json`
  (runs the external-tier probes, e.g. Supabase 42501). **Soft-skip if creds are missing** ⇒ write
  "**not verifiable**", NEVER "verified". This is the ONLY point where the network gets touched.

**(c) CROSS-DOC CONSISTENCY of volatile facts.** Is the same count/version/status/ref consistent
everywhere, or is there a drifted copy? (`node bin/cli.mjs report` gives you reality; grep gives you
the copies.)

## Step N — hardening (proportional)
For EVERY false claim you find, explicitly state **"mechanize it" vs. "leave it to the audit"**:
- **cleanly mechanizable** (a recurring class, low false-positive rate) → add the rule to
  `virgilio.config.json` (`forbiddenPhrases` | a new `fact` | a `guard`) **AND** a bite fixture that
  proves it. Then `node bin/cli.mjs bite` must stay green.
- **one-off / ambiguous** → do NOT mechanize it (a noisy rule erodes trust): note it for the human.

## Final step — leave a trace
Write a handoff entry (`templates/handoff-entry.template.md`) **even at 0 findings** (to record that
the audit ran). Output: findings as `path:line`+claim+reality+evidence, the proposed config patch, and
the generated bite fixtures.
