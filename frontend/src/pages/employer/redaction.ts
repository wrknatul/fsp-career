// The backend replaces contact data in candidate-typed text with this mark until an offer is accepted.
// FSP facts keep the competition protocol URL in `evidence`, so for them the whole field turns into the mark.
export const HIDDEN_MARK = '[скрыто]'

/** True when the whole evidence string was swallowed by redaction (nothing useful is left to show). */
export function isHiddenEvidence(evidence: string | null): boolean {
  return evidence !== null && evidence.trim() === HIDDEN_MARK
}
