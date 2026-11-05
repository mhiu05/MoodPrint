import type { components } from "../../../api/generated/schema";
import {
  facetValid,
  limitsOf,
  type Profile,
  type Taxonomy,
  type Facet,
} from "./profileRules";

type Schema = components["schemas"];
export type Intention = NonNullable<Schema["FriendshipDiscovery"]["intention"]>;
export type Approach = NonNullable<
  Schema["FriendshipDiscovery"]["connectionApproach"]
>;
export const INTENTIONS: {
  id: Intention;
  icon: string;
  label: string;
  goal: string;
}[] = [
  { id: "talk", icon: "💬", label: "Có người tâm sự", goal: "friendship" },
  {
    id: "shared-interests",
    icon: "🎯",
    label: "Bạn chung sở thích",
    goal: "shared-interests",
  },
  { id: "study", icon: "📚", label: "Bạn cùng học", goal: "study-buddy" },
  {
    id: "experiences",
    icon: "🌿",
    label: "Bạn cùng trải nghiệm",
    goal: "friendship",
  },
];
export const APPROACHES: { id: Approach; icon: string; label: string }[] = [
  { id: "gradual", icon: "🌱", label: "Từ từ làm quen" },
  { id: "lively", icon: "✨", label: "Nói chuyện rôm rả" },
  { id: "activity-first", icon: "🎲", label: "Cùng làm gì đó trước" },
];
export const COMPACT_INTERESTS = [
  ["music", "🎧", "Âm nhạc"],
  ["coffee", "☕", "Cà phê"],
  ["games", "🎮", "Chơi game"],
  ["movies", "🎬", "Xem phim"],
  ["reading", "📚", "Đọc sách"],
  ["travel", "✈️", "Du lịch"],
] as const;
export const INTEREST_GROUPS = {
  creative: ["photography", "drawing", "writing", "crafts", "singing"],
  active: ["walking", "running", "cycling", "yoga", "football", "badminton"],
};
const EMPTY: Profile = {
  interests: [],
  values: [],
  languages: [],
  style: "balanced",
  goal: "friendship",
  activities: [],
  availability: [],
  strictGoal: false,
};
export type Stage = "builder" | "review-preparation" | "review-ready";
export type Operation = "idle" | "saving" | "previewing" | "publishing";
export interface EditorState {
  canonical: Omit<Profile, "interests" | "discovery">;
  intention: Intention | null;
  connectionApproach: Approach | null;
  retainedInterests: string[];
  featuredInterests: string[];
  goalMode: "follow-intention" | "preserve";
  draftVersion: number;
  publishedVersion: number;
  savedSnapshot: string;
  stage: Stage;
  mobileQuestion: 0 | 1 | 2;
  operation: Operation;
  serverPreview: Schema["PreviewView"] | null;
  editRevision: number;
  notice: string;
}
export type EditorAction =
  | { type: "SET_INTENTION"; value: Intention }
  | { type: "SET_APPROACH"; value: Approach }
  | { type: "FEATURE" | "DEFEATURE"; id: string }
  | { type: "DELETE_FULL_INTEREST"; id: string; label?: string }
  | { type: "PATCH_CANONICAL"; patch: Partial<EditorState["canonical"]> }
  | { type: "SET_QUESTION"; question: 0 | 1 | 2 }
  | { type: "SET_STAGE"; stage: Stage }
  | { type: "OPERATION"; operation: Operation }
  | { type: "SAVE_SUCCEEDED"; draft: Schema["DraftView"] }
  | { type: "PREVIEW_SUCCEEDED"; preview: Schema["PreviewView"] }
  | { type: "PREVIEW_INVALIDATED" }
  | {
      type: "HYDRATE";
      draft: Schema["DraftView"];
      published: Schema["PublishedView"] | null;
    };
const unique = (ids: string[]) => [...new Set(ids)];
export function toDraftProfile(state: EditorState): Profile {
  return {
    ...state.canonical,
    interests: unique([...state.retainedInterests, ...state.featuredInterests]),
    discovery: {
      version: 1,
      intention: state.intention,
      connectionApproach: state.connectionApproach,
      featuredInterests: state.featuredInterests,
    },
  };
}
/** Compare wire responses without depending on JSON object property order. */
export function samePublicProfile(a: Profile, b: Profile) {
  const normalize = (profile: Profile) => ({
    ...EMPTY,
    ...profile,
    discovery: profile.discovery
      ? {
          version: profile.discovery.version,
          intention: profile.discovery.intention ?? null,
          connectionApproach: profile.discovery.connectionApproach ?? null,
          featuredInterests: profile.discovery.featuredInterests ?? [],
        }
      : null,
  });
  const stable = (value: unknown): string => {
    if (Array.isArray(value)) return `[${value.map(stable).join(",")}]`;
    if (value && typeof value === "object")
      return `{${Object.entries(value)
        .sort(([x], [y]) => x.localeCompare(y))
        .map(([key, item]) => `${JSON.stringify(key)}:${stable(item)}`)
        .join(",")}}`;
    return JSON.stringify(value) ?? "null";
  };
  return stable(normalize(a)) === stable(normalize(b));
}
const snapshot = (state: EditorState) => JSON.stringify(toDraftProfile(state));
export const isDirty = (state: EditorState) =>
  snapshot(state) !== state.savedSnapshot;
export function hydrateEditor(
  draft?: Schema["DraftView"],
  published?: Schema["PublishedView"] | null,
): EditorState {
  const {
    interests = [],
    discovery,
    ...canonical
  } = { ...EMPTY, ...(draft?.version ? draft.profile : published?.profile) };
  const state: EditorState = {
    canonical,
    retainedInterests: [...interests],
    featuredInterests: [
      ...(discovery?.featuredInterests?.length
        ? discovery.featuredInterests
        : interests.slice(0, 3)),
    ],
    intention: discovery?.intention ?? null,
    connectionApproach: discovery?.connectionApproach ?? null,
    goalMode: draft?.version || published ? "preserve" : "follow-intention",
    draftVersion: draft?.version ?? 0,
    publishedVersion: published?.profileVersion ?? draft?.publishedVersion ?? 0,
    savedSnapshot: "",
    stage: "builder",
    mobileQuestion: 0,
    operation: "idle",
    serverPreview: null,
    editRevision: 0,
    notice: "",
  };
  return { ...state, savedSnapshot: snapshot(state) };
}
function edited(
  state: EditorState,
  patch: Partial<EditorState>,
  notice = "",
): EditorState {
  return {
    ...state,
    ...patch,
    editRevision: state.editRevision + 1,
    notice,
    serverPreview: null,
    stage: state.stage === "review-ready" ? "review-preparation" : state.stage,
  };
}
export function reduceEditor(
  state: EditorState,
  action: EditorAction,
): EditorState {
  switch (action.type) {
    case "HYDRATE":
      return hydrateEditor(action.draft, action.published);
    case "SET_INTENTION":
      return edited(
        state,
        {
          intention: action.value,
          canonical:
            state.goalMode === "follow-intention"
              ? {
                  ...state.canonical,
                  goal: INTENTIONS.find((i) => i.id === action.value)!.goal,
                }
              : state.canonical,
        },
        `Đã chọn ${INTENTIONS.find((i) => i.id === action.value)!.label}.`,
      );
    case "SET_APPROACH":
      return edited(
        state,
        { connectionApproach: action.value },
        `Đã chọn ${APPROACHES.find((i) => i.id === action.value)!.label}.`,
      );
    case "PATCH_CANONICAL":
      return edited(state, {
        canonical: { ...state.canonical, ...action.patch },
        goalMode: action.patch.goal !== undefined ? "preserve" : state.goalMode,
      });
    case "FEATURE": {
      if (state.featuredInterests.includes(action.id)) return state;
      if (state.featuredInterests.length >= 3)
        return {
          ...state,
          notice:
            "Bạn đã chọn 3 sở thích nổi bật. Bỏ một sở thích để chọn thêm nhé.",
        };
      if (
        unique([
          ...state.retainedInterests,
          ...state.featuredInterests,
          action.id,
        ]).length > 10
      )
        return {
          ...state,
          notice:
            "Bạn đã lưu 10 sở thích. Xóa một mục trong “Quản lý sở thích đã lưu” để thêm sở thích mới.",
        };
      return edited(
        state,
        { featuredInterests: [...state.featuredInterests, action.id] },
        `Đã chọn ${state.featuredInterests.length + 1} trên 3 sở thích nổi bật.`,
      );
    }
    case "DEFEATURE":
      return edited(
        state,
        {
          featuredInterests: state.featuredInterests.filter(
            (id) => id !== action.id,
          ),
        },
        `Đã bỏ nổi bật. Còn ${state.featuredInterests.filter((id) => id !== action.id).length} trên 3 sở thích nổi bật.`,
      );
    case "DELETE_FULL_INTEREST":
      return edited(
        state,
        {
          retainedInterests: state.retainedInterests.filter(
            (id) => id !== action.id,
          ),
          featuredInterests: state.featuredInterests.filter(
            (id) => id !== action.id,
          ),
        },
        `Đã xóa ${action.label ?? action.id} khỏi hồ sơ. Còn ${toDraftProfile(state).interests!.filter((id) => id !== action.id).length} sở thích đã lưu.`,
      );
    case "SET_QUESTION":
      return { ...state, mobileQuestion: action.question };
    case "SET_STAGE":
      return { ...state, stage: action.stage, serverPreview: null };
    case "OPERATION":
      return {
        ...state,
        operation: action.operation,
        ...(action.operation === "saving"
          ? {
              serverPreview: null,
              stage:
                state.stage === "review-ready"
                  ? ("review-preparation" as const)
                  : state.stage,
            }
          : {}),
      };
    case "SAVE_SUCCEEDED": {
      const saved = hydrateEditor(action.draft, null);
      // A save response is authoritative, not another initial legacy projection.
      if (action.draft.profile.discovery) {
        saved.featuredInterests = [
          ...(action.draft.profile.discovery.featuredInterests ?? []),
        ];
        saved.savedSnapshot = snapshot(saved);
      }
      return {
        ...saved,
        stage:
          state.stage === "review-ready" ? "review-preparation" : state.stage,
        mobileQuestion: state.mobileQuestion,
        operation: state.operation,
        editRevision: state.editRevision,
      };
    }
    case "PREVIEW_SUCCEEDED":
      return {
        ...state,
        serverPreview: action.preview,
        publishedVersion: state.publishedVersion,
        stage: "review-ready",
        operation: "idle",
      };
    case "PREVIEW_INVALIDATED":
      return {
        ...state,
        serverPreview: null,
        stage: state.stage === "builder" ? "builder" : "review-preparation",
      };
  }
}
export type ReviewIssue = { question: 0 | 1 | 2; text: string };
export function validateReview(state: EditorState): ReviewIssue[] {
  const issues: ReviewIssue[] = [];
  if (!state.intention)
    issues.push({ question: 0, text: "Chọn điều bạn đang tìm kiếm." });
  if (
    !state.featuredInterests.length ||
    toDraftProfile(state).interests!.length < 3
  )
    issues.push({
      question: 1,
      text: "Cần ít nhất 3 sở thích đã lưu trước khi hiển thị hồ sơ. Chọn ít nhất một mục nổi bật.",
    });
  if (!state.connectionApproach)
    issues.push({ question: 2, text: "Chọn cách bạn muốn kết nối." });
  return issues;
}
export function canonicalReady(profile: Profile, taxonomy: Taxonomy) {
  const limits = limitsOf(taxonomy);
  return (Object.keys(limits) as Facet[]).every((facet) =>
    facetValid(profile, facet, limits),
  );
}
export function incompatibleProfile(profile: Profile, taxonomy: Taxonomy) {
  return (
    (
      [
        "interests",
        "values",
        "languages",
        "activities",
        "availability",
      ] as const
    ).some((facet) =>
      (profile[facet] ?? []).some((id) => !taxonomy[facet]?.[id]),
    ) ||
    Boolean(profile.goal && !taxonomy.goals[profile.goal]) ||
    Boolean(profile.style && !taxonomy.styles[profile.style])
  );
}
export function buildPublicProfileView(
  profile: Profile,
  label: (id: string) => string,
  local = false,
) {
  return {
    profile,
    intention: INTENTIONS.find((i) => i.id === profile.discovery?.intention)
      ?.label,
    approach: APPROACHES.find(
      (i) => i.id === profile.discovery?.connectionApproach,
    )?.label,
    featured: (local
      ? (profile.discovery?.featuredInterests ?? [])
      : profile.discovery?.featuredInterests?.length
        ? profile.discovery.featuredInterests
        : (profile.interests ?? []).slice(0, 3)
    ).map(label),
    goal: profile.goal ? label(profile.goal) : "",
    style: profile.style ? label(profile.style) : "",
  };
}
