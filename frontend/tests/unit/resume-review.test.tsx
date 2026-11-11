import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { AnalysisResults } from "@/features/analyses/components/analysis-report";
import type { AiResumeReview } from "@/lib/types";
import userEvent from "@testing-library/user-event";
const quote = "Built billing APIs in Python with integration tests for payment and refund flows.";
const finding = {
  title: "Concrete implementation work",
  detail: "The billing API and refund tests provide specific implementation context.",
  evidence: [{ block_id: "b1", excerpt: quote }],
};
const review: AiResumeReview = {
  summary:
    "The résumé communicates a concrete engineering contribution but leaves the impact and scale of the billing work unclear.",
  strengths: [finding],
  concerns: [{ ...finding, title: "Impact needs context" }],
  next_steps: [{ ...finding, title: "Clarify the billing outcome" }],
  model: "synthetic-model",
  model_digest: "synthetic-digest",
  prompt_version: "resume-review-1",
  reviewed_blocks: 1,
  total_blocks: 2,
  seconds: 1,
};
describe("source-grounded résumé review", () => {
  it("shows generated feedback and quotations without presenting zero job matches as missing qualifications", async () => {
    const user = userEvent.setup();
    render(
      <AnalysisResults
        review={review}
        engine={null}
        assessments={[]}
        warnings={[]}
        matches={[]}
        limitations={[]}
        recommendations={[]}
        recommendationsHref="/app/analyses/a/recommendations"
      />,
    );
    expect(screen.getByText(review.summary)).toBeInTheDocument();
    expect(screen.getAllByText(quote).length).toBeGreaterThan(0);
    expect(screen.queryByText("Missing or conflicting")).toBeNull();
    expect(screen.queryByRole("tab", { name: "Evidence" })).toBeNull();
    expect(screen.getByRole("link", { name: "Edit the cited résumé passages" })).toHaveAttribute(
      "href",
      "/app/analyses/a/recommendations",
    );
    await user.click(screen.getByRole("tab", { name: /Suggestions/ }));
    expect(
      screen.getByRole("heading", { name: "Your editing priorities", level: 3 }),
    ).toBeVisible();
  });
  it("renders model-provided markup as inert text", () => {
    render(
      <AnalysisResults
        review={{
          ...review,
          summary: "<img src=x onerror=alert(1)> is source text, not trusted HTML.",
        }}
        engine={null}
        assessments={[]}
        warnings={[]}
        matches={[]}
        limitations={[]}
        recommendations={[]}
      />,
    );
    expect(document.querySelector(".ai-resume-review img")).toBeNull();
    expect(screen.getByText(/<img src=x/)).toBeInTheDocument();
  });
});
