import { useWorkspaceStore } from "../../app/store";
import type { ProfilePort } from "../ports";
import type { ApiClient } from "./client";
import { commitForOwner, currentOwner, jsonBody } from "./cache";
import { mapUser, serializeAgeBand, type ProfileDTO } from "./mappers";
export function createProfilePort(api: ApiClient): ProfilePort {
  const cache = (owner: string | null, data: ProfileDTO) => {
    const user = mapUser(data);
    commitForOwner(owner, () =>
      useWorkspaceStore.setState({
        user,
        preferences: { reducedMotion: data.reducedMotion ?? false },
      }),
    );
    return { user, reducedMotion: data.reducedMotion ?? false };
  };
  return {
    async get() {
      const owner = currentOwner();
      return cache(owner, await api("/v1/me"));
    },
    async save(patch) {
      const owner = currentOwner();
      return cache(
        owner,
        await api(
          "/v1/me",
          jsonBody("PATCH", {
            ...patch,
            ...(patch.ageBand
              ? { ageBand: serializeAgeBand(patch.ageBand) }
              : {}),
          }),
        ),
      );
    },
    async remove() {
      await api("/v1/me", jsonBody("DELETE", { confirm: "DELETE" }));
    },
  };
}
