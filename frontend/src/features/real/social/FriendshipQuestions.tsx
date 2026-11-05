import type { Dispatch } from "react";
import { Button } from "../../../components/UI";
import {
  APPROACHES,
  COMPACT_INTERESTS,
  INTENTIONS,
  INTEREST_GROUPS,
  toDraftProfile,
  type EditorState,
  type EditorAction,
} from "./discoveryProfile";
import type { Taxonomy } from "./profileRules";

/** Move focus before React removes its current target from this interest list. */
export function focusAfterInterestRemoval(
  button: HTMLButtonElement,
  fallback: HTMLElement | null,
) {
  const buttons = Array.from(
    button
      .closest("ul")
      ?.querySelectorAll<HTMLButtonElement>(
        ":scope > li > button:not(:disabled)",
      ) ?? [],
  );
  const index = buttons.indexOf(button);
  (buttons[index + 1] ?? buttons[index - 1] ?? fallback)?.focus();
}

export function FeaturedTray({
  state,
  label,
  dispatch,
  disabled = false,
  fallbackFocus,
}: {
  state: EditorState;
  label: (id: string) => string;
  dispatch: Dispatch<EditorAction>;
  disabled?: boolean;
  fallbackFocus: () => HTMLElement | null;
}) {
  return (
    <ul className="featured-tray" aria-label="Sở thích nổi bật đã chọn">
      {state.featuredInterests.map((id) => (
        <li key={id}>
          <button
            type="button"
            disabled={disabled}
            onClick={(event) => {
              focusAfterInterestRemoval(event.currentTarget, fallbackFocus());
              dispatch({ type: "DEFEATURE", id });
            }}
            aria-label={`Bỏ nổi bật: ${label(id)}`}
          >
            {label(id)} <span aria-hidden="true">×</span>
          </button>
        </li>
      ))}
    </ul>
  );
}
export function InterestChoice({
  id,
  label,
  icon,
  state,
  dispatch,
  disabled = false,
}: {
  id: string;
  label: string;
  icon?: string;
  state: EditorState;
  dispatch: Dispatch<EditorAction>;
  disabled?: boolean;
}) {
  const checked = state.featuredInterests.includes(id);
  return (
    <label
      className="friendship-choice friendship-pill"
      data-checked={checked || undefined}
    >
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={() =>
          dispatch({ type: checked ? "DEFEATURE" : "FEATURE", id })
        }
      />
      {icon && <span aria-hidden="true">{icon}</span>}
      <span>{label}</span>
      <span className="choice-check" aria-hidden="true">
        {checked ? "✓" : ""}
      </span>
    </label>
  );
}
export function FriendshipQuestions({
  state,
  dispatch,
  taxonomy,
  openPicker,
}: {
  state: EditorState;
  dispatch: Dispatch<EditorAction>;
  taxonomy: Taxonomy;
  openPicker: (mode: "all" | "creative" | "active" | "manage") => void;
}) {
  const busy = state.operation !== "idle";
  const label = (id: string) => taxonomy.interests[id] ?? id;
  const full = toDraftProfile(state).interests ?? [];
  return (
    <div className="friendship-questions" data-question={state.mobileQuestion}>
      <fieldset
        className="friendship-question"
        disabled={busy}
        data-question="0"
        aria-describedby="intention-hint"
      >
        <legend id="friendship-q0" tabIndex={-1}>
          Bạn đang tìm kiếm điều gì?
        </legend>
        <p id="intention-hint" className="tag-hint">
          Mong muốn này hiển thị trên thẻ. Gợi ý vẫn dựa trên sở thích và tùy
          chọn ghép bạn đã lưu.
        </p>
        <div className="friendship-intentions">
          {INTENTIONS.map((item) => (
            <label
              className="friendship-choice"
              key={item.id}
              data-checked={state.intention === item.id || undefined}
            >
              <input
                type="radio"
                name="friendship-intention"
                checked={state.intention === item.id}
                onChange={() =>
                  dispatch({ type: "SET_INTENTION", value: item.id })
                }
              />
              <span aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
              <span className="choice-check" aria-hidden="true">
                {state.intention === item.id ? "✓" : ""}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset
        className="friendship-question"
        disabled={busy}
        data-question="1"
        aria-describedby="featured-hint"
      >
        <legend id="friendship-q1" tabIndex={-1}>
          Chọn những điều bạn thích{" "}
          <span className="featured-count">
            {state.featuredInterests.length}/3
          </span>
        </legend>
        <p id="featured-hint" className="tag-hint">
          Chọn tối đa 3 sở thích nổi bật trên thẻ của bạn.
        </p>
        <div className="friendship-entry-choices tag-chips">
          {COMPACT_INTERESTS.map(([id, icon, text]) => (
            <InterestChoice
              key={id}
              id={id}
              icon={icon}
              label={text}
              state={state}
              dispatch={dispatch}
            />
          ))}
          {(
            [
              ["creative", "🎨", "Sáng tạo", "Chọn sở thích sáng tạo"],
              ["active", "🏸", "Thể thao", "Chọn sở thích thể thao"],
            ] as const
          ).map(([kind, icon, text, name]) => {
            const count = state.featuredInterests.filter((id) =>
              INTEREST_GROUPS[kind].includes(id),
            ).length;
            return (
              <button
                type="button"
                className="friendship-choice friendship-pill"
                data-checked={count > 0 || undefined}
                key={kind}
                aria-haspopup="dialog"
                aria-label={`${name}${count > 0 ? ` · ${count}` : ""}`}
                onClick={() => openPicker(kind)}
              >
                <span aria-hidden="true">{icon}</span>
                {text}
                {count > 0 && (
                  <>
                    <span aria-hidden="true">✓</span>
                    <span> · {count}</span>
                  </>
                )}
                <span aria-hidden="true">›</span>
              </button>
            );
          })}
        </div>
        <FeaturedTray
          state={state}
          label={label}
          dispatch={dispatch}
          disabled={busy}
          fallbackFocus={() => document.getElementById("friendship-q1")}
        />
        <Button
          variant="text"
          aria-haspopup="dialog"
          onClick={() => openPicker("all")}
        >
          Xem thêm sở thích
        </Button>
        {(state.draftVersion > 0 || state.retainedInterests.length > 0) && (
          <p className="tag-hint">
            Sở thích đã lưu vẫn được giữ khi bạn bỏ nổi bật.
          </p>
        )}
        {full.length > state.featuredInterests.length && (
          <p className="tag-hint">
            Bạn đã lưu {full.length} sở thích. Các sở thích còn lại vẫn được giữ
            để ghép bạn và có trong thông tin công khai.
          </p>
        )}
        {full.length > 0 && (
          <Button
            variant="text"
            aria-haspopup="dialog"
            onClick={() => openPicker("manage")}
          >
            Quản lý sở thích đã lưu
          </Button>
        )}
      </fieldset>
      <fieldset
        className="friendship-question"
        disabled={busy}
        data-question="2"
      >
        <legend id="friendship-q2" tabIndex={-1}>
          Bạn thích kết nối theo cách nào?
        </legend>
        <div className="friendship-approaches">
          {APPROACHES.map((item) => (
            <label
              key={item.id}
              className="friendship-choice"
              data-checked={state.connectionApproach === item.id || undefined}
            >
              <input
                type="radio"
                name="friendship-approach"
                checked={state.connectionApproach === item.id}
                onChange={() =>
                  dispatch({ type: "SET_APPROACH", value: item.id })
                }
              />
              <span aria-hidden="true">{item.icon}</span>
              <span>{item.label}</span>
              <span className="choice-check" aria-hidden="true">
                {state.connectionApproach === item.id ? "✓" : ""}
              </span>
            </label>
          ))}
        </div>
      </fieldset>
    </div>
  );
}
