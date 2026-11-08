import { useWorkspaceStore } from "../app/store";
import type { AuthPort, Services } from "./ports";
import { getSupabase } from "./supabase";
import { createAuthPort } from "./http/auth";
import { createApiClient, type StreamClient } from "./http/client";
import { createCasePort } from "./http/incidents";
import { createEvidencePort } from "./http/evidence";
import { createPlanPort } from "./http/plans";
import { createProfilePort } from "./http/profile";
import {
  createContactPort,
  createKnowledgeStatePort,
  createSupportPort,
} from "./http/personal";
import { createMockServices } from "./mock";
import { createChatPort, createCompanionService } from "./composition/chat";
import { createAnalysisPort } from "./composition/analysis";
import { createRoleplayPort } from "./composition/roleplay";
import {
  createKnowledgeCatalogPort,
  createKnowledgeSearchPort,
} from "./composition/knowledge";
import { preserveExpiredSession } from "./session-reset";
const auth = createAuthPort();
const api = createApiClient({
  getIdentity: () => useWorkspaceStore.getState().workspace.userId,
  baseUrl: import.meta.env.VITE_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000",
  async getToken() {
    const { data, error } = await getSupabase().auth.getSession();
    if (error) throw error;
    return data.session?.access_token ?? null;
  },
  async refreshToken() {
    const { data, error } = await getSupabase().auth.refreshSession();
    return error ? null : (data.session?.access_token ?? null);
  },
  onUnauthenticated() {
    preserveExpiredSession();
    window.dispatchEvent(new Event("moodprint:unauthenticated"));
  },
});
export function createRealServices(
  client: StreamClient,
  authPort: AuthPort = auth,
): Services {
  return {
    auth: authPort,
    profile: createProfilePort(client),
    cases: createCasePort(client),
    evidence: createEvidencePort(client),
    plans: createPlanPort(client),
    contacts: createContactPort(client),
    support: createSupportPort(client),
    knowledgeState: createKnowledgeStatePort(client),
    knowledgeCatalog: createKnowledgeCatalogPort,
    knowledgeSearch: createKnowledgeSearchPort(client),
    companion: createCompanionService(client),
    chat: createChatPort,
    analysis: createAnalysisPort,
    roleplay: createRoleplayPort,
    voice: { simulated: true },
    run: async (work) => work(),
  };
}
const real = createRealServices(api);
const demo = createMockServices(auth);
export function getServices(): Services {
  return useWorkspaceStore.getState().workspace.kind === "real" ? real : demo;
}
