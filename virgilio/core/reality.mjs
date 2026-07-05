// core/reality.mjs — the tri-state envelope at the heart of virgilio.
//
// Every volatile fact read from an adapter comes back as a Reality<T>:
//   available:true  → SATISFIED/VIOLATED (value is meaningful, the check can judge it)
//   available:false → INDETERMINATE: reality is NOT observable here → the caller MUST
//                     emit a loud Skip, NEVER coerce it into a made-up pass/fail.
// This is the anti-false-verdict: an adapter that doesn't know never produces a fake green/red.

export const TIERS = ["filesystem", "git-ref", "external"];

export function reality({ value = null, available, tier, evidence = "", reason = "" }) {
  if (typeof available !== "boolean") {
    throw new Error(`reality(): 'available' must be boolean — did an adapter forget availability? (evidence=${evidence})`);
  }
  if (!TIERS.includes(tier)) throw new Error(`reality(): unknown tier '${tier}' (expected: ${TIERS.join("|")})`);
  if (available === false && !reason) {
    throw new Error(`reality(): available:false requires a 'reason' (why reality isn't observable here) — tier=${tier}`);
  }
  return Object.freeze({
    available,
    value: available ? value : null, // value forced to null when indeterminate: no leftover residue
    tier,
    evidence,
    reason: available ? "" : reason,
  });
}

// Convenience constructor for the INDETERMINATE case.
export const SKIP = (tier, reason, evidence = "") =>
  reality({ available: false, value: null, tier, evidence: evidence || reason, reason });

export const isAvailable = (r) => Boolean(r) && r.available === true;
