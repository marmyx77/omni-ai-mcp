#!/usr/bin/env node
// bin/cli.mjs — the dispatcher. No check logic here: just routing (exit-code passthrough).
//
//   check   BLOCKING gate, read-only, zero network (only the filesystem + git-ref tiers)
//   report  read-only: emits the configured REALITY as JSON (init seeding + audit evidence)
//   bite    prove-it-bites: mutation-tests every rule against hermetic git fixtures
//   probe   AUDIT-only: runs the 'external'-tier adapters (network/creds), NEVER in the gate
//
// Usage: node bin/cli.mjs <cmd> [--config ./virgilio.config.json]

const [, , cmd, ...rest] = process.argv;

function configPath() {
  const i = rest.indexOf("--config");
  return i >= 0 && rest[i + 1] ? rest[i + 1] : "./virgilio.config.json";
}

const routes = {
  check: () => import("../core/check.mjs").then((m) => m.main({ configPath: configPath() })),
  report: () => import("../core/report.mjs").then((m) => m.main({ configPath: configPath() })),
  bite: () => import("../core/bite.mjs").then((m) => m.main({ configPath: configPath() })),
  probe: () => import("../core/probe.mjs").then((m) => m.main({ configPath: configPath() })),
};

if (!cmd || !routes[cmd]) {
  console.error(`virgilio: unknown command '${cmd ?? ""}'. Use: check | report | bite | probe  [--config <path>]`);
  process.exit(2);
}

routes[cmd]()
  .then((code) => process.exit(typeof code === "number" ? code : 0))
  .catch((e) => {
    console.error(`virgilio ${cmd}: unexpected error — ${e?.stack || e?.message || e}`);
    process.exit(2);
  });
