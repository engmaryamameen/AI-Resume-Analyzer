import type { GuestState } from "@/lib/types";

type GuestView =
  | { phase: "checking"; guest: GuestState | null }
  | { phase: "ready"; guest: GuestState }
  | { phase: "submitting"; guest: GuestState }
  | { phase: "deleting"; guest: GuestState }
  | { phase: "unavailable"; guest: null; error: unknown };
type Event =
  | { type: "checking" | "submitting" | "deleting" | "finished" }
  | { type: "received"; guest: GuestState }
  | { type: "unavailable"; error: unknown };

/** Only a checked workspace may start a mutation; a result arriving during it cannot clear its lock. */
export function guestReducer(view: GuestView, event: Event): GuestView {
  switch (event.type) {
    case "checking":
      return view.phase === "submitting" || view.phase === "deleting"
        ? view
        : { phase: "checking", guest: view.guest };
    case "received":
      return {
        phase: view.phase === "submitting" || view.phase === "deleting" ? view.phase : "ready",
        guest: event.guest,
      };
    case "unavailable":
      return { phase: "unavailable", guest: null, error: event.error };
    case "submitting":
    case "deleting":
      return view.phase === "ready" ? { phase: event.type, guest: view.guest } : view;
    case "finished":
      return view.phase === "submitting" || view.phase === "deleting"
        ? { phase: "ready", guest: view.guest }
        : view;
  }
}
