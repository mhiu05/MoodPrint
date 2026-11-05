import type { PromptCapabilities, PromptOptions } from "../../../api/contracts";

export function skillChipLabel(skills: PromptCapabilities["skills"], id: string): string {
  return skills.find(skill => skill.id === id)?.name ?? id;
}

export type SelectionState = { revision: number; options: PromptOptions };
export function normalizePromptOptions(options: PromptOptions): PromptOptions {
  const result: PromptOptions = {};
  if (options.skillId) result.skillId = options.skillId;
  const tools = [...new Set(options.tools ?? [])].sort();
  if (tools.length) result.tools = tools;
  if (options.area?.trim()) result.area = options.area.trim().replace(/\s+/g, " ");
  if (options.mapsSearchId) result.mapsSearchId = options.mapsSearchId;
  return result;
}
export const selectionKey = (options: PromptOptions) => JSON.stringify(normalizePromptOptions(options));
export function acceptSelection(current: SelectionState, submittedRevision: number): SelectionState {
  return current.revision === submittedRevision ? { revision: current.revision + 1, options: {} } : current;
}
