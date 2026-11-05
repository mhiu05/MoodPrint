import { useEffect, useRef, useState, type Dispatch } from "react";
import { Button, Dialog } from "../../../components/UI";
import {
  FeaturedTray,
  InterestChoice,
  focusAfterInterestRemoval,
} from "./FriendshipQuestions";
import {
  INTEREST_GROUPS,
  toDraftProfile,
  type EditorState,
  type EditorAction,
} from "./discoveryProfile";
import type { Taxonomy } from "./profileRules";

const fold = (value: string) =>
  value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase();
export function InterestPickerDialog({
  state,
  dispatch,
  taxonomy,
  mode,
  onClose,
}: {
  state: EditorState;
  dispatch: Dispatch<EditorAction>;
  taxonomy: Taxonomy;
  mode: "all" | "creative" | "active" | "manage";
  onClose: () => void;
}) {
  const pickerRef = useRef<HTMLDivElement>(null);
  const returnFocus = useRef<HTMLElement>(null);
  useEffect(() => {
    returnFocus.current = document.getElementById("friendship-q1");
  }, []);
  const doneButton = () =>
    pickerRef.current?.querySelector<HTMLButtonElement>(
      "[data-interest-done]",
    ) ?? null;
  const [category, setCategory] = useState(
    mode === "creative" || mode === "active"
      ? mode
      : (Object.keys(taxonomy.categories ?? {})[0] ?? ""),
  );
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [compact, setCompact] = useState(
    mode === "creative" || mode === "active",
  );
  const label = (id: string) => taxonomy.interests[id] ?? id;
  const ids = search.trim()
    ? Object.keys(taxonomy.interests).filter((id) =>
        fold(`${id} ${label(id)}`).includes(fold(search.trim())),
      )
    : compact && (category === "creative" || category === "active")
      ? INTEREST_GROUPS[category]
      : (taxonomy.categories?.[category] ?? []);
  return (
    <Dialog
      title={
        mode === "manage" ? "Quản lý sở thích đã lưu" : "Chọn sở thích nổi bật"
      }
      onClose={onClose}
      returnFocus={returnFocus}
    >
      <div
        className="friendship-picker"
        ref={pickerRef}
        onKeyDown={(event) => {
          // Search inputs consume Escape to clear text before native dialog cancel.
          if (event.key === "Escape") {
            event.preventDefault();
            event.stopPropagation();
            onClose();
          }
        }}
      >
        <FeaturedTray
          state={state}
          label={label}
          dispatch={dispatch}
          fallbackFocus={() =>
            pickerRef.current?.querySelector<HTMLInputElement>(
              "input[type=search]",
            ) ?? doneButton()
          }
        />
        {mode === "manage" ? (
          <>
            <p>Xóa sẽ thay đổi thông tin công khai và gợi ý kết nối.</p>
            <ul className="full-interest-list">
              {(toDraftProfile(state).interests ?? []).map((id) => (
                <li key={id}>
                  <span>{label(id)}</span>
                  <Button
                    variant="text"
                    onClick={(event) => {
                      focusAfterInterestRemoval(
                        event.currentTarget,
                        doneButton(),
                      );
                      dispatch({
                        type: "DELETE_FULL_INTEREST",
                        id,
                        label: label(id),
                      });
                    }}
                    aria-label={`Xóa khỏi hồ sơ: ${label(id)}`}
                  >
                    Xóa khỏi hồ sơ
                  </Button>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <>
            <label className="picker-field">
              Tìm sở thích
              <input
                type="search"
                value={search}
                onChange={(event) => {
                  setSearch(event.target.value);
                  setPage(0);
                }}
              />
            </label>
            <label className="picker-field">
              Nhóm sở thích
              <select
                value={category}
                onChange={(event) => {
                  setCategory(event.target.value);
                  setPage(0);
                  setCompact(false);
                  setSearch("");
                }}
              >
                {Object.keys(taxonomy.categories ?? {}).map((key) => (
                  <option key={key} value={key}>
                    {taxonomy.categoryLabels?.[key] ?? key}
                  </option>
                ))}
              </select>
            </label>
            <p className="tag-hint">{ids.length} kết quả</p>
            <div className="tag-chips picker-results">
              {ids.slice(page * 8, page * 8 + 8).map((id) => (
                <InterestChoice
                  key={id}
                  id={id}
                  label={label(id)}
                  state={state}
                  dispatch={dispatch}
                />
              ))}
            </div>
            {ids.length === 0 && (
              <p>Chưa thấy sở thích này. Thử từ khác nhé.</p>
            )}
            <nav aria-label="Trang sở thích" className="picker-pages">
              <Button
                variant="secondary"
                disabled={page === 0}
                onClick={() => setPage(page - 1)}
              >
                Trước
              </Button>
              <span>
                {page + 1}/{Math.max(1, Math.ceil(ids.length / 8))}
              </span>
              <Button
                variant="secondary"
                disabled={(page + 1) * 8 >= ids.length}
                onClick={() => setPage(page + 1)}
              >
                Sau
              </Button>
            </nav>
          </>
        )}
        <p role="status" aria-atomic="true">
          {state.notice ||
            `${state.featuredInterests.length}/3 sở thích nổi bật`}
        </p>
        <Button data-interest-done onClick={onClose}>
          Xong
        </Button>
      </div>
    </Dialog>
  );
}
