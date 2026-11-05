import type { ComponentProps } from "react";
import { Button } from "../../../components/UI";
import type { components } from "../../../api/generated/schema";
import { PublicProfileCard } from "./PublicProfileCard";
import { buildPublicProfileView } from "./discoveryProfile";
import { selectConversationStarter } from "./conversationStarters";
import type { Taxonomy } from "./profileRules";
import "./social.css";

export { SeedAvatar } from "./PublicProfileCard";
type Schema = components["schemas"];
/** Compatibility wrapper preserves request-card heading levels and action slots. */
export function PeerCard({
  profile,
  label,
  ...props
}: Omit<ComponentProps<typeof PublicProfileCard>, "mode" | "view"> & {
  profile: Schema["PublicProfile"];
}) {
  return (
    <PublicProfileCard
      {...props}
      view={buildPublicProfileView(profile, label)}
      mode="peer"
      label={label}
    />
  );
}
export function CandidateCard({
  card,
  label,
  taxonomy,
  busy,
  sent,
  onGreet,
  onSkip,
  onBlock,
  error,
  onReload,
}: {
  card: Schema["CandidateCardDTO"];
  label: (id: string) => string;
  taxonomy?: Taxonomy;
  busy: boolean;
  sent: boolean;
  onGreet: () => void;
  onSkip: () => void;
  onBlock: () => void;
  error?: string;
  onReload?: () => void;
}) {
  const starter = selectConversationStarter(
    card,
    taxonomy ?? { interests: {} },
  );
  return (
    <PeerCard
      alias={card.alias}
      avatarSeed={card.avatarSeed}
      profile={card.profile}
      label={label}
      reasons={card.reasons}
      matchLabel={card.matchLabel}
      sharedActivities={card.sharedActivities}
      starter={starter.text}
    >
      {sent ? (
        <p role="status" className="peer-card-sent">
          Đã gửi lời mời kết nối
        </p>
      ) : (
        <>
          <Button disabled={busy || Boolean(onReload)} onClick={onGreet}>
            Gửi lời mời kết nối
          </Button>
          <Button
            variant="secondary"
            disabled={busy || Boolean(onReload)}
            onClick={onSkip}
          >
            Bỏ qua
          </Button>
        </>
      )}
      <Button
        variant="text"
        disabled={busy || Boolean(onReload)}
        onClick={onBlock}
      >
        Chặn
      </Button>
      {error && <p role="alert">{error}</p>}
      {onReload && (
        <Button variant="secondary" onClick={onReload}>
          Tải lại gợi ý
        </Button>
      )}
    </PeerCard>
  );
}
