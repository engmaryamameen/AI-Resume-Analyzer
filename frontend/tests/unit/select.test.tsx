import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { Select } from "@/components/select";

function Picker({
  change = () => undefined,
  disabled = false,
}: {
  change?: (value: string) => void;
  disabled?: boolean;
}) {
  const [value, setValue] = useState("");
  return (
    <>
      <label htmlFor="sample">Sample résumé</label>
      <Select
        id="sample"
        value={value}
        disabled={disabled}
        onChange={(v) => {
          setValue(v);
          change(v);
        }}
      >
        <option value="">Select a résumé</option>
        <option value="avery" data-description="Backend engineering experience">
          Avery
        </option>
        <option value="jordan">Jordan</option>
        <option value="disabled" disabled>
          Unavailable
        </option>
      </Select>
      <button>Outside</button>
    </>
  );
}

describe("Select", () => {
  it("shows descriptions and marks the selected option", async () => {
    const change = vi.fn();
    render(<Picker change={change} />);
    await userEvent.click(screen.getByRole("combobox", { name: "Sample résumé" }));
    expect(screen.getByText("Backend engineering experience")).toBeVisible();
    await userEvent.click(screen.getByRole("option", { name: /Avery/ }));
    expect(change).toHaveBeenCalledWith("avery");
    expect(screen.getByRole("combobox")).toHaveTextContent("Avery");
    await userEvent.click(screen.getByRole("combobox"));
    expect(screen.getByRole("option", { name: /Avery/ })).toHaveAttribute("aria-selected", "true");
  });
  it("supports keyboard selection and skips disabled options", async () => {
    render(<Picker />);
    screen.getByRole("combobox").focus();
    await userEvent.keyboard("{ArrowDown}{End}{Enter}");
    expect(screen.getByRole("combobox")).toHaveTextContent("Jordan");
    expect(screen.queryByRole("listbox")).toBeNull();
    expect(screen.getByRole("combobox")).toHaveFocus();
  });
  it("Escape and outside clicks dismiss without changing the value", async () => {
    const change = vi.fn();
    render(<Picker change={change} />);
    await userEvent.click(screen.getByRole("combobox"));
    await userEvent.keyboard("{ArrowDown}{Escape}");
    expect(change).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("combobox"));
    await userEvent.click(screen.getByRole("button", { name: "Outside" }));
    expect(screen.queryByRole("listbox")).toBeNull();
  });
  it("supports typeahead and a disabled trigger", async () => {
    const { rerender } = render(<Picker />);
    screen.getByRole("combobox").focus();
    await userEvent.keyboard("jor");
    expect(screen.getByRole("combobox")).toHaveTextContent("Jordan");
    rerender(<Picker disabled />);
    expect(screen.getByRole("combobox")).toBeDisabled();
  });
});
