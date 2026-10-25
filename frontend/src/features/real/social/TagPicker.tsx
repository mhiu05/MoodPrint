import { useId } from "react";
import { counterText, toggle } from "./profileRules";

/** Multi-select chips with native checkbox semantics, grouped when categories exist. */
export function TagPicker({
  legend,
  hint,
  options,
  groups,
  value,
  limits,
  onChange,
}: {
  legend: string;
  hint?: string;
  options: Record<string, string>;
  groups?: [string, string[]][];
  value: string[];
  limits: [number, number];
  onChange: (next: string[]) => void;
}) {
  const counter = useId();
  const atMax = value.length >= limits[1];
  const chip = (key: string) => {
    const checked = value.includes(key);
    return (
      <label className="tag-chip" key={key} data-checked={checked || undefined}>
        <input
          type="checkbox"
          checked={checked}
          disabled={!checked && atMax}
          aria-describedby={counter}
          onChange={() => onChange(toggle(value, key, limits[1]))}
        />
        {options[key] ?? key}
      </label>
    );
  };
  return (
    <fieldset className="tag-picker">
      <legend>{legend}</legend>
      {hint && <p className="tag-hint">{hint}</p>}
      <p
        id={counter}
        className="tag-counter"
        aria-live="polite"
        data-short={value.length < limits[0] || undefined}
      >
        {counterText(value.length, limits)}
      </p>
      {groups ? (
        groups.map(([label, keys]) => (
          <div className="tag-group" role="group" aria-label={label} key={label}>
            <p className="tag-group-title" aria-hidden="true">
              {label}
            </p>
            <div className="tag-chips">{keys.map(chip)}</div>
          </div>
        ))
      ) : (
        <div className="tag-chips">{Object.keys(options).map(chip)}</div>
      )}
    </fieldset>
  );
}
