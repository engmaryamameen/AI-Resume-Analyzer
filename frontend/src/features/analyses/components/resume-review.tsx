import Link from "next/link";
import type { AiResumeReview, ReviewFinding } from "@/lib/types";

export function ReviewFindings({ title, items }: { title: string; items: ReviewFinding[] }) {
  return (
    <section className="ai-review-findings">
      <h3>{title}</h3>
      {items.map((item, index) => (
        <article key={`${item.title}-${index}`}>
          <h4>{item.title}</h4>
          <p>{item.detail}</p>
          {item.evidence.map((citation, i) => (
            <blockquote key={`${citation.block_id}-${i}`}>
              <span>From your résumé</span>
              <p>{citation.excerpt}</p>
            </blockquote>
          ))}
        </article>
      ))}
    </section>
  );
}
export function ResumeReviewPanel({
  review,
  editHref,
}: {
  review: AiResumeReview;
  editHref?: string;
}) {
  return (
    <section className="ai-resume-review" aria-label="AI résumé review">
      <div className="ai-review-heading">
        <span className="micro-label">YOUR RÉSUMÉ, REVIEWED IN CONTEXT</span>
        <h2>A closer look at your experience</h2>
        <p>{review.summary}</p>
        <span className="ai-review-method">
          Generated locally by {review.model} · Source-checked quotations
        </span>
      </div>
      <div className="ai-review-columns">
        <ReviewFindings title="What comes through" items={review.strengths} />
        <ReviewFindings title="What needs attention" items={review.concerns} />
      </div>
      <ReviewFindings title="Your editing priorities" items={review.next_steps} />
      {editHref && (
        <Link href={editHref} className="report-next-link">
          Edit the cited résumé passages
        </Link>
      )}
      <p className="ai-review-limit">
        AI feedback can be mistaken. Check each quoted passage and recommendation before editing.
        This reviews the document, not your suitability for employment.
        {review.reviewed_blocks < review.total_blocks
          ? ` ${review.reviewed_blocks} of ${review.total_blocks} passages were included; contact headers are excluded.`
          : ""}
      </p>
    </section>
  );
}
