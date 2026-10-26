"use client";

import { createContext, useContext } from "react";
import type { User } from "./types";

export const UserContext = createContext<{ user: User; setUser: (u: User) => void } | null>(null);

export function useUser() {
  const ctx = useContext(UserContext);
  if (!ctx) throw new Error("useUser must be used inside the signed-in app shell");
  return ctx;
}
