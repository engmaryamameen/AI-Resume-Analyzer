export default function WorkspaceLoading() {
  return (
    <div role="status" aria-label="Loading workspace" className="animate-pulse space-y-7">
      <div className="h-9 w-2/3 rounded bg-line/60" />
      <div className="h-4 w-1/2 rounded bg-line/40" />
      <div className="grid grid-cols-3 gap-4">
        {[1, 2, 3].map((i) => (
          <div key={i} className="h-40 rounded-lg border border-line bg-surface" />
        ))}
      </div>
      <div className="h-64 rounded-lg border border-line bg-surface" />
      <span className="sr-only">Loading your workspace…</span>
    </div>
  );
}
