import type { components, operations } from "./generated/schema";

export type ConsentPurpose =
  operations["update_consent_api_v1_consents__purpose__put"]["parameters"]["path"]["purpose"];
export type SessionView = components["schemas"]["SessionView"];
export type BotPublicDTO = components["schemas"]["BotPublicDTO"];
export type ConversationHeader = components["schemas"]["ConversationHeader"];
export type ConversationView = components["schemas"]["ConversationView"];
export type AIRunAccepted = components["schemas"]["AIRunAccepted"];
export type MoodDTO = components["schemas"]["MoodDTO"];
export type PrivateItemDTO = components["schemas"]["PrivateItemDTO"];
export type ActionReceipt = components["schemas"]["ActionReceipt"];
export type LoginInput = components["schemas"]["LoginInput"];
export type ConsentInput = components["schemas"]["ConsentInput"];
export type ConversationInput = components["schemas"]["ConversationInput"];
export type StartRunInput = components["schemas"]["StartRunInput"];
export type MoodInput = components["schemas"]["MoodInput"];
export type PrivateItemInput = components["schemas"]["PrivateItemInput"];
export type PrivateItemEdit = components["schemas"]["PrivateItemEdit"];
export type VersionInput = components["schemas"]["VersionInput"];
export type AiOutput = components["schemas"]["AiOutput"];
export type AICard = NonNullable<AiOutput["cards"]>[number];
