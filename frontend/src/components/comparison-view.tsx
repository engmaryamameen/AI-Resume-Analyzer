import { Icon } from "./icon";
import { STATUS } from "@/lib/copy";
import type { Comparison } from "@/lib/types";
import { Badge, Card, Notice } from "./ui";

const CHANGE: Record<
  Comparison["requirement_changes"][number]["change"],
  { label: string; tone: "good" | "bad" | "plain" | "info" }
> = {
  improved: { label: "Stronger evidence", tone: "good" },
  weaker: { label: "Weaker evidence", tone: "bad" },
  unchanged: { label: "No change", tone: "plain" },
  added: { label: "New requirement", tone: "info" },
  removed: { label: "No longer asked", tone: "plain" },
};

export function ComparisonView({ c }: { c: Comparison }) {
  return (
    <>
      {c.like_for_like ? (
        <div className="mb-6">
          <Notice tone="good">
            These two analyses used the same method, job and résumé, so the differences below
            reflect real changes in the résumé&apos;s text.
          </Notice>
        </div>
      ) : (
        <div
          className="mb-6 space-y-2"
          role="group"
          aria-label="Why this isn't a like-for-like comparison"
        >
          <Notice tone="warn" title="Read these differences with care">
            They are not a like-for-like comparison, for these reasons:
          </Notice>
          {c.notes.map((n) => (
            <Notice key={n.code} tone="warn">
              {n.message}
            </Notice>
          ))}
        </div>
      )}
      <section aria-labelledby="metrics">
        <h2 id="metrics" className="font-serif text-2xl">
          Readings
        </h2>
        {c.metric_changes.length === 0 ? (
          <p className="mt-2 text-muted">No numeric readings to compare.</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="w-full min-w-[32rem] text-left text-sm">
              <caption className="sr-only">
                Changes in each reading between the two analyses
              </caption>
              <thead>
                <tr className="border-b border-line">
                  <th scope="col" className="py-2">
                    Reading
                  </th>
                  <th scope="col">Before</th>
                  <th scope="col">After</th>
                </tr>
              </thead>
              <tbody>
                {c.metric_changes.map((m) => (
                  <tr key={`${m.assessment}-${m.name}`} className="border-b border-line">
                    <th scope="row" className="py-3 font-normal">
                      {m.name.replaceAll("_", " ")}
                    </th>
                    <td>{m.before ?? "—"}</td>
                    <td>{m.after}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      <section className="mt-10" aria-labelledby="reqs">
        <h2 id="reqs" className="font-serif text-2xl">
          Requirements
        </h2>
        <ul className="mt-3 space-y-3">
          {c.requirement_changes.map((r) => (
            <Card
              as="li"
              key={r.requirement}
              className="flex flex-wrap items-center justify-between gap-3"
            >
              <span className="font-medium">{r.requirement}</span>
              <span className="flex flex-wrap items-center gap-2 text-sm">
                <span
                  className="comparison-transition"
                  aria-label={`${r.before ? STATUS[r.before].label : "Not assessed"} to ${r.after ? STATUS[r.after].label : "Not assessed"}`}
                >
                  <span>{r.before ? STATUS[r.before].label : "—"}</span>
                  <Icon name="arrow" size={15} />
                  <span>{r.after ? STATUS[r.after].label : "—"}</span>
                </span>
                <Badge tone={CHANGE[r.change].tone}>{CHANGE[r.change].label}</Badge>
              </span>
            </Card>
          ))}
        </ul>
      </section>
    </>
  );
}
