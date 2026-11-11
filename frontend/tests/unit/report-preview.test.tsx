import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ReportPreview } from "@/features/landing/report-preview";

describe("contextual report example", () => {
  it("changes the requirements with the role and resets the selected finding", async () => {
    const user = userEvent.setup();
    render(<ReportPreview />);
    await user.click(screen.getByRole("button", { name: /Production ownership/ }));
    expect(screen.getByRole("heading", { name: "Production ownership" })).toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText("COMPARE WITH A ROLE"), "platform");
    expect(screen.getByRole("heading", { name: "Deployment automation" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /PostgreSQL optimization/ })).toBeNull();
    expect(screen.getByRole("button", { name: /Deployment automation/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByText("Interactive example · synthetic data")).toBeInTheDocument();
  });

  it("distinguishes missing evidence from a missing qualification", async () => {
    const user = userEvent.setup();
    render(<ReportPreview />);
    await user.click(screen.getByRole("button", { name: /PostgreSQL optimization/ }));
    const evidence = document.getElementById("sample-evidence")!;
    expect(
      within(evidence).getByText("No supporting passage in this sample résumé."),
    ).toBeInTheDocument();
    expect(within(evidence).getByText(/not proof of a gap in your experience/)).toBeInTheDocument();
    expect(evidence.querySelector("blockquote")).toBeNull();
    expect(screen.getByRole("link", { name: /full working demo/ })).toHaveAttribute(
      "href",
      "/demo",
    );
  });
});
