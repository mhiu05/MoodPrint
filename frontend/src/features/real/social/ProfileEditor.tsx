import { useEffect, useRef, useState } from "react";
import { Button, cx } from "../../../components/UI";
import type { components } from "../../../api/generated/schema";
import { ErrorNotice, useSession } from "../RealApp";
import { PeerCard } from "./CandidateCard";
import { TagPicker } from "./TagPicker";
import {
  STEPS,
  canAdvance,
  limitsOf,
  type Profile,
  type Taxonomy,
} from "./profileRules";
import "./social.css";

type Schema = components["schemas"];
type Draft = Schema["DraftView"];
type Preview = Schema["PreviewView"];
type Published = Schema["PublishedView"];

const EMPTY: Profile = {
  interests: [],
  values: [],
  style: "balanced",
  goal: "friendship",
  languages: [],
  activities: [],
  availability: [],
  strictGoal: false,
};

/**
 * Five-step matching profile editor. Only these public choices are ever shared; the
 * last step shows exactly the card other members will see (server preview) before
 * publishing. Private notes, moods and AI conversations are never inputs.
 */
export function ProfileEditor({
  taxonomy,
  draft,
  published,
  onDraft,
  onPublished,
  onClose,
}: {
  taxonomy: Taxonomy;
  draft?: Draft;
  published?: Published | null;
  onDraft: (draft: Draft) => void;
  onPublished: (published: Published) => void;
  onClose: () => void;
}) {
  const { api } = useSession();
  const limits = limitsOf(taxonomy);
  const [profile, setProfile] = useState<Profile>(() => ({
    ...EMPTY,
    ...(draft?.version ? draft.profile : published?.profile),
  }));
  const [step, setStep] = useState(0);
  const [preview, setPreview] = useState<Preview>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  const [notice, setNotice] = useState("");
  const heading = useRef<HTMLHeadingElement>(null);
  const current = STEPS[step];
  useEffect(() => {
    heading.current?.focus();
  }, [step]);
  const label = (key: string) =>
    ({
      ...taxonomy.interests,
      ...taxonomy.values,
      ...taxonomy.styles,
      ...taxonomy.goals,
      ...taxonomy.languages,
      ...taxonomy.activities,
      ...taxonomy.availability,
    })[key] || key;
  const change = (next: Partial<Profile>) => {
    setPreview(undefined);
    setNotice("");
    setProfile((value) => ({ ...value, ...next }));
  };

  async function run(action: () => Promise<void>) {
    if (busy) return;
    setBusy(true);
    setError(undefined);
    try {
      await action();
    } catch (reason) {
      setError(reason);
    } finally {
      setBusy(false);
    }
  }
  async function saveDraft() {
    const saved = await api.request<Draft>("/profiles/matching-draft", {
      method: "PUT",
      body: {
        ...profile,
        expectedVersion: draft?.version || 0,
      } satisfies Schema["DraftInput"],
    });
    onDraft(saved);
    setNotice("Đã lưu bản nháp.");
    return saved;
  }
  async function toPreview() {
    await saveDraft();
    setPreview(
      await api.request<Preview>("/profiles/matching-draft/preview", {
        method: "POST",
      }),
    );
    setStep(STEPS.length - 1);
  }
  async function publish() {
    if (!preview) return;
    const result = await api.request<Published>("/profiles/published", {
      method: "POST",
      body: {
        draftVersion: preview.draftVersion,
        previewDigest: preview.previewDigest,
        expectedPublishedVersion:
          published?.profileVersion ?? draft?.publishedVersion ?? 0,
      } satisfies Schema["PublishInput"],
    });
    onPublished(result);
  }

  const next = () => {
    if (step === STEPS.length - 2) void run(toPreview);
    else setStep((value) => value + 1);
  };
  const categories = Object.entries(taxonomy.categories ?? {}).map(
    ([key, tags]) =>
      [taxonomy.categoryLabels?.[key] ?? key, tags] as [string, string[]],
  );

  return (
    <section className="real-section profile-editor" aria-label="Hồ sơ kết nối">
      <ol className="editor-steps" aria-label="Các bước">
        {STEPS.map((item, index) => (
          <li key={item.id} aria-current={index === step ? "step" : undefined}>
            <button
              type="button"
              disabled={
                busy ||
                index === STEPS.length - 1 ||
                STEPS.slice(0, index).some((s) => !canAdvance(s.id, profile, limits))
              }
              onClick={() => setStep(index)}
            >
              <span aria-hidden="true">{index + 1}</span>
              {item.title}
            </button>
          </li>
        ))}
      </ol>
      <h2 ref={heading} tabIndex={-1}>
        Bước {step + 1}/{STEPS.length}: {current.title}
      </h2>
      {current.id === "interests" && (
        <TagPicker
          legend="Bạn thích làm gì?"
          hint="Chọn 3–10 điều bạn muốn trò chuyện cùng người khác."
          options={taxonomy.interests}
          groups={categories.length ? categories : undefined}
          value={profile.interests ?? []}
          limits={limits.interests}
          onChange={(interests) => change({ interests })}
        />
      )}
      {current.id === "values" && (
        <TagPicker
          legend="Điều bạn coi trọng ở một người bạn"
          hint="Chọn 2–4 giá trị."
          options={taxonomy.values}
          value={profile.values ?? []}
          limits={limits.values}
          onChange={(values) => change({ values })}
        />
      )}
      {current.id === "style" && (
        <>
          {(
            [
              ["style", "Cách trò chuyện", taxonomy.styles],
              ["goal", "Bạn đang tìm kiếm", taxonomy.goals],
            ] as const
          ).map(([kind, title, options]) => (
            <fieldset className="tag-picker" key={kind}>
              <legend>{title}</legend>
              <div className="tag-chips">
                {Object.entries(options).map(([value, name]) => (
                  <label className="tag-chip" key={value} data-checked={profile[kind] === value || undefined}>
                    <input
                      type="radio"
                      name={kind}
                      checked={profile[kind] === value}
                      onChange={() => change({ [kind]: value })}
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
              onChange={(event) => change({ strictGoal: event.target.checked })}
            />
            Chỉ gợi ý người có cùng mục tiêu với mình
          </label>
          <TagPicker
            legend="Ngôn ngữ trò chuyện"
            options={taxonomy.languages}
            value={profile.languages ?? []}
            limits={limits.languages}
            onChange={(languages) => change({ languages })}
          />
        </>
      )}
      {current.id === "activities" && (
        <>
          <TagPicker
            legend="Hoạt động muốn thử cùng nhau"
            hint="Không bắt buộc. Giúp gợi ý người muốn làm cùng một điều."
            options={taxonomy.activities}
            value={profile.activities ?? []}
            limits={limits.activities}
            onChange={(activities) => change({ activities })}
          />
          <TagPicker
            legend="Thời gian bạn hay rảnh"
            hint="Không bắt buộc."
            options={taxonomy.availability}
            value={profile.availability ?? []}
            limits={limits.availability}
            onChange={(availability) => change({ availability })}
          />
        </>
      )}
      {current.id === "preview" && preview && (
        <>
          <p>Người khác chỉ thấy đúng thẻ này. Ghi chép riêng, cảm xúc và hội thoại với trợ lý không bao giờ được đưa vào.</p>
          <PeerCard
            alias="Bạn"
            avatarSeed="00"
            profile={preview.profile}
            label={label}
            heading="Thẻ hồ sơ của bạn"
          />
          {published && (
            <p className={cx.note}>
              Các kết nối hiện có vẫn được giữ. Hồ sơ mới chỉ thay đổi những gợi ý bạn
              nhận được.
            </p>
          )}
        </>
      )}
      <ErrorNotice error={error} />
      {notice && <p role="status">{notice}</p>}
      <div className={cx.actions}>
        {step > 0 && (
          <Button variant="secondary" disabled={busy} onClick={() => setStep(step - 1)}>
            Quay lại
          </Button>
        )}
        {current.id !== "preview" ? (
          <Button disabled={busy || !canAdvance(current.id, profile, limits)} onClick={next}>
            {step === STEPS.length - 2 ? "Xem trước hồ sơ" : "Tiếp tục"}
          </Button>
        ) : (
          <Button disabled={busy || !preview} onClick={() => void run(publish)}>
            Xuất bản hồ sơ
          </Button>
        )}
        <Button variant="text" disabled={busy} onClick={() => void run(async () => void (await saveDraft()))}>
          Lưu bản nháp
        </Button>
        <Button variant="text" disabled={busy} onClick={onClose}>
          Đóng
        </Button>
      </div>
    </section>
  );
}
