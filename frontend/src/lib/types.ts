// Mirrors backend/app/api/schemas.py, analysis/schema.py and ml/contracts.py. Kept by hand; compare with
// /openapi.json (development only) if the API changes.

export type MatchStatus = "supported" | "mentioned_only" | "contradicted" | "insufficient" | "no_evidence";
export type RunStatus = "queued" | "running" | "succeeded" | "failed" | "cancelled";
export type EvidenceLabel = "supports" | "mentions_only" | "contradicts" | "insufficient";
export type MentionRole = "affirmed" | "listed" | "mentioned" | "negated" | "hedged";
export type RequirementKind = "required" | "preferred";
export type RequirementCategory = "skill" | "experience_years" | "education" | "certification" | "responsibility" | "soft_skill";
export type RequirementOrigin = "extracted" | "inferred" | "user";

export interface Page<T> { items: T[]; total: number; limit: number; offset: number }
export interface User { id: string; email: string; role: string }

export interface Signal { code: string; message: string; severity: "info" | "warn" | "error"; block_id?: string | null }
export interface Parseability { level: "good" | "fair" | "poor"; reliable_for_analysis: boolean; signals: Signal[] }

export interface ResumeVersion {
  id: string; version_no: number; source: string; status: "processing" | "ready" | "failed";
  error_code: string | null; parseability: Parseability | null; created_at: string;
}
export interface Resume { id: string; title: string; created_at: string; latest_version: ResumeVersion }

export interface Block { id: string; section_id: string; kind: "bullet" | "paragraph" | "entry_header"; text: string; page: number | null; line: number }
export interface Section { id: string; kind: string; heading: string | null; block_ids: string[] }
export interface ContactField { value: string | null; confidence: "high" | "medium" | "low"; block_id: string | null }
export interface NormalizedDocument {
  page_count: number | null; blocks: Block[]; sections: Section[];
  contact: { name: ContactField; email: ContactField; phone: ContactField; links: string[] };
  total_experience_months: number | null; uncertainties: Signal[];
}
export interface ResumeDetail extends Resume { normalized: NormalizedDocument | null; versions: ResumeVersion[] }

export interface Requirement {
  id: string; ordinal: number; text: string; kind: RequirementKind; category: RequirementCategory; origin: RequirementOrigin;
  terms: string[]; min_years: number | null;
  source_span: { start?: number; end?: number; alt_group?: number | null; reason?: string; inferred_from?: string[] } | null;
}
export interface JobVersion { id: string; version_no: number; source: string; created_at: string }
export interface Job { id: string; title: string; created_at: string; latest_version: JobVersion }
export interface JobDetail extends Job { raw_text: string; requirements: Requirement[]; warnings: Signal[]; versions: JobVersion[] }

export interface ModelRef { id: string; origin: "pretrained" | "fine_tuned"; base_model: string; revision: string; license: string }
export interface EngineInfo { mode: "learned" | "rules"; models: ModelRef[]; calibrated: boolean; fingerprint: string; notes: string[] }
export interface ModelStatus { learned_models_approved: boolean; models: ModelRef[]; note: string }

export interface Staleness { is_stale: boolean; reasons: string[] }
export interface Analysis {
  id: string; status: RunStatus; resume_version_id: string; resume_document_id: string | null; resume_version_no: number | null;
  jd_version_id: string; latest_resume_version_id: string | null; latest_jd_version_id: string | null;
  pipeline_version: string; engine: EngineInfo | null; error_code: string | null;
  created_at: string; completed_at: string | null; staleness: Staleness;
}

export interface Evidence {
  block_id: string | null; section_kind: string | null; page?: number | null; line?: number | null; excerpt: string;
  highlights: [number, number][]; label: EvidenceLabel | null; roles: MentionRole[];
  retrieval_score?: number | null; retrieval_method?: string | null; derived: boolean;
}
export interface Match {
  requirement: Requirement; status: MatchStatus; conflict: boolean; probability: number | null;
  reasons: string[]; evidence: Evidence[]; explanation: string | null;
}
export interface Metric { name: string; value: number | string; unit: "count" | "percent" | "months" | "text"; definition: string }
export interface Assessment {
  id: "requirement_evidence" | "document_structure" | "writing_style" | "extraction_reliability";
  label: string; summary: string; metrics: Metric[]; limitations: string[];
}
export interface Recommendation {
  kind: "add_evidence" | "resolve_conflict" | "clarify" | "add_dates" | "style_note";
  requirement_ordinal: number | null; title: string; detail: string; block_id: string | null; excerpt: string | null; fill_in: string | null;
}
export interface Mention {
  passage_id: string; start: number; end: number; text: string; type: string; role: MentionRole | null;
  role_probs: Record<string, number> | null; source: "rules" | "learned";
}

export interface AnalysisDetail extends Analysis {
  assessments: Assessment[] | null; warnings: Signal[]; recommendations: Recommendation[]; limitations: string[];
  matches: Match[]; mentions: Mention[];
}

export interface Comparison {
  base_id: string; target_id: string; like_for_like: boolean; notes: { code: string; message: string }[];
  metric_changes: { assessment: string; name: string; unit: string; before: number | string | null; after: number | string }[];
  requirement_changes: { requirement: string; before: MatchStatus | null; after: MatchStatus | null; change: "improved" | "weaker" | "unchanged" | "added" | "removed" }[];
}

export interface DemoSamples {
  resumes: { id: string; title: string; description: string }[];
  jobs: { id: string; title: string; description: string; text: string }[];
  notice: string;
}
export interface DemoResult {
  resume: { id: string; title: string; normalized: NormalizedDocument; parseability: Parseability };
  job: { id: string | null; title: string; text: string };
  engine: EngineInfo; assessments: Assessment[]; warnings: Signal[]; recommendations: Recommendation[];
  limitations: string[]; mentions: Mention[];
  matches: Match[];
}
