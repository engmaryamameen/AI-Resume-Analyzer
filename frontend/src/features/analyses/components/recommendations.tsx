"use client";
import Link from "next/link";
import { Icon } from "@/components/icon";
import { Card } from "@/components/ui";
import { RECOMMENDATION_KIND } from "@/lib/copy";
import type { Recommendation } from "@/lib/types";

export function RecommendationList({
  items,
  editHref,
  compact = false,
}: {
  items: Recommendation[];
  editHref?: string;
  compact?: boolean;
}) {
  if (items.length === 0)
    return <p className="text-sm text-muted">Nothing to suggest for this analysis.</p>;
  return (
    <ol className="recommendation-list">
      {items.map((r, i) => (
        <Card as="li" key={`${r.kind}-${i}`} className="improvement-card">
          <div className="improvement-heading">
            <span className="improvement-number">{String(i + 1).padStart(2, "0")}</span>
            <div>
              <span className="improvement-kind">{RECOMMENDATION_KIND[r.kind]}</span>
              <h3>{r.title}</h3>
            </div>
          </div>
          <p className="improvement-detail">{r.detail}</p>
          {(r.excerpt || r.fill_in) && (
            <details className="improvement-guide" open={!compact || undefined}>
              <summary>
                See your wording &amp; editing guide <Icon name="chevronDown" size={15} />
              </summary>
              <div>
                {r.excerpt && (
                  <div>
                    <span className="improvement-label">Your current wording</span>
                    <blockquote>{r.excerpt}</blockquote>
                  </div>
                )}
                {r.fill_in && (
                  <div>
                    <span className="improvement-label">Try this structure</span>
                    <p className="improvement-template">{r.fill_in}</p>
                    <p className="improvement-hint">
                      Fill in only what you can support with true details. This is a template, not a
                      suggested claim.
                    </p>
                  </div>
                )}
              </div>
            </details>
          )}
          {editHref && r.block_id && (
            <Link href={`${editHref}#${r.block_id}`} className="improvement-edit">
              Edit this line <Icon name="arrowUpRight" size={14} />
            </Link>
          )}
        </Card>
      ))}
    </ol>
  );
}
