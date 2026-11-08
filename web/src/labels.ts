/**
 * The label layer (wireframes §4.4–4.7). Every code the API returns is shown to people through these
 * maps: a sentence-case label first, the one-line explanation and the raw code in a tooltip or a detail
 * view. Keyed by code so an Arabic layer (P2-8) can be added without touching pages.
 *
 * Copy precedence: honesty (ux-research §6) > wireframes copy > visual-system values.
 */

export type Tone = "ok" | "progress" | "att" | "crit" | "info" | "ai" | "neutral";

export interface Label {
  label: string;
  explain?: string;
  tone?: Tone;
}

type LabelMap = Record<string, Label>;

const L = (label: string, explain?: string, tone?: Tone): Label => ({ label, explain, tone });

/* ------------------------------------------------------------------ */
/* configurations (§4.4)                                               */
/* ------------------------------------------------------------------ */

export const CONFIGS: LabelMap = {
  resultrelay_council: L("ResultRelay + agent council", "The full system: rules, gate, and AI agents that can only hand a case to a person."),
  resultrelay: L("ResultRelay, rules only", "Policy retrieval, revision-bound acknowledgment and the invariant gate. No AI."),
  static_rules: L("Conventional rules engine", "The same gate with the genetics rule hard-coded and no clause citations. The row to beat."),
  retrieval_only: L("Citation-only RAG", "Quotes policy text without checking jurisdiction or scope; treats accepted as delivered."),
  policy_blind: L("Policy-blind tracker", "Tracks and sends. Accepted counts as delivered; any acknowledgment closes the case."),
  ablate_no_kb: L("Without: knowledge base", "Rules only, minus the requirement for a cited clause."),
  ablate_no_applicability_filter: L("Without: jurisdiction filter", "Rules only, but the top-scoring clause governs, wherever it's from."),
  ablate_no_invariants: L("Without: invariant gate", "Rules only, but proposals run as proposed."),
  ablate_no_audit_agent: L("Without: audit assessor", "Rules only, minus the fifth assessor."),
  ablate_full_context: L("Without: separated context", "Rules only, but every assessor sees the whole case."),
  ablate_ack_any: L("Without: revision binding", "Rules only, but any acknowledgment closes the case, even for an old revision."),
  ablate_optimistic_transport: L("Without: strict delivery", "Rules only, but gateway acceptance counts as delivery."),
};

/* ------------------------------------------------------------------ */
/* case states (§4.5) — escalation is "needs a person" (att), not red   */
/* ------------------------------------------------------------------ */

export const STATES: LabelMap = {
  RESULT_DRAFT: L("Draft", "Not released by the lab yet. Nothing may be sent.", "progress"),
  RESULT_FINALIZED: L("Finalised", "Released by the lab. Nothing sent yet.", "progress"),
  TRANSMISSION_QUEUED: L("Queued", "Waiting to send. Queued is not sent.", "progress"),
  TRANSMISSION_ATTEMPTED: L("Sent", "Left ResultRelay. The network hasn't answered yet.", "progress"),
  TRANSPORT_ACCEPTED: L("Accepted by gateway", "The SMS provider took the message. That isn't proof it reached the phone.", "progress"),
  DELIVERY_CONFIRMED: L("Delivered", "The phone returned a receipt. No person has acknowledged it.", "progress"),
  DELIVERY_FAILED: L("Delivery failed", "The network reported a definite failure.", "crit"),
  DELIVERY_STATE_UNKNOWN: L("Delivery unknown", "Nobody knows if it arrived. Assume neither; no resend until it's reconciled.", "crit"),
  AWAITING_ACKNOWLEDGMENT: L("Awaiting acknowledgment", "Delivered; waiting for a named person.", "progress"),
  CLINICAL_ACKNOWLEDGMENT_CONFIRMED: L("Acknowledged", "A named person acknowledged this revision. Not documented yet.", "progress"),
  COMMUNICATION_DOCUMENTED: L("Documented", "Acknowledged and recorded for the current revision. The case is closed.", "ok"),
  RETRY_PENDING: L("Retry waiting", "May resend only after the last attempt is reconciled.", "progress"),
  ESCALATION_REQUIRED: L("With a named person", "The gate gave the case to a named role with a deadline. No automatic sends.", "att"),
  ESCALATION_IN_REVIEW: L("In review", "A named person has taken the case. Automatic sends stay blocked.", "att"),
  CORRECTION_PENDING: L("Correction pending", "The result changed. Anything tied to the old revision no longer counts.", "att"),
  CORRECTED_RESULT_FINALIZED: L("Corrected result released", "The corrected revision is final and linked to the one it replaces.", "att"),
  CORRECTED_RESULT_DELIVERY_PENDING: L("Corrected result to send", "The corrected revision needs its own send and acknowledgment.", "att"),
  CORRECTED_RESULT_ACKNOWLEDGED: L("Corrected result acknowledged", "A person acknowledged the corrected revision itself. The case is closed.", "ok"),
  SUPERSEDED: L("Replaced", "An earlier revision, kept for the record. No longer current.", "neutral"),
};

/** Chain stages (Console) → the states each one counts. */
export const CHAIN_STAGES: Array<{ id: string; label: string; note: string; states: string[] }> = [
  { id: "finalised", label: "Finalised", note: "released by the lab", states: ["RESULT_DRAFT", "RESULT_FINALIZED"] },
  { id: "sent", label: "Sent", note: "queued or in flight", states: ["TRANSMISSION_QUEUED", "TRANSMISSION_ATTEMPTED", "RETRY_PENDING"] },
  { id: "gateway", label: "Accepted by gateway", note: "accepted, not delivered", states: ["TRANSPORT_ACCEPTED"] },
  { id: "delivered", label: "Delivered", note: "delivered, not acknowledged", states: ["DELIVERY_CONFIRMED", "AWAITING_ACKNOWLEDGMENT"] },
  { id: "acknowledged", label: "Acknowledged", note: "named person, this revision", states: ["CLINICAL_ACKNOWLEDGMENT_CONFIRMED"] },
  { id: "documented", label: "Documented", note: "the only state that closes", states: ["COMMUNICATION_DOCUMENTED", "CORRECTED_RESULT_ACKNOWLEDGED"] },
];

export const CHAIN_EXITS: Array<{ id: string; label: string; note: string; tone: Tone; states: string[] }> = [
  { id: "person", label: "With a named person", note: "owner and deadline set", tone: "att", states: ["ESCALATION_REQUIRED", "ESCALATION_IN_REVIEW"] },
  { id: "unknown", label: "Delivery unknown or failed", note: "reconcile before retry", tone: "crit", states: ["DELIVERY_STATE_UNKNOWN", "DELIVERY_FAILED"] },
  { id: "correction", label: "Correction in progress", note: "earlier ack. no longer counts", tone: "att", states: ["CORRECTION_PENDING", "CORRECTED_RESULT_FINALIZED", "CORRECTED_RESULT_DELIVERY_PENDING"] },
];

/** Index 0–5 of the chain stage a state belongs to, or -1 if the case has left the chain. */
export function chainIndex(state: string): number {
  return CHAIN_STAGES.findIndex((s) => s.states.includes(state));
}
export function chainExit(state: string) {
  return CHAIN_EXITS.find((e) => e.states.includes(state));
}

/* ------------------------------------------------------------------ */
/* transitions, gate, invariants                                       */
/* ------------------------------------------------------------------ */

export const TRANSITIONS: LabelMap = {
  APPLIED: L("Moved", "The gate allowed the change of state.", "neutral"),
  BLOCKED: L("Blocked", "The gate refused; the state didn't change.", "crit"),
  FORBIDDEN: L("Forbidden", "This change is never allowed from this state.", "crit"),
  NO_RULE: L("No rule", "No rule covers this event in this state; nothing changed.", "neutral"),
  RECORDED: L("Recorded", "Information kept; the state didn't change.", "neutral"),
};

export const GATE: LabelMap = {
  true: L("Allowed", "The gate let the proposed action run.", "progress"),
  false: L("Refused", "The gate stopped the proposed action.", "crit"),
};

export const INVARIANTS: LabelMap = {
  "INV-1": L("Accepted is not delivered", "A send request or gateway acceptance never proves delivery."),
  "INV-2": L("Delivered is not acknowledged", "A phone's receipt is not a person acknowledging."),
  "INV-3": L("Silence is not an answer", "A timeout means \"unknown\"; an unmatched receipt confirms nothing."),
  "INV-4": L("Reconcile before resending", "No new send while the last one's outcome is unknown."),
  "INV-5": L("Each receipt counts once", "A duplicate receipt is refused."),
  "INV-6": L("A correction names what it replaces", "A corrected result must point to the revision it supersedes."),
  "INV-8": L("Acknowledgment binds to the current revision", "An acknowledgment of an older revision doesn't count."),
  "INV-9": L("No channel switch without authority", "A channel that's down doesn't authorise another; that needs a cited rule or approved procedure."),
  "INV-10": L("No closing with questions open", "Acknowledgment alone isn't a record; open conditions block closure."),
};

export const ACTIONS: LabelMap = {
  SEND_PRIMARY: L("Send on the main channel", "First send on the lab's primary channel."),
  AWAIT_EVIDENCE: L("Wait for evidence", "Hold until the network or a person reports back."),
  RECONCILE_ATTEMPT: L("Check the last send", "Find out what happened to the previous attempt."),
  RETRY_SAME_CHANNEL: L("Resend on the same channel", "Allowed only after the last attempt is reconciled."),
  PROPOSE_FALLBACK: L("Propose another channel", "Needs a cited rule or an approved lab procedure."),
  AWAIT_ACKNOWLEDGMENT: L("Wait for acknowledgment", "Delivered; waiting for a named person."),
  RECORD_DOCUMENTATION: L("Record the communication", "Close the case for the current revision."),
  OPEN_CORRECTION_TASK: L("Open a correction task", "The result changed; restart for the new revision."),
  ESCALATE_HUMAN: L("Hand to a person", "Give the case to a named role with a deadline."),
  VERIFY_RECIPIENT: L("Verify the recipient", "Confirm who is on the other end before relying on them."),
  NO_ACTION: L("Do nothing", "Nothing to do at this step."),
};

/* ------------------------------------------------------------------ */
/* assessors and the agent council                                     */
/* ------------------------------------------------------------------ */

export const ASSESSORS: LabelMap = {
  lab_workflow: L("Lab workflow assessor", "Deterministic rule assessor (advisory)."),
  policy_applicability: L("Policy applicability assessor", "Deterministic rule assessor (advisory)."),
  network_delivery: L("Delivery assessor", "Deterministic rule assessor (advisory)."),
  escalation_coordinator: L("Escalation assessor", "Deterministic rule assessor (advisory)."),
  audit_governance: L("Audit assessor", "Deterministic rule assessor (advisory)."),
  deterministic_gate: L("Gate", "The deterministic invariant gate. Its decision is binding."),
};

export const ASSESSMENT: LabelMap = {
  OK: L("No concerns", "The assessor found nothing blocking.", "neutral"),
  HOLD_FOR_EVIDENCE: L("Hold: evidence missing", "Something it needs hasn't been observed yet.", "progress"),
  REQUIRES_HUMAN: L("Needs a person", "It can't be settled by rules alone.", "att"),
  NOT_APPLICABLE: L("Not relevant here", "This assessor has nothing to say about this step.", "neutral"),
};

export const AGENTS: LabelMap = {
  analyst: L("Policy analyst (DHA lens)", "Reads the binding DHA and federal clauses: where does the duty stand?"),
  institution: L("Telecom analyst (TDRA lens)", "Called when delivery is unclear: does any telecom rule define delivery to a person?"),
  reviewer: L("Adversarial reviewer", "A different model family. Challenges every claim and can object; never approves."),
  orchestrator: L("Orchestrator", "Deterministic: reads the checked council output and the gate's decision."),
};

export const AGENT_STATUS: LabelMap = {
  ANSWERED: L("Answered", "The agent gave a complete answer.", "neutral"),
  PARTIAL: L("Partly answered", "Some questions came back unanswered.", "att"),
  DISPUTED: L("Disputed, not relied on", "Still contradicted the record after one revision. Kept in the trace only.", "crit"),
  REFUSED_RESIDENCY: L("Refused: data would leave the UAE", "Processing outside the UAE needs a Health Authority resolution (Federal Law 2/2019 Art. 13).", "crit"),
  UNAVAILABLE: L("Model unavailable", "The agent couldn't be reached; the gate decided without it.", "neutral"),
};

/** Code checks on agent claims (assurance outcomes). */
export const CHECKS: LabelMap = {
  UPHELD: L("Upheld", "Every fact the claim relies on is in the case record.", "neutral"),
  CORRECTED: L("Corrected", "Failed a check, went back once with the findings, and was fixed.", "neutral"),
  DISPUTED: L("Still wrong after revision", "Kept in the trace, never relied on.", "crit"),
  ACCEPTED: L("Objection stands", "The objection fits the case record.", "att"),
  OBJECTION_REJECTED: L("Objection rejected", "The objection doesn't fit the case record, so it can't trigger anything.", "neutral"),
};

export const ORCHESTRATOR: LabelMap = {
  PROCEED: L("Let the gate decide", "No objection survived; the gate decides as usual."),
  ESCALATE: L("Hand to a person", "An objection or disputed claim survived the code checks.", "att"),
};

export const OBJECTIONS: LabelMap = {
  NONE: L("No objection", "Nothing concrete against the action."),
  ACCEPTANCE_AS_DELIVERY: L("Treats \"accepted\" as \"delivered\"", "There is no delivery receipt."),
  STALE_REVISION_ACK: L("Relies on an old revision's acknowledgment", "The acknowledgment is for an earlier revision."),
  SCOPE_ROUTES_ELSEWHERE: L("This result must go to the physician", "The clauses route it away from the patient."),
  UNAPPROVED_CHANNEL: L("Uses a channel nobody approved", "No approved fallback procedure exists."),
  RETRY_BEFORE_RECONCILE: L("Resends before reconciling", "The last attempt's outcome is still unknown."),
  ACK_WINDOW_EXPIRED: L("Still waiting after the window closed", "The lab's acknowledgment window has passed."),
  UNVERIFIED_RECIPIENT: L("Acknowledged by an unverified recipient", "The acknowledgment isn't from a verified recipient."),
  TEXT_CONTRADICTS_RECORD: L("Reply contradicts the record", "What a person wrote contradicts the structured record. Code can't check this, so the bar is 0.70."),
};

export const CLAIM_PROBLEMS: LabelMap = {
  NONE: L("No problem", "The claim follows from the facts and the clause."),
  CONTRADICTS_CASE_FACTS: L("Contradicts the case record", "It asserts a receipt, acknowledgment or attempt that isn't recorded."),
  CLAUSE_DOES_NOT_SUPPORT: L("The clause doesn't say that", "The cited clause doesn't support the claim."),
  WRONG_AUTHORITY: L("Cites a rule that doesn't govern here", "A comparator or another jurisdiction's clause."),
  WRONG_REVISION: L("Uses an older revision", "It relies on evidence for a superseded revision."),
  IGNORES_WHAT_WAS_SAID: L("Ignores what the person said", "It reads the fields, not the words."),
};

export const OBLIGATIONS: LabelMap = {
  COMMUNICATED: L("Communicated", "A person acknowledged the current revision; the record can be written."),
  AWAITING_ACK: L("Waiting for acknowledgment", "Sent or delivered; nobody has acknowledged the current revision."),
  DIRECT_NOT_PERMITTED: L("Must not go to the patient directly", "The clauses route it to a physician."),
  NOT_YET_SENT: L("Not sent yet", "Nothing prevents a first send."),
  INSUFFICIENT_EVIDENCE: L("The rules don't settle it", "The facts and clauses shown aren't enough."),
};

export const GAPS_NAMED: LabelMap = {
  NONE: L("No gap", "No policy gap bears on this step."),
  NO_ACK_CLOCK: L("No official deadline to acknowledge", "No binding clause sets a time limit (GR-03)."),
  DELIVERY_EVIDENCE_UNDEFINED: L("No rule says what proves delivery", "GR-01, GR-15."),
  RECIPIENT_RESPONSIBILITY_UNCLEAR: L("Unclear who must receive it", "GR-16."),
  IDENTITY_OF_RESPONDER_UNVERIFIABLE: L("No rule for verifying who replied", "GR-09."),
  RETENTION_CLASS_UNCLEAR: L("Unclear what kind of record this is", "Audit log or health data? GR-11."),
  FALLBACK_UNAUTHORISED: L("No rule allows another channel", "GR-04."),
};

export const CONFLICTS: LabelMap = {
  READINGS_DIFFER: L("Analyst and reviewer disagree", "Recorded, not escalated by itself."),
  OBJECTION: L("Objection stands", "A reviewer objection survived the code check.", "att"),
  UNSETTLED_HIGH_RISK: L("The rules don't settle a high-risk step", "Recorded; the gate still decides."),
  TELECOM_GAP: L("No telecom rule covers this message", "GR-15."),
  SCOPE_CONFLICT: L("Patient send for a physician-routed result", "The action sends to the patient a result the clauses route elsewhere.", "att"),
};

export const ADVISER: LabelMap = {
  DISABLED: L("Adviser off", "No model is configured; nothing was suggested."),
  ADVISORY_ONLY: L("Advice only", "A suggestion the gate read after deciding."),
  REFUSED_RESIDENCY: L("Refused: data would leave the UAE", "Out-of-country processing is not allowed.", "crit"),
  REJECTED_UNGROUNDED: L("Rejected: no clause behind it", "The suggestion cited nothing that exists."),
  REJECTED_OUT_OF_JURISDICTION: L("Rejected: wrong jurisdiction", "It relied on a clause that can't govern a Dubai case."),
  REJECTED_MALFORMED: L("Rejected: unreadable answer", "The answer didn't match the expected form."),
};

/* ------------------------------------------------------------------ */
/* clauses, verification, gaps                                         */
/* ------------------------------------------------------------------ */

/** Claim class. `{place}` is interpolated by humanise(…, { place }). */
export const CLAIMS: LabelMap = {
  BINDING_REQUIREMENT: L("Binding · {place}", "Must be followed in {place}.", "neutral"),
  OFFICIAL_GUIDANCE: L("Official guidance", "Published by an authority; not mandatory.", "neutral"),
  INSTITUTIONAL_PROCEDURE: L("Lab procedure", "This laboratory's own approved procedure.", "neutral"),
  GLOBAL_COMPARATOR: L("Comparator · {place}", "From elsewhere. Informs; never governs a Dubai case.", "info"),
  PRODUCT_DESIGN_CONTROL: L("Our setting", "A value we chose. No regulation sets it.", "neutral"),
  RESEARCH_HYPOTHESIS: L("Hypothesis", "An idea under test, not a rule.", "neutral"),
  UNRESOLVED: L("Unresolved", "Not yet classified; not relied on.", "att"),
};

export const VERIFICATION: LabelMap = {
  VERIFIED_AGAINST_SOURCE: L("Quote found on the source page", "Checked word for word against the page cited."),
  VERIFIED_OFFICIAL: L("Checked against the official download", "The publisher's own file."),
  VERIFIED_OFFICIAL_REPOSITORY: L("Checked against the official repository", "The government's legislation portal."),
  VERIFIED_TRANSCRIPTION: L("Checked against a transcription", "The official text, retyped from the source."),
  VERIFIED_MIRROR: L("Checked against a mirror copy", "A faithful copy hosted elsewhere."),
  VERIFIED_THIRD_PARTY_COPY: L("Checked against a third-party copy", "Not the publisher's file; treat with care."),
  VERIFIED: L("Checked", "The gap's evidence was re-read against the sources."),
  ABSENCE_SEARCHED: L("Searched, nothing found", "The sources were searched and say nothing on this."),
};

export const GAP_KINDS: LabelMap = {
  SOURCE_AMBIGUITY: L("The rules are unclear", "They can be read more than one way.", "att"),
  INSUFFICIENT_EVIDENCE: L("Not enough evidence", "No source found that settles it.", "att"),
  CANDIDATE_POLICY_GAP: L("Possible policy gap", "Nothing seems to cover it; a regulator may need to.", "att"),
  SOURCE_CONFLICT: L("The rules conflict", "Two sources say different things.", "crit"),
  IMPLEMENTATION_GAP: L("Not built yet", "The rule is clear; the product doesn't do it yet.", "neutral"),
  INTEROPERABILITY_GAP: L("Systems can't exchange it", "Standards don't model it.", "neutral"),
};

/* ------------------------------------------------------------------ */
/* channels, escalations, roles, scope, places, layers                 */
/* ------------------------------------------------------------------ */

export const CHANNEL_STATUS: LabelMap = {
  UP: L("Working", undefined, "neutral"),
  DEGRADED: L("Degraded", undefined, "att"),
  DOWN: L("Down", undefined, "crit"),
  UNKNOWN: L("Unknown", undefined, "att"),
};

export const CHANNELS: LabelMap = {
  "SMS-PATIENT": L("SMS to patient"),
  "PORTAL-PATIENT": L("Patient portal"),
  "PHONE-CALL": L("Phone call"),
};

/** `{role}` is interpolated. */
export const ESCALATION_STATUS: LabelMap = {
  OPEN: L("Waiting for {role}", "Nobody has taken the case yet.", "att"),
  IN_REVIEW: L("Taken", "A named person has taken the case.", "att"),
  CLOSED_ON_COMPLETION: L("Closed with the case", "The case completed; the escalation closed with it.", "neutral"),
};

export const ROLES: LabelMap = {
  SUPERVISOR: L("Supervisor on duty", "Tier 1: the laboratory supervisor on duty."),
  CLINICAL_LEAD: L("Clinical lead", "Tier 2: raised when tier 1 doesn't respond in time."),
  PATIENT: L("Patient"),
  PHYSICIAN: L("Referring physician"),
  REFERRING_PHYSICIAN: L("Referring physician"),
};

export const SCOPES: LabelMap = { WALK_IN: L("Walk-in"), GENETIC: L("Genetic") };

export const PLACES: LabelMap = {
  "AE-DU": L("Dubai"),
  "AE-FED": L("UAE federal"),
  "AE-AZ": L("Abu Dhabi"),
  GLOBAL: L("International"),
};

export const LAYERS: LabelMap = {
  WORKFLOW: L("Workflow"), CLINICAL: L("Lab"), TRANSPORT: L("Network"),
  HUMAN: L("People"), POLICY: L("Rules"), AUDIT: L("Audit"),
};

/* ------------------------------------------------------------------ */
/* events (scenario events + audit entries)                            */
/* ------------------------------------------------------------------ */

export const EVENTS: LabelMap = {
  "result.finalized": L("Lab released the result"),
  "result.corrected": L("Lab corrected the result"),
  "result.supersede": L("Older revision replaced"),
  "transmission.requested": L("Send requested"),
  "transport.accepted": L("Gateway accepted"),
  "transport.timeout": L("Gateway timed out"),
  "transport.delivery_receipt": L("Delivery receipt"),
  "transport.delivery_failed": L("Delivery failed"),
  "transport.status_unknown": L("Delivery status unknown"),
  "reconciliation.result": L("Reconciliation result"),
  "clinical.acknowledgment": L("Acknowledgment received"),
  "patient.callback_no_access": L("Patient called: can't see the message"),
  "channel.fallback_proposed": L("Another channel proposed"),
  "escalation.requested": L("Handed to a person"),
  "escalation.resolved": L("Person took the case"),
  "documentation.recorded": L("Communication recorded"),
  "policy.source_updated": L("Policy source updated"),
  "timer.tick": L("Time passed"),
  "system.action": L("Decision point"),
  // audit-chain entries
  "escalation.overdue": L("Deadline passed; raised to the next tier"),
  "state.transition.blocked": L("Gate refused a change"),
  "state.transition.applied": L("State changed"),
  "state.transition.no_rule": L("No rule for this event"),
  "state.transition.forbidden": L("Change forbidden"),
  "state.transition.recorded": L("Recorded, no change"),
  "step.completed": L("Step completed"),
  "agent.message": L("Agent message"),
  "agent.tool_call": L("Agent tool call"),
  "assurance.review": L("Code checked an agent claim"),
  "council.escalation": L("Council handed the case to a person"),
  "orchestrator.decision": L("Orchestrator decision"),
  "proposal.contested": L("Proposal contested"),
  "action.blocked": L("Action blocked by the gate"),
  "action.failed": L("Action failed"),
  "event.received": L("Event received"),
  "event.injected": L("Event injected by a judge"),
  "event.informational": L("Information recorded"),
  "legacy.conflation": L("Baseline conflated two states"),
  "run.started": L("Run started"),
  "run.completed": L("Run completed"),
};

export const ASSERTIONS: LabelMap = {
  no_delivery_without_matched_receipt: L("No \"delivered\" without a matching receipt"),
  no_ack_without_delivery: L("No acknowledgment before delivery"),
  no_false_closure: L("No closing with questions open"),
  unknown_preserved_after_timeout: L("A timeout stays \"unknown\""),
  reconcile_before_retry: L("Reconcile before resending"),
  no_duplicate_dispatch: L("No duplicate sends"),
  no_unauthorised_channel: L("No unapproved channel"),
  no_patient_direct_communication_for_genetic_result: L("Genetic results never go straight to the patient"),
  stale_ack_not_used_for_current_revision: L("An old revision's acknowledgment isn't used"),
  correction_references_previous_revision: L("A correction names what it replaces"),
  receipt_bound_to_its_revision: L("Each receipt counts for its own revision"),
  no_out_of_jurisdiction_binding_citation: L("No other jurisdiction's rule as governing"),
  fallback_only_with_recorded_authorisation: L("Fallback only with recorded authority"),
  human_approval_enforced: L("Human approval enforced"),
  audit_chain_valid: L("Audit chain verifies"),
  provenance_present: L("Every send cites a clause"),
};

/* ------------------------------------------------------------------ */
/* scenarios (§4.6)                                                    */
/* ------------------------------------------------------------------ */

export const SCENARIOS: Record<string, { title: string; why: string | null; normallyCloses?: boolean }> = {
  S1: { title: "Delivery outcome unknown", why: "Nobody knows if the SMS arrived, and the patient says they saw nothing." },
  S2: { title: "Corrected after it was acknowledged", why: "The result was corrected; the earlier acknowledgment no longer counts." },
  S3a: { title: "SMS down, no approved fallback", why: "The SMS channel is down and no procedure approves another channel." },
  S3b: { title: "SMS down, approved fallback", why: "Normally closes: the approved procedure authorises the portal.", normallyCloses: true },
  S4: { title: "Genetic result, generic rule retrieved", why: "A genetic result must go to the referring physician (DHA ST-28 §13.4), not the patient." },
  S5: { title: "Late acknowledgment races a correction", why: "A late acknowledgment belongs to the old revision and can't close the new one." },
  S6: { title: "Abu Dhabi rule ranks above Dubai's", why: "Normally closes: the Abu Dhabi clause is kept as a comparator.", normallyCloses: true },
  S7: { title: "Genetic result routed to the physician", why: "Normally closes: sent to the physician, as §13.4 requires.", normallyCloses: true },
  S8: { title: "Accepted by the gateway, never delivered", why: "The gateway accepted the SMS. No receipt, no acknowledgment." },
  S9: { title: "The daughter replied", why: "The reply came from the patient's daughter. The patient hasn't been reached." },
  S10: { title: "Escalation nobody answered", why: "The supervisor didn't respond within 30 min. Raised to the clinical lead." },
  S11: { title: "Delivered, never acknowledged", why: "Delivered, but nobody has acknowledged it. Delivered is not acknowledged." },
};

/** "S10-escalation-nobody-answers" → "S10"; "SYN-S3a-…" → "S3a". */
export function scenarioKey(id?: string | null): string {
  const m = /(?:^|[^A-Za-z0-9])(S\d+[ab]?)(?=$|[^0-9])/.exec(`-${id ?? ""}`);
  return m ? m[1] : (id ?? "");
}
export function scenarioTitle(id?: string | null, fallback?: string): string {
  return SCENARIOS[scenarioKey(id)]?.title ?? fallback ?? id ?? "";
}
export function scenarioWhy(id?: string | null): string | null {
  return SCENARIOS[scenarioKey(id)]?.why ?? null;
}

/* ------------------------------------------------------------------ */
/* lookup                                                              */
/* ------------------------------------------------------------------ */

export const KINDS = {
  state: STATES, transition: TRANSITIONS, gate: GATE, invariant: INVARIANTS, action: ACTIONS,
  assessor: ASSESSORS, assessment: ASSESSMENT, agent: AGENTS, agentStatus: AGENT_STATUS, check: CHECKS,
  orchestrator: ORCHESTRATOR, objection: OBJECTIONS, claimProblem: CLAIM_PROBLEMS, obligation: OBLIGATIONS,
  gapNamed: GAPS_NAMED, conflict: CONFLICTS, adviser: ADVISER, claim: CLAIMS, verification: VERIFICATION,
  gapKind: GAP_KINDS, channelStatus: CHANNEL_STATUS, channel: CHANNELS, escalationStatus: ESCALATION_STATUS,
  role: ROLES, scope: SCOPES, place: PLACES, layer: LAYERS, event: EVENTS, assertion: ASSERTIONS,
  config: CONFIGS,
} as const;

export type LabelKind = keyof typeof KINDS;

export interface LabelVars {
  role?: string;
  place?: string;
}

function fill(s: string | undefined, vars: LabelVars): string | undefined {
  if (!s) return s;
  return s
    .replace(/\{role\}/g, vars.role ? roleLabel(vars.role).toLowerCase() : "a named person")
    .replace(/\{place\}/g, vars.place ? (PLACES[vars.place]?.label ?? vars.place) : "the UAE");
}

/** Fallback for unknown codes: SCREAMING_SNAKE / dotted.path → "Sentence case". Never shows raw enums. */
export function sentenceCase(code: string): string {
  const s = String(code).replace(/[._]+/g, " ").trim().toLowerCase();
  return s ? s[0].toUpperCase() + s.slice(1) : "";
}

export function roleLabel(code?: string | null): string {
  if (!code) return "";
  return ROLES[code]?.label ?? sentenceCase(code);
}

/** Full lookup: label, explanation and tone, with {role}/{place} filled. Unknown codes are sentence-cased. */
export function lookup(kind: LabelKind, code: string | boolean | null | undefined, vars: LabelVars = {}): Label & { known: boolean } {
  const key = String(code ?? "");
  const hit = (KINDS[kind] as LabelMap)[key];
  if (!hit) return { label: key ? sentenceCase(key) : "–", known: false, tone: "neutral" };
  let label = fill(hit.label, vars) ?? key;
  // "With a named person" names the person once the role is known (escalated states only).
  if (kind === "state" && vars.role && (key === "ESCALATION_REQUIRED")) label = `With the ${roleLabel(vars.role).toLowerCase()}`;
  if (kind === "claim" && !vars.place) label = label.replace(/ · the UAE$/, "");
  return { label, explain: fill(hit.explain, vars), tone: hit.tone ?? "neutral", known: true };
}

/** humanise("state", "ESCALATION_REQUIRED") → "With a named person". */
export function humanise(kind: LabelKind, code: string | boolean | null | undefined, vars: LabelVars = {}): string {
  return lookup(kind, code, vars).label;
}

export function explain(kind: LabelKind, code: string | boolean | null | undefined, vars: LabelVars = {}): string | undefined {
  return lookup(kind, code, vars).explain;
}

/** Wireframes §4.3: "due 14:51 · 23 min left" / "due 14:51 · overdue 4 min". `now` defaults to the wall clock. */
export function deadline(dueIso?: string | null, nowIso?: string | null): { text: string; overdue: boolean } | null {
  if (!dueIso) return null;
  const due = new Date(dueIso);
  if (Number.isNaN(due.getTime())) return null;
  const hhmm = due.toISOString().slice(11, 16);
  if (!nowIso) return { text: `due ${hhmm}`, overdue: false };
  const mins = Math.round((due.getTime() - new Date(nowIso).getTime()) / 60000);
  return mins >= 0
    ? { text: `due ${hhmm} · ${mins} min left`, overdue: false }
    : { text: `due ${hhmm} · overdue ${-mins} min`, overdue: true };
}
