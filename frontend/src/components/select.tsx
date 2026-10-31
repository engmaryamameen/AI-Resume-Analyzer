"use client";

import { Children, isValidElement, useEffect, useId, useRef, useState } from "react";
import type { KeyboardEvent, ReactNode } from "react";
import { Icon } from "./icon";

type OptionProps = {
  value: string;
  children: ReactNode;
  disabled?: boolean;
  "data-description"?: string;
};
interface SelectProps {
  id?: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
  disabled?: boolean;
  required?: boolean;
  name?: string;
  className?: string;
}

/** A single-select listbox: focus stays on the combobox, with an active descendant for keyboard reading. */
export function Select({
  id,
  value,
  onChange,
  children,
  disabled,
  required,
  name,
  className = "",
}: SelectProps) {
  const generated = useId();
  const triggerId = id ?? generated;
  const listId = `${generated}-options`;
  const options = Children.toArray(children)
    .filter(isValidElement<OptionProps>)
    .map((node) => node.props);
  const selected = options.findIndex((option) => option.value === value);
  const selectable = options
    .map((option, index) => (!option.disabled && option.value !== "" ? index : -1))
    .filter((index) => index >= 0);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [above, setAbove] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const typeahead = useRef({ text: "", at: 0 });

  useEffect(() => {
    if (!open) return;
    const dismiss = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [open]);
  useEffect(() => {
    if (!open || !list.current) return;
    const option = document.getElementById(`${listId}-${active}`);
    if (option && option.offsetTop < list.current.scrollTop)
      list.current.scrollTop = option.offsetTop;
    else if (
      option &&
      option.offsetTop + option.offsetHeight > list.current.scrollTop + list.current.clientHeight
    )
      list.current.scrollTop = option.offsetTop + option.offsetHeight - list.current.clientHeight;
  }, [active, open, listId]);

  function expand(last = false) {
    const rect = trigger.current?.getBoundingClientRect();
    if (rect)
      setAbove(
        window.innerHeight - rect.bottom < Math.min(selectable.length * 68 + 16, 320) &&
          rect.top > window.innerHeight - rect.bottom,
      );
    setActive(
      selectable.includes(selected) ? selected : ((last ? selectable.at(-1) : selectable[0]) ?? -1),
    );
    setOpen(true);
  }
  function choose(index: number) {
    const option = options[index];
    if (!option || option.disabled || option.value === "") return;
    onChange(option.value);
    setOpen(false);
    trigger.current?.focus();
  }
  function keydown(event: KeyboardEvent<HTMLButtonElement>) {
    if (["ArrowDown", "ArrowUp", "Home", "End", "Enter", " ", "Escape"].includes(event.key))
      event.preventDefault();
    if (event.key === "Escape" || event.key === "Tab") {
      setOpen(false);
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      if (open) choose(active);
      else expand();
      return;
    }
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      if (!open) {
        expand(event.key === "ArrowUp");
        return;
      }
      const next = selectable.indexOf(active) + (event.key === "ArrowDown" ? 1 : -1);
      setActive(selectable[(next + selectable.length) % selectable.length] ?? -1);
    } else if (event.key === "Home" || event.key === "End") {
      if (!open) expand();
      setActive((event.key === "Home" ? selectable[0] : selectable.at(-1)) ?? -1);
    } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
      const now = Date.now();
      const text =
        (now - typeahead.current.at < 600 ? typeahead.current.text : "") + event.key.toLowerCase();
      typeahead.current = { text, at: now };
      const matches = selectable.filter((index) =>
        String(options[index]?.children).toLowerCase().startsWith(text),
      );
      const next = matches.find((index) => index > active) ?? matches[0];
      if (next !== undefined) {
        if (open) setActive(next);
        else onChange(options[next]!.value);
      }
    }
  }
  const current = options[selected];
  return (
    <div ref={root} className={`select-field ${className}`} data-open={open || undefined}>
      <select
        className="select-form-control"
        tabIndex={-1}
        aria-hidden="true"
        name={name}
        disabled={disabled}
        required={required}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onInvalid={(event) => {
          event.preventDefault();
          trigger.current?.focus();
          expand();
        }}
      >
        {children}
      </select>
      <button
        ref={trigger}
        id={triggerId}
        type="button"
        role="combobox"
        aria-expanded={open}
        aria-haspopup="listbox"
        aria-controls={listId}
        aria-activedescendant={open && active >= 0 ? `${listId}-${active}` : undefined}
        aria-required={required || undefined}
        disabled={disabled}
        className="select-trigger"
        data-placeholder={value === "" || undefined}
        onClick={() => (open ? setOpen(false) : expand())}
        onKeyDown={keydown}
        onBlur={(event) => {
          if (!root.current?.contains(event.relatedTarget as Node)) setOpen(false);
        }}
      >
        <span className="select-value">{current?.children ?? "Choose an option"}</span>
        <Icon name="chevronDown" size={18} className="select-chevron" />
      </button>
      {open && !disabled && (
        <div
          ref={list}
          id={listId}
          role="listbox"
          aria-labelledby={triggerId}
          className={`select-options ${above ? "select-options-above" : ""}`}
        >
          {options.map((option, index) =>
            option.value === "" ? null : (
              <div
                id={`${listId}-${index}`}
                role="option"
                aria-selected={value === option.value}
                aria-disabled={option.disabled || undefined}
                data-active={active === index || undefined}
                key={option.value}
                className="select-option"
                onPointerMove={() => {
                  if (!option.disabled) setActive(index);
                }}
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => choose(index)}
              >
                <span className="select-option-copy">
                  <span>{option.children}</span>
                  {option["data-description"] && (
                    <span className="select-option-description">{option["data-description"]}</span>
                  )}
                </span>
                <span className="select-option-check">
                  {value === option.value && <Icon name="check" size={16} />}
                </span>
              </div>
            ),
          )}
        </div>
      )}
    </div>
  );
}
