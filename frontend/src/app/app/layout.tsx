import { WorkspaceShell } from "@/features/auth/components/workspace-shell";

export default function Layout({ children }: { children: React.ReactNode }) {
  return <WorkspaceShell>{children}</WorkspaceShell>;
}
