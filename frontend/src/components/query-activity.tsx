export function QueryActivity({ active }: { active: boolean }) {
  return (
    <p role="status" aria-live="polite" className="text-sm text-muted">
      {active ? "Refreshing…" : ""}
    </p>
  );
}
