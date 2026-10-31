import { useState, type Dispatch } from "react";
import { TagPicker } from "./TagPicker";
import { limitsOf, type Taxonomy } from "./profileRules";
import {
  toDraftProfile,
  type EditorState,
  type EditorAction,
} from "./discoveryProfile";

export function ProfilePublishReview({
  state,
  dispatch,
  taxonomy,
}: {
  state: EditorState;
  dispatch: Dispatch<EditorAction>;
  taxonomy: Taxonomy;
}) {
  const profile = toDraftProfile(state);
  const limits = limitsOf(taxonomy);
  const missingValues = (profile.values?.length ?? 0) < limits.values[0];
  const missingLanguages =
    (profile.languages?.length ?? 0) < limits.languages[0];
  // Keep the supplement mounted while the member completes it (including focus).
  const [showSupplement] = useState(missingValues || missingLanguages);
  const patch = (change: Partial<EditorState["canonical"]>) =>
    dispatch({ type: "PATCH_CANONICAL", patch: change });
  const values = (
    <TagPicker
      legend="Chọn 2 điều bạn coi trọng ở một người bạn"
      hint="Chọn 2–4 giá trị công khai."
      options={taxonomy.values}
      value={profile.values ?? []}
      limits={limits.values}
      onChange={(values) => patch({ values })}
    />
  );
  const languages = (
    <TagPicker
      legend="Ngôn ngữ trò chuyện"
      hint="Chọn 1–2 ngôn ngữ công khai."
      options={taxonomy.languages}
      value={profile.languages ?? []}
      limits={limits.languages}
      onChange={(languages) => patch({ languages })}
    />
  );
  return (
    <fieldset className="review-settings" disabled={state.operation !== "idle"}>
      <legend className="sr-only">Thông tin bổ sung trước khi hiển thị</legend>
      <h2 tabIndex={-1} id="friendship-review-heading">
        Xem lại thông tin chia sẻ
      </h2>
      {showSupplement && (
        <section aria-label="Bổ sung để ghép bạn chính xác hơn">
          <h3>Bổ sung để ghép bạn chính xác hơn</h3>
          <p>
            Những lựa chọn này là thông tin công khai và dùng để gợi ý kết nối.
          </p>
          {values}
          {languages}
        </section>
      )}
      <p className="tag-hint">
        Mục tiêu ghép bạn: {taxonomy.goals[profile.goal ?? "friendship"]}. Cách
        trò chuyện dùng để ghép bạn:{" "}
        {taxonomy.styles[profile.style ?? "balanced"]}
        {state.goalMode === "follow-intention" && profile.style === "balanced"
          ? " (mặc định, có thể đổi)"
          : ""}
        .
      </p>
      <details>
        <summary>Tùy chọn ghép bạn đã lưu</summary>
        {!showSupplement && (
          <>
            {values}
            {languages}
          </>
        )}
        {(
          [
            ["goal", "Mục tiêu kết nối", taxonomy.goals],
            ["style", "Cách trò chuyện", taxonomy.styles],
          ] as const
        ).map(([key, text, options]) => (
          <fieldset className="tag-picker" key={key}>
            <legend>{text}</legend>
            <div className="tag-chips">
              {Object.entries(options).map(([id, name]) => (
                <label
                  key={id}
                  className="tag-chip"
                  data-checked={profile[key] === id || undefined}
                >
                  <input
                    type="radio"
                    name={`canonical-${key}`}
                    checked={profile[key] === id}
                    onChange={() => patch({ [key]: id })}
                  />
                  {name}
                </label>
              ))}
            </div>
          </fieldset>
        ))}
        <label className="strict-goal">
          <input
            type="checkbox"
            checked={Boolean(profile.strictGoal)}
            onChange={(event) => patch({ strictGoal: event.target.checked })}
          />
          Chỉ gợi ý người có cùng mục tiêu với mình
        </label>
        <TagPicker
          legend="Hoạt động muốn thử cùng nhau"
          hint="Không bắt buộc, được chia sẻ công khai."
          options={taxonomy.activities}
          value={profile.activities ?? []}
          limits={limits.activities}
          onChange={(activities) => patch({ activities })}
        />
        <TagPicker
          legend="Thời gian bạn hay rảnh"
          hint="Không bắt buộc, được chia sẻ công khai."
          options={taxonomy.availability}
          value={profile.availability ?? []}
          limits={limits.availability}
          onChange={(availability) => patch({ availability })}
        />
      </details>
    </fieldset>
  );
}
