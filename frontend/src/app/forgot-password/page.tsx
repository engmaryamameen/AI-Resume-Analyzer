import { SiteHeader } from "@/components/site-header";
import { AccountLinkForm } from "@/features/auth/components/account-link-form";
export default function Page() {
  return (
    <>
      <SiteHeader />
      <main id="main">
        <AccountLinkForm mode="forgot-password" />
      </main>
    </>
  );
}
