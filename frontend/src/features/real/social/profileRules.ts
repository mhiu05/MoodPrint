import type { components } from "../../../api/generated/schema";

type Schema = components["schemas"];
export type Profile = Schema["PublicProfile"];
export type Taxonomy = Schema["TaxonomyDTO"];
export type Facet =
  | "interests"
  | "values"
  | "languages"
  | "activities"
  | "availability";
export type Limits = Record<Facet, [number, number]>;

export const STEPS = [
  { id: "interests", title: "Sở thích" },
  { id: "values", title: "Giá trị" },
  { id: "style", title: "Cách trò chuyện & mục tiêu" },
  { id: "activities", title: "Hoạt động & thời gian" },
  { id: "preview", title: "Xem trước" },
] as const;
export type StepId = (typeof STEPS)[number]["id"];

const FALLBACK: Limits = {
  interests: [3, 10],
  values: [2, 4],
  languages: [1, 2],
  activities: [0, 4],
  availability: [0, 6],
};

export function limitsOf(taxonomy?: Pick<Taxonomy, "limits">): Limits {
  const limits = { ...FALLBACK };
  for (const facet of Object.keys(FALLBACK) as Facet[]) {
    const value = taxonomy?.limits?.[facet];
    if (value && value.length === 2) limits[facet] = [value[0], value[1]];
  }
  return limits;
}

export function selected(profile: Profile, facet: Facet): string[] {
  return profile[facet] ?? [];
}

export function facetValid(profile: Profile, facet: Facet, limits: Limits) {
  const [low, high] = limits[facet];
  const count = selected(profile, facet).length;
  return count >= low && count <= high;
}

/** Whether the user may leave `step` going forward (minimums and maximums met). */
export function canAdvance(step: StepId, profile: Profile, limits: Limits) {
  switch (step) {
    case "interests":
      return facetValid(profile, "interests", limits);
    case "values":
      return facetValid(profile, "values", limits);
    case "style":
      return Boolean(profile.style && profile.goal) && facetValid(profile, "languages", limits);
    case "activities":
      return (
        facetValid(profile, "activities", limits) &&
        facetValid(profile, "availability", limits)
      );
    case "preview":
      return (Object.keys(limits) as Facet[]).every((facet) =>
        facetValid(profile, facet, limits),
      );
  }
}

/** Counter shown under each picker, e.g. "Đã chọn 2 · cần ít nhất 3". */
export function counterText(count: number, [low, high]: [number, number]) {
  if (count < low) return `Đã chọn ${count} · cần ít nhất ${low}`;
  return low > 0 ? `Đã chọn ${count}/${high}` : `Đã chọn ${count} (không bắt buộc, tối đa ${high})`;
}

/** Adds or removes a tag without ever exceeding the facet maximum. */
export function toggle(list: string[], value: string, max: number) {
  if (list.includes(value)) return list.filter((item) => item !== value);
  return list.length >= max ? list : [...list, value];
}
