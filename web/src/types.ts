export type ClaimClass =
  | "BINDING_REQUIREMENT" | "OFFICIAL_GUIDANCE" | "INSTITUTIONAL_PROCEDURE"
  | "GLOBAL_COMPARATOR" | "PRODUCT_DESIGN_CONTROL" | "RESEARCH_HYPOTHESIS" | "UNRESOLVED";

export interface Citation {
  source_id: string; section: string; page: number; claim_type: ClaimClass; quote?: string | null;
}

export interface AgentMessage {
  agent_id: string;
  assessment_status: string;
  recommended_action: string;
  applicable_sources: Citation[];
  conditions_checked: string[];
  conditions_unresolved: string[];
  confidence: number;
  requires_human_review: boolean;
  concise_rationale: string;
  data: Record<string, unknown>;
  context_scope: string[];
  mode: string;
}

export interface GateDecision {
  permitted: boolean;
  enforced_action: string;
  reason: string;
  invariant?: string | null;
  blocked_actions: string[];
  conditions_checked: string[];
  requires_human: boolean;
  policy_refs: string[];
}

export interface Transition {
  step?: number; prior_state: string; resulting_state: string; trigger_event: string;
  status: string; reason: string; invariant?: string | null; at?: string; actor?: string;
}

export interface EventRow {
  event_id: string; seq: number; at: string; kind: string; actor: string;
  source_layer: string; summary: string; payload: Record<string, unknown>;
}

export interface Step {
  step: number;
  event: EventRow;
  at: string;
  kind: string;
  prior_state: string;
  agents: AgentMessage[];
  retrieved_evidence: Array<{ agent_id: string; source_id: string; section: string; page: number; claim_type: ClaimClass; quote?: string }>;
  proposed_action: string | null;
  proposal_trace?: string[];
  gate: GateDecision | null;
  enforced_action: string | null;
  resulting_state: string;
  transitions: Transition[];
  human_intervention: { escalation_id?: string; role?: string; reason?: string } | null;
  unresolved_questions: string[];
  information_available: Record<string, Record<string, unknown>>;
  actions_performed: Array<Record<string, unknown>>;
  audit_findings: string[];
  state_description?: string;
  policy_retrieval?: Record<string, unknown> | null;
  legacy_conflation?: string;
}

export interface Attempt {
  attempt_id: string; channel: string; result_revision_id: string; idempotency_key: string;
  accepted: boolean; delivered: boolean; failed: boolean; outcome: string;
  reconciled: boolean; duplicate_suppressed: boolean; created_at: string;
}

export interface Run {
  run_id: string; scenario_id: string; configuration: string; configuration_label: string;
  configuration_description: string; case_id: string; jurisdiction: string; facility_type: string;
  case_scope: string; state: string; state_description: string; current_revision_id: string;
  revisions: Array<{ revision_id: string; version: number; status: string; supersedes_revision_id?: string | null; test_name: string }>;
  acknowledgments: Array<{ ack_id: string; result_revision_id: string; role: string; channel: string; at: string }>;
  escalations: Array<{ escalation_id: string; role: string; reason: string; status: string }>;
  blocking_conditions: string[];
  open_questions: string[];
  documentation_recorded: boolean;
  approvals: Record<string, { by: string; at: string; note?: string }>;
  channels: Array<{ channel_id: string; status: string; kind: string; primary: boolean; note: string }>;
  attempts: Attempt[];
  transport_ledger: Array<Record<string, unknown>>;
  events: EventRow[];
  transitions: Transition[];
  steps: Step[];
  audit: Array<{ seq: number; at: string; event: string; actor: string; summary: string; hash: string }>;
  audit_chain_valid: boolean;
  synthetic: boolean;
}
