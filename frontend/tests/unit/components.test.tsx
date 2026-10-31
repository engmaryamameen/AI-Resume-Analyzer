import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  AnalysisResults,
  AssessmentCard,
  EnginePanel,
  EvidenceCard,
  Probability,
  RequirementCard,
  StatusBadge,
} from "@/components/analysis-view";
import { ComparisonView } from "@/components/comparison-view";
import { Diff, diffWords } from "@/components/diff";
import { ModelStatusView } from "@/components/model-status";
import { ApiError } from "@/lib/api";
import { analysisFailure, failureMessage, friendlyError, percent } from "@/lib/copy";
import type { Assessment, Comparison, EngineInfo, Evidence, Match, ModelStatus } from "@/lib/types";

const requirement = (id: string, text: string) => ({
  id,
  ordinal: 0,
  text,
  kind: "required" as const,
  category: "skill" as const,
  origin: "extracted" as const,
  terms: [],
  min_years: null,
  source_span: null,
});

const evidence: Evidence = {
  block_id: "b1",
  section_kind: "experience",
  excerpt: "Built an API in Python",
  highlights: [[16, 22]],
  label: "supports",
  roles: ["affirmed"],
  derived: false,
  retrieval_score: 0.8123,
  retrieval_method: "bm25",
};

const supported: Match = {
  requirement: requirement("1", "Python"),
  status: "supported",
  conflict: false,
  probability: null,
  reasons: [],
  evidence: [evidence],
  explanation: "A bullet describes building something with it.",
};
const mentioned: Match = {
  requirement: requirement("2", "Kubernetes"),
  status: "mentioned_only",
  conflict: false,
  probability: null,
  reasons: ["It only appears in a skills list."],
  evidence: [],
  explanation: "Named, but nothing says what you did with it.",
};
const absent: Match = {
  requirement: requirement("3", "Rust"),
  status: "no_evidence",
  conflict: false,
  probability: null,
  reasons: [],
  evidence: [],
  explanation: "Nothing in the résumé relates to this.",
};

const rulesEngine: EngineInfo = {
  mode: "rules",
  models: [],
  calibrated: false,
  fingerprint: "rules",
  notes: ["Learned models are not in use: no model manifest is installed."],
};
const learnedEngine: EngineInfo = {
  mode: "learned",
  calibrated: true,
  fingerprint: "abc",
  models: [
    {
      id: "verifier",
      origin: "fine_tuned",
      base_model: "cross-encoder/nli-distilroberta-base",
      revision: "b14d131f9d32668a5e6a982729b57ff6ed5dfcbd",
      license: "Apache-2.0",
    },
    {
      id: "retriever",
      origin: "pretrained",
      base_model: "BAAI/bge-small-en-v1.5",
      revision: "5c38ec7c405ec4b44b94cc5a9bb96e735b38267a",
      license: "MIT",
    },
  ],
  notes: [],
};

const assessments: Assessment[] = [
  {
    id: "requirement_evidence",
    label: "Requirements and evidence",
    summary: "1 of 3 backed up.",
    metrics: [
      {
        name: "supported",
        value: 1,
        unit: "count",
        definition: "Requirements with a passage that describes doing or holding them.",
      },
    ],
    limitations: ["Statuses describe wording, not truth."],
  },
  {
    id: "writing_style",
    label: "Writing style",
    summary: "Too few bullets to say much.",
    metrics: [],
    limitations: [],
  },
];

async function noAccessibilityViolations(container: HTMLElement) {
  const result = await axe.run(container, {
    rules: {
      "color-contrast": { enabled: false },
      region: { enabled: false },
      "heading-order": { enabled: false },
      "page-has-heading-one": { enabled: false },
    },
  });
  expect(result.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
}

afterEach(() => vi.restoreAllMocks());

describe("StatusBadge", () => {
  it("names every status in words, so meaning never depends on colour or icon alone", () => {
    const labels = {
      supported: /Backed up/,
      mentioned_only: /Only mentioned/,
      contradicted: /Contradicted/,
      insufficient: /Not enough to tell/,
      no_evidence: /Nothing found/,
    } as const;
    for (const [status, label] of Object.entries(labels)) {
      const { unmount } = render(<StatusBadge status={status as keyof typeof labels} />);
      expect(screen.getByText(label)).toBeInTheDocument();
      unmount();
    }
  });
});

describe("EvidenceCard", () => {
  it("quotes the résumé verbatim and highlights the matched words", () => {
    const { container } = render(<EvidenceCard evidence={evidence} />);
    expect(container.querySelector("blockquote")?.textContent).toBe("Built an API in Python");
    expect(container.querySelector("mark")?.textContent).toBe("Python");
  });

  it("says where it came from and how the passage was read", () => {
    render(<EvidenceCard evidence={evidence} />);
    expect(screen.getByText("Experience")).toBeInTheDocument();
    expect(screen.getByText("Describes doing it")).toBeInTheDocument();
    expect(screen.getByText("stated as done or held")).toBeInTheDocument();
  });

  it("shows the raw retrieval score only as an ordering detail, never as a percentage", () => {
    const { container } = render(<EvidenceCard evidence={evidence} />);
    expect(container.textContent).toContain("match order value 0.81");
    expect(container.textContent).not.toMatch(/81\s?%|0\.81\s?%/);
  });

  it("says plainly when a figure was worked out rather than quoted", () => {
    render(
      <EvidenceCard
        evidence={{
          ...evidence,
          block_id: null,
          derived: true,
          excerpt: "Dated roles span about 6.0 years (computed from the date ranges).",
          highlights: [],
          retrieval_score: null,
        }}
      />,
    );
    expect(screen.getByText(/Worked out from your dates, not quoted/)).toBeInTheDocument();
  });

  it("ignores highlight ranges that fall outside the text", () => {
    const { container } = render(
      <EvidenceCard evidence={{ ...evidence, highlights: [[50, 90]] }} />,
    );
    expect(container.querySelector("mark")).toBeNull();
  });
});

describe("Probability", () => {
  it("renders nothing when there is no calibrated estimate", () => {
    const { container } = render(<Probability value={null} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("labels an estimate as estimated and calibrated, and explains what that means", async () => {
    render(<Probability value={0.87} />);
    expect(
      screen.getByText(/Estimated, calibrated: about 87% likely to be right/),
    ).toBeInTheDocument();
    expect(screen.getByText(/checked against labelled examples/)).toBeInTheDocument();
  });

  it("formats whole percentages", () => {
    expect(percent(0.874)).toBe("87%");
  });
});

describe("RequirementCard", () => {
  it("shows status, explanation, reasons and evidence together", () => {
    render(
      <ul>
        <RequirementCard match={supported} />
      </ul>,
    );
    expect(screen.getByRole("heading", { name: "Python" })).toBeInTheDocument();
    expect(screen.getByText(/Backed up/)).toBeInTheDocument();
    expect(screen.getByText(/A bullet describes building something with it/)).toBeInTheDocument();
    expect(
      screen.getByText(
        (_, element) =>
          element?.tagName.toLowerCase() === "blockquote" &&
          element.textContent?.includes("Built an API in Python") === true,
      ),
    ).toBeInTheDocument();
  });

  it("flags conflicting passages", () => {
    render(
      <ul>
        <RequirementCard match={{ ...mentioned, status: "insufficient", conflict: true }} />
      </ul>,
    );
    expect(screen.getByText("Conflicting passages")).toBeInTheDocument();
  });

  it("shows no probability line unless one was sent", () => {
    const { rerender } = render(
      <ul>
        <RequirementCard match={supported} />
      </ul>,
    );
    expect(screen.queryByText(/Estimated, calibrated/)).toBeNull();
    rerender(
      <ul>
        <RequirementCard match={{ ...supported, probability: 0.9 }} />
      </ul>,
    );
    expect(screen.getByText(/Estimated, calibrated: about 90%/)).toBeInTheDocument();
  });

  it("states a missing requirement without inventing evidence", () => {
    render(
      <ul>
        <RequirementCard match={absent} />
      </ul>,
    );
    expect(screen.getByText(/Nothing found/)).toBeInTheDocument();
    expect(screen.queryByText("What the résumé says")).toBeNull();
  });
});

describe("EnginePanel", () => {
  it("says the rule-based reading is not machine learning and shows why models are not in use", () => {
    render(<EnginePanel engine={rulesEngine} />);
    expect(screen.getByText("Rule-based reading")).toBeInTheDocument();
    expect(screen.getByText(/not by learned models/)).toBeInTheDocument();
    expect(screen.getByText(/no model manifest is installed/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("lists each model with its origin, revision and licence when learned models were used", () => {
    render(<EnginePanel engine={learnedEngine} />);
    expect(screen.getByText("Local models")).toBeInTheDocument();
    expect(screen.getByText("Calibrated estimates")).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Models used for this analysis" });
    expect(within(table).getByText("BAAI/bge-small-en-v1.5")).toBeInTheDocument();
    expect(within(table).getByText(/published model, used as is/)).toBeInTheDocument();
    expect(within(table).getByText(/fine-tuned for this task/)).toBeInTheDocument();
    expect(within(table).getByText("5c38ec7c405e")).toBeInTheDocument();
    expect(within(table).getByText("Apache-2.0")).toBeInTheDocument();
  });

  it("does not claim calibrated estimates when the models are uncalibrated", () => {
    render(<EnginePanel engine={{ ...learnedEngine, calibrated: false }} />);
    expect(screen.getByText("No probability estimates")).toBeInTheDocument();
  });

  it("renders nothing without engine information", () => {
    const { container } = render(<EnginePanel engine={null} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("ModelStatusView", () => {
  const unavailable: ModelStatus = {
    learned_models_approved: false,
    models: [],
    note: "No model manifest is installed; analyses use the rule-based reading.",
  };

  it("presents the default rules reader as a supported method", () => {
    render(<ModelStatusView status={unavailable} />);
    expect(screen.getByText("Local rules")).toBeInTheDocument();
    expect(screen.getByText(/may miss paraphrases/)).toBeInTheDocument();
    expect(screen.queryByText("Models not available")).toBeNull();
  });

  it("lists approved models", () => {
    render(
      <ModelStatusView
        status={{
          learned_models_approved: true,
          models: learnedEngine.models,
          note: "Approved local models are installed.",
        }}
      />,
    );
    expect(screen.getByText("Local models approved")).toBeInTheDocument();
    expect(screen.getByText(/cross-encoder\/nli-distilroberta-base/)).toBeInTheDocument();
  });
});

describe("AssessmentCard", () => {
  it("shows every metric with its definition and no grade, meter or band", () => {
    const { container } = render(<AssessmentCard assessment={assessments[0]!} />);
    expect(
      screen.getByText(/Requirements with a passage that describes doing or holding them/),
    ).toBeInTheDocument();
    expect(screen.getByText(/supported:/)).toBeInTheDocument();
    expect(container.querySelector('[role="meter"], [role="progressbar"]')).toBeNull();
  });

  it("keeps limitations available", async () => {
    render(<AssessmentCard assessment={assessments[0]!} />);
    await userEvent.click(screen.getByText("Where this falls short"));
    expect(screen.getByText("Statuses describe wording, not truth.")).toBeVisible();
  });
});

describe("AnalysisResults", () => {
  function view() {
    return render(
      <AnalysisResults
        engine={rulesEngine}
        assessments={assessments}
        matches={[supported, mentioned, absent]}
        warnings={[{ code: "w", message: "The file was hard to read.", severity: "warn" }]}
        limitations={["Models can be wrong."]}
        recommendations={[
          {
            kind: "add_evidence",
            requirement_ordinal: 1,
            title: "Show how you used “Kubernetes”",
            detail: "It is named but not described.",
            block_id: "b9",
            excerpt: "Kubernetes",
            fill_in: "[what you did] with [skill], [result you can verify]",
          },
        ]}
      />,
    );
  }

  it("shows the engine and separates evidence, readings and suggestions into focused views", async () => {
    view();
    expect(
      screen.getByRole("heading", { name: "How this was read", level: 2 }),
    ).toBeInTheDocument();
    expect(screen.getByText("The file was hard to read.")).toBeInTheDocument();
    expect(
      screen.getByRole("heading", { name: "Start with these improvements" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/1 requirement has missing or conflicting evidence/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Requirement by requirement" })).toBeNull();
    expect(screen.queryByRole("heading", { name: /Four readings/ })).toBeNull();
    await userEvent.click(screen.getByRole("tab", { name: "Document insights" }));
    expect(screen.getByRole("heading", { name: /Four readings/ })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /Suggestions/ }));
    expect(screen.getByRole("heading", { name: "Suggestions" })).toBeInTheDocument();
    expect(screen.getByText("Models can be wrong.")).toBeInTheDocument();
  });

  it("groups requirements by status", async () => {
    view();
    await userEvent.click(screen.getByRole("tab", { name: "Evidence" }));
    expect(screen.getByRole("heading", { name: "Python" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Kubernetes" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Rust" })).toBeInTheDocument();
  });

  it("shows an actionable edit first and reveals original wording and an honest template on demand", async () => {
    const { container } = view();
    expect(screen.getByRole("heading", { name: /Show how you used/ })).toBeInTheDocument();
    expect(screen.getAllByText("It is named but not described.")[0]!).toBeVisible();
    expect(container.querySelector(".improvement-guide")?.hasAttribute("open")).toBe(false);
    await userEvent.click(
      screen.getAllByText("See your wording & editing guide", { selector: "summary" })[0]!,
    );
    expect(container.querySelector(".improvement-guide")?.hasAttribute("open")).toBe(true);
    expect(screen.getAllByText("Try this structure")[0]!).toBeVisible();
    expect(screen.getAllByText(/Fill in only what you can support/)[0]!).toBeVisible();
  });

  it("has no scores, meters or grade words anywhere", () => {
    const { container } = view();
    expect(container.querySelector('[role="meter"]')).toBeNull();
    expect(container.textContent).not.toMatch(/\bscore\b|Looks strong|Needs work/i);
  });

  it("combines status and source-text search and clears an empty result", async () => {
    view();
    await userEvent.click(screen.getByRole("tab", { name: "Evidence" }));
    await userEvent.click(screen.getByRole("button", { name: /Backed up/, pressed: false }));
    expect(screen.getByRole("heading", { name: "Python" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Kubernetes" })).toBeNull();
    await userEvent.type(screen.getByRole("searchbox"), "unrelated");
    expect(screen.getByText(/Showing 0 of 3/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Clear filters" }));
    expect(screen.getByRole("heading", { name: "Kubernetes" })).toBeInTheDocument();
    await userEvent.type(screen.getByRole("searchbox"), "built an api");
    expect(screen.getByRole("heading", { name: "Python" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Rust" })).toBeNull();
  });

  it("filters requirements by priority without changing the original findings", async () => {
    view();
    await userEvent.click(screen.getByRole("tab", { name: "Evidence" }));
    await userEvent.click(screen.getByRole("combobox", { name: "Requirement priority" }));
    await userEvent.click(screen.getByRole("option", { name: "Nice-to-have" }));
    expect(screen.getByText(/Showing 0 of 3/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("combobox", { name: "Requirement priority" }));
    await userEvent.click(screen.getByRole("option", { name: "Must-have" }));
    expect(screen.getByText(/Showing 3 of 3/)).toBeInTheDocument();
  });

  it("has no detectable accessibility violations", async () => {
    const { container } = view();
    await noAccessibilityViolations(container);
  });
});

describe("Diff", () => {
  it("marks what was added and removed", () => {
    expect(diffWords("Worked on the API", "Built the API")).toEqual([
      { text: "Worked on", kind: "removed" },
      { text: "Built", kind: "added" },
      { text: "the API", kind: "same" },
    ]);
  });

  it("announces changes to screen readers as text, not colour", () => {
    render(<Diff before="Worked on the API" after="Built the API" />);
    expect(screen.getByText("added:", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("removed:", { exact: false })).toBeInTheDocument();
  });

  it("handles identical and empty text", () => {
    expect(diffWords("same text", "same text")).toEqual([{ text: "same text", kind: "same" }]);
    expect(diffWords("", "")).toEqual([]);
  });
});

describe("ComparisonView", () => {
  const base: Comparison = {
    base_id: "a",
    target_id: "b",
    like_for_like: true,
    notes: [],
    metric_changes: [
      { assessment: "requirement_evidence", name: "supported", unit: "count", before: 1, after: 2 },
    ],
    requirement_changes: [
      { requirement: "Python", before: "mentioned_only", after: "supported", change: "improved" },
      { requirement: "Rust", before: null, after: "no_evidence", change: "added" },
    ],
  };

  it("says when the two analyses are a like-for-like comparison", () => {
    render(<ComparisonView c={base} />);
    expect(screen.getByText(/same method, job and résumé/)).toBeInTheDocument();
  });

  it("explains every reason a comparison is not like-for-like", () => {
    render(
      <ComparisonView
        c={{
          ...base,
          like_for_like: false,
          notes: [
            {
              code: "different_analysis_method",
              message: "These analyses used different models or rules.",
            },
            {
              code: "different_job_descriptions",
              message: "These analyses target different job descriptions.",
            },
          ],
        }}
      />,
    );
    expect(screen.getByText(/Read these differences with care/)).toBeInTheDocument();
    expect(screen.getByText(/different models or rules/)).toBeInTheDocument();
    expect(screen.getByText(/different job descriptions/)).toBeInTheDocument();
    expect(screen.queryByText(/same method, job and résumé/)).toBeNull();
  });

  it("shows before and after for each requirement and metric", () => {
    render(<ComparisonView c={base} />);
    expect(screen.getByLabelText("Only mentioned to Backed up")).toBeInTheDocument();
    expect(screen.getByText("Stronger evidence")).toBeInTheDocument();
    expect(screen.getByText("New requirement")).toBeInTheDocument();
    const row = screen.getByRole("row", { name: /supported/ });
    expect(within(row).getByText("2")).toBeInTheDocument();
  });

  it("has no detectable accessibility violations", async () => {
    const { container } = render(<ComparisonView c={base} />);
    await noAccessibilityViolations(container);
  });
});

describe("error messages", () => {
  it("turns known codes into plain language", () => {
    expect(friendlyError(new ApiError(422, "jd_too_short", "x"))).toMatch(
      /Paste the whole job description/,
    );
    expect(friendlyError(new ApiError(403, "password_incorrect", "x"))).toBe(
      "That password isn't right.",
    );
  });

  it("adds the request reference for server errors and unfamiliar codes", () => {
    expect(friendlyError(new ApiError(500, "boom", "x", "req-123"))).toContain(
      "Reference: req-123",
    );
    expect(friendlyError(new ApiError(400, "something_new", "Odd.", "req-9"))).toContain(
      "Reference: req-9",
    );
  });

  it("does not add a reference to errors the user can fix themselves", () => {
    expect(friendlyError(new ApiError(422, "jd_too_short", "x", "req-1"))).not.toContain(
      "Reference",
    );
  });

  it("never exposes a raw error for unexpected exceptions", () => {
    expect(friendlyError(new Error("stack trace here"))).toBe(
      "Something unexpected happened. Please try again.",
    );
  });

  it("explains failed reads and failed analyses", () => {
    expect(failureMessage("no_extractable_text")).toMatch(/scan or a photo/);
    expect(failureMessage("something_else")).toMatch(/Try exporting it again/);
    expect(analysisFailure("worker_lost")).toMatch(/interrupted/);
    expect(analysisFailure("unexpected_RuntimeError")).toContain("unexpected_RuntimeError");
  });
});
