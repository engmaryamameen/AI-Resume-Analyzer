/** Word-level before/after diff. Longest-common-subsequence over words; fine for single bullets. */
export type DiffPart = { text: string; kind: "same" | "added" | "removed" };

export function diffWords(before: string, after: string): DiffPart[] {
  const a = before.split(/\s+/).filter(Boolean);
  const b = after.split(/\s+/).filter(Boolean);
  const dp: number[][] = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      dp[i]![j] = a[i] === b[j] ? dp[i + 1]![j + 1]! + 1 : Math.max(dp[i + 1]![j]!, dp[i]![j + 1]!);
  const out: DiffPart[] = [];
  let i = 0, j = 0;
  const push = (text: string, kind: DiffPart["kind"]) => {
    const last = out[out.length - 1];
    if (last && last.kind === kind) last.text += " " + text; else out.push({ text, kind });
  };
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) { push(a[i]!, "same"); i++; j++; }
    else if (dp[i + 1]![j]! >= dp[i]![j + 1]!) push(a[i++]!, "removed");
    else push(b[j++]!, "added");
  }
  while (i < a.length) push(a[i++]!, "removed");
  while (j < b.length) push(b[j++]!, "added");
  return out;
}

export function Diff({ before, after }: { before: string; after: string }) {
  const parts = diffWords(before, after);
  return (
    <p className="text-sm leading-relaxed">
      {parts.map((p, i) =>
        p.kind === "same" ? <span key={i}>{p.text} </span>
        : p.kind === "added" ? <ins key={i} className="rounded bg-good/15 px-0.5 no-underline"><span className="sr-only">added: </span>{p.text} </ins>
        : <del key={i} className="rounded bg-bad/15 px-0.5"><span className="sr-only">removed: </span>{p.text} </del>)}
    </p>
  );
}
