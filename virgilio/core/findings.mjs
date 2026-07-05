// core/findings.mjs — the verdict types and the audit-grade formatters.
//
// Finding = a VIOLATION: a doc declaration contradicted by re-observed reality.
//           Always carries file:line + claim + reality + EVIDENCE (the exact command/observation).
// Skip     = a CLASS of reality NOT observed here (e.g. stale-deploy skipped because origin/main
//           hasn't been fetched). ALWAYS printed and kept distinct: a green-with-skip is NOT a
//           full green — it flags a coverage gap, not the absence of drift.

export function finding({ checkId, file = "", line = 0, claim = "", reality = "", evidence = "", message, ruleRef = "" }) {
  return {
    checkId,
    file,
    line,
    claim,
    reality,
    evidence,
    message: message ?? (claim ? `${claim} — reality: ${reality}` : reality),
    ruleRef,
  };
}

export function skip({ checkId, tier, reason }) {
  return { checkId, tier, reason };
}

export function formatFinding(f) {
  const loc = f.file ? `[${f.file}${f.line ? ":" + f.line : ""}] ` : "";
  const ev = f.evidence ? `  ·  evidence: ${f.evidence}` : "";
  const rule = f.ruleRef ? `  (${f.ruleRef})` : "";
  return `${loc}${f.message}${rule}${ev}`;
}

export function formatSkip(s) {
  return `⚠ SKIP [${s.checkId}] tier=${s.tier} — ${s.reason}`;
}
