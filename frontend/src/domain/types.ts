import type { BotId, BotThread } from "../companions/registry";
export type Age = "unknown" | "under16" | "teen" | "adult";
export type Permission = "AI" | "MEM" | "MATCH" | "VOICE";
export type Profile = {
  interests: string[];
  values: string[];
  style: string;
  goal: string;
  languages: string[];
  sources: { id: string; version: number }[];
};
export type Published = Profile & { version: number; valid: boolean };
export type PrivateItem = {
  id: string;
  text: string;
  origin: "declared" | "ai";
  status: "proposed" | "confirmed" | "edited" | "rejected" | "deleted";
  version: number;
  memoryApproved: boolean;
};
export type Mood = {
  id: string;
  date: string;
  value: number;
  note: string;
  version: number;
  time: number;
};
export type Identity = {
  displayName: string;
  gender: string;
  displayNameVersion: number;
  genderVersion: number;
};
export type Candidate = {
  id: string;
  alias: string;
  color: string;
  profile: Profile;
  version: number;
  consentVersion: number;
  allowed: boolean;
  identity: Identity;
};
export type Request = {
  id: string;
  candidateId: string;
  direction: "in" | "out";
  status:
    | "pending"
    | "accepted"
    | "cancelled"
    | "declined"
    | "expired"
    | "invalidated";
  profileVersion: number;
  matchVersion: number;
  peerVersion: number;
  peerConsentVersion: number;
  created: number;
  expires: number;
};
export type Message = {
  id: string;
  actor: "self" | "peer" | "ai";
  text: string;
  scripted: boolean;
  at: number;
};
export type Connection = {
  id: string;
  candidateId: string;
  status: "open" | "closed" | "blocked";
  profileVersion: number;
  matchVersion: number;
  peerVersion: number;
  peerConsentVersion: number;
  selfAccepted: boolean;
  peerAccepted: boolean;
  messages: Message[];
  pending?: string;
  replyTurn: number;
};
export type Reveal = {
  id: string;
  connectionId: string;
  field: "displayName" | "gender";
  owner: "self" | "peer";
  recipient: "self" | "peer";
  fieldVersion: number;
  status: "pending" | "granted" | "declined" | "revoked" | "expired";
  expires: number;
  cooldown: number;
};
export type Activity = {
  id: string;
  connectionId: string;
  activityId: "ACT01";
  status:
    "pending" | "active" | "declined" | "cancelled" | "stopped" | "completed";
  selfAccepted: boolean;
  peerAccepted: boolean;
  step: number;
  answers: (string | null)[];
  reply?: string;
  pending?: string;
  feedback?: string;
};
export type Token = {
  epoch: number;
  ai: number;
  voice: number;
  match: number;
  profile: number;
  peer: number;
  peerConsent: number;
};
export type Job = {
  id: string;
  scope: string;
  delay: number;
  token: Token;
  event: Action;
};
export type State = {
  bots: Record<BotId, BotThread>;
  epoch: number;
  age: Age;
  ready: boolean;
  clock: number;
  seq: number;
  fixtureId: string;
  consent: Record<Permission, boolean>;
  versions: Record<Permission, number>;
  draft: Profile;
  published?: Published;
  profileVersion: number;
  privateItems: PrivateItem[];
  moods: Mood[];
  candidates: Candidate[];
  ai: {
    messages: Message[];
    scenario: string;
    turn: number;
    pending?: string;
    error: boolean;
    last?: string;
    voice: "idle" | "loading" | "draft" | "error";
    transcript: string;
  };
  requests: Request[];
  connections: Connection[];
  reveals: Reveal[];
  activities: Activity[];
  blocked: string[];
  cooldowns: Record<string, number>;
  identities: {
    displayName: string;
    gender: string;
    displayNameVersion: number;
    genderVersion: number;
  };
  reports: {
    id: string;
    candidateId: string;
    reason: string;
    evidence: string[];
    key: string;
  }[];
  jobs: Job[];
  errorOnce: boolean;
  outcome: "reply" | "silent";
  notice: string;
};
export type Action = {
  botId?: BotId;
  type: string;
  epoch?: number;
  token?: Token;
  id?: string;
  candidateId?: string;
  connectionId?: string;
  key?: string;
  text?: string;
  value?: number;
  date?: string;
  permission?: Permission;
  on?: boolean;
  age?: Age;
  permissions?: Record<Permission, boolean>;
  profile?: Profile;
  field?: "displayName" | "gender";
  owner?: "self" | "peer";
  outcome?: string;
  reason?: string;
  evidence?: string[];
  days?: number;
  step?: number;
  activityId?: string;
  preset?: string;
};
