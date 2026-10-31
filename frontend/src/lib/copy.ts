import type { IconName } from "@/components/icon";
import { ApiError } from "./api";
import type { EvidenceLabel, MatchStatus, MentionRole, Recommendation } from "./types";

export const STATUS: Record<
  MatchStatus,
  { label: string; hint: string; tone: "good" | "warn" | "info" | "bad" | "plain"; icon: IconName }
> = {
  supported: {
    label: "Backed up",
    hint: "A passage describes you actually doing or holding this.",
    tone: "good",
    icon: "check",
  },
  mentioned_only: {
    label: "Only mentioned",
    hint: "It's named, but nothing says what you did with it.",
    tone: "warn",
    icon: "list",
  },
  contradicted: {
    label: "Contradicted",
    hint: "The résumé says the opposite, or says you don't have it.",
    tone: "bad",
    icon: "x",
  },
  insufficient: {
    label: "Not enough to tell",
    hint: "Something related is there, but it isn't specific enough to count.",
    tone: "info",
    icon: "help",
  },
  no_evidence: {
    label: "Nothing found",
    hint: "No passage in the résumé relates to this.",
    tone: "plain",
    icon: "minus",
  },
};

export const STATUS_ORDER: MatchStatus[] = [
  "supported",
  "mentioned_only",
  "insufficient",
  "contradicted",
  "no_evidence",
];

export const EVIDENCE_LABEL: Record<EvidenceLabel, string> = {
  supports: "Describes doing it",
  mentions_only: "Names it, nothing more",
  contradicts: "Says otherwise",
  insufficient: "Related but vague",
};

export const ROLE_LABEL: Record<MentionRole, string> = {
  affirmed: "stated as done or held",
  listed: "in a list",
  mentioned: "mentioned in passing",
  negated: "said not to apply",
  hedged: "learning or partial",
};

export const CATEGORY_LABEL: Record<string, string> = {
  skill: "Skill",
  soft_skill: "Soft skill",
  experience_years: "Years of experience",
  education: "Education",
  certification: "Certification",
  responsibility: "Responsibility",
};

export const STALE_REASON: Record<string, string> = {
  resume_version_superseded: "The résumé has been edited since this analysis.",
  job_description_version_superseded: "The requirements have been edited since this analysis.",
  analysis_method_changed: "The analysis method or models have changed since this ran.",
};

export const RECOMMENDATION_KIND: Record<Recommendation["kind"], string> = {
  add_evidence: "Show it in use",
  resolve_conflict: "Check a contradiction",
  clarify: "Be more specific",
  add_dates: "Add dates",
  style_note: "Wording",
};

export const PROBABILITY_EXPLANATION =
  "An estimate from the model, checked against labelled examples it had not seen. Of requirements that get about this " +
  "figure, roughly that share turn out to be right. It is shown only because the models passed that check, and it can " +
  "still be wrong for résumés unlike the examples.";

export const ENGINE_COPY = {
  semantic:
    "Read by local semantic models with rules for entities and dates. The models compare meaning; your documents stay on this server.",
  learned: "Read by local models running on this server. Nothing was sent to an outside service.",
  rules:
    "Read by the rule-based reader, not by learned models. It is literal: it finds the words you wrote and what " +
    "sits around them, and misses paraphrases.",
};

export const ORIGIN_LABEL = {
  pretrained: "published model, used as is",
  fine_tuned: "fine-tuned for this task",
} as const;

const MESSAGES: Record<string, string> = {
  guest_limit:
    "Your free review has been used. Create a free account for another analysis, or return when your 24-hour allowance resets.",
  file_too_large: "That file is over 5 MB. Try exporting a smaller PDF.",
  unsupported_file_type:
    "We can read PDF and Word (.docx) files. Could you save yours as one of those?",
  legacy_doc_unsupported:
    "Older .doc files aren't supported. In Word, use Save As and pick .docx, then upload that.",
  file_type_mismatch:
    "The file doesn't match its extension. Re-export it as a PDF or .docx and try again.",
  empty_file: "That file is empty.",
  invalid_credentials: "That email and password don't match.",
  password_incorrect: "That password isn't right.",
  email_taken: "There's already an account with that email. Try signing in instead.",
  weak_password: "Please pick a longer, less guessable password (at least 12 characters).",
  invalid_email: "That email address doesn't look right.",
  rate_limited: "You're going a little fast. Give it a moment and try again.",
  csrf_failed: "Your session has expired. Please sign in again.",
  unauthenticated: "Please sign in to continue.",
  stale_base_version: "This was changed somewhere else. Reload the page to see the latest version.",
  version_not_ready:
    "That résumé isn't ready yet. Give it a few seconds, or re-upload if it failed.",
  unknown_block:
    "One of the lines you edited no longer exists in this version. Reload and try again.",
  jd_too_short: "That's a bit short to work with. Paste the whole job description.",
  jd_too_long: "That job description is very long. Trim it to the main requirements.",
  idempotency_key_reused: "That request was already used for something else. Please try again.",
  analysis_not_complete: "That analysis hasn't finished yet.",
  user_busy: "Your account is busy with another change. Try again in a moment.",
  network_error: "The service couldn't be reached. Please try again shortly.",
};

export const EXTRACTION_FAILURES: Record<string, string> = {
  pdf_corrupt:
    "We couldn't open this PDF. It may be damaged. Try exporting it again from your editor.",
  pdf_encrypted: "This PDF is password-protected. Remove the password and upload it again.",
  too_many_pages: "This résumé runs past our 8-page limit. Trim it or upload the first pages.",
  no_extractable_text:
    "We couldn't find any text. It may be a scan or a photo. Export a PDF straight from your editor instead.",
  docx_macro: "This Word file contains macros, so we won't open it. Save a copy without macros.",
  docx_corrupt: "We couldn't open this Word file. It may be damaged. Try saving it again.",
  docx_compression_ratio:
    "This Word file expands to an unreasonable size, so we won't open it. Save a fresh copy.",
  extraction_timeout: "Reading the file took too long. Try again, or upload a simpler version.",
  extraction_crashed: "The reader stopped while opening this file. Try exporting it again.",
  extraction_unavailable: "File reading is unavailable right now. Try again in a little while.",
  cancelled: "Reading this file was cancelled.",
  worker_lost: "Reading was interrupted on our side. Upload the file again.",
};

export const ANALYSIS_FAILURES: Record<string, string> = {
  worker_lost: "The analysis was interrupted on our side. Run it again.",
  inputs_unavailable: "The résumé or job description for this analysis is gone.",
};

/** The reference to quote when asking for help, when the server gave one. */
export function reference(e: unknown): string {
  return e instanceof ApiError && e.requestId ? ` Reference: ${e.requestId}` : "";
}

export function friendlyError(e: unknown): string {
  if (e instanceof ApiError) {
    const text =
      MESSAGES[e.code] ??
      (e.status >= 500
        ? "Something went wrong on our side. Please try again in a moment."
        : e.message);
    return text + (e.status >= 500 || !(e.code in MESSAGES) ? reference(e) : "");
  }
  return "Something unexpected happened. Please try again.";
}

export function failureMessage(code: string | null): string {
  return (
    (code && EXTRACTION_FAILURES[code]) ||
    "We couldn't read this file. Try exporting it again as a PDF or .docx."
  );
}

export function analysisFailure(code: string | null): string {
  if (code && ANALYSIS_FAILURES[code]) return ANALYSIS_FAILURES[code]!;
  return (
    "The analysis didn't finish. Run it again; if it keeps failing, quote this code: " +
    (code ?? "unknown") +
    "."
  );
}

export const SECTION_LABEL: Record<string, string> = {
  header: "Top of the page",
  summary: "Summary",
  experience: "Experience",
  education: "Education",
  projects: "Projects",
  skills: "Skills",
  certifications: "Certifications",
  awards: "Awards",
  publications: "Publications",
  volunteering: "Volunteering",
  languages: "Languages",
  interests: "Interests",
  other: "Other",
};

export function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function years(months: number | null): string | null {
  if (months === null) return null;
  const y = months / 12;
  return y < 1 ? `${months} months` : `about ${y.toFixed(1)} years`;
}

export function percent(p: number): string {
  return `${Math.round(p * 100)}%`;
}
