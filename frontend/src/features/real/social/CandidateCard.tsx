import type { ReactNode } from "react";
import { Button } from "../../../components/UI";
import type { components } from "../../../api/generated/schema";
import "./social.css";

type Schema = components["schemas"];
type Profile = Schema["PublicProfile"];

const LABELS = { many: "Nhiều điểm chung", some: "Có vài điểm chung" } as const;
const HUES = [152, 24, 210, 280, 340, 48];

/** Decorative avatar derived from the pair seed; carries no identity. */
export function SeedAvatar({ seed, alias }: { seed: string; alias: string }) {
  const hue = HUES[parseInt(seed.slice(0, 2) || "0", 16) % HUES.length];
  return (
    <span
      className="seed-avatar"
      aria-hidden="true"
      style={{ background: `hsl(${hue} 38% 88%)`, color: `hsl(${hue} 45% 26%)` }}
    >
      {alias.replace("Bạn đồng hành ", "").slice(0, 2).toUpperCase()}
    </span>
  );
}

/** Public card shown in suggestions, requests and the editor preview. No numbers, ever. */
export function PeerCard({
  alias,
  avatarSeed,
  profile,
  reasons,
  matchLabel,
  sharedActivities = [],
  label,
  heading,
  headingLevel = 3,
  children,
}: {
  alias: string;
  avatarSeed: string;
  profile: Profile;
  reasons?: string[];
  matchLabel?: "many" | "some";
  sharedActivities?: string[];
  label: (key: string) => string;
  heading?: string;
  headingLevel?: 2 | 3;
  children?: ReactNode;
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const activities = profile.activities ?? [];
  return (
    <article className="peer-card" aria-label={`Hồ sơ của ${alias}`}>
      <header className="peer-card-header">
        <SeedAvatar seed={avatarSeed} alias={alias} />
        <div>
          <Heading>{heading ?? alias}</Heading>
          {matchLabel && <span className="match-label">{LABELS[matchLabel]}</span>}
        </div>
      </header>
      {reasons && reasons.length > 0 && (
        <ul className="reason-chips" aria-label="Điểm chung">
          {reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
      <dl className="peer-facts">
        <div>
          <dt>Sở thích</dt>
          <dd>{(profile.interests ?? []).map(label).join(" · ")}</dd>
        </div>
        <div>
          <dt>Giá trị</dt>
          <dd>{(profile.values ?? []).map(label).join(" · ")}</dd>
        </div>
        <div>
          <dt>Trò chuyện</dt>
          <dd>
            {[profile.style, profile.goal, ...(profile.languages ?? [])]
              .filter(Boolean)
              .map((key) => label(key!))
              .join(" · ")}
          </dd>
        </div>
        {activities.length > 0 && (
          <div>
            <dt>Muốn thử</dt>
            <dd>
              {activities
                .map((key) =>
                  sharedActivities.includes(key) ? `${label(key)} (cả hai)` : label(key),
                )
                .join(" · ")}
            </dd>
          </div>
        )}
        {(profile.availability ?? []).length > 0 && (
          <div>
            <dt>Hay rảnh</dt>
            <dd>{(profile.availability ?? []).map(label).join(" · ")}</dd>
          </div>
        )}
      </dl>
      {children && <div className="peer-card-actions">{children}</div>}
    </article>
  );
}

type Card = Schema["CandidateCardDTO"];

/** A suggestion with its actions; the overflow keeps blocking one step away. */
export function CandidateCard({
  card,
  label,
  busy,
  sent,
  onGreet,
  onSkip,
  onBlock,
}: {
  card: Card;
  label: (key: string) => string;
  busy: boolean;
  sent: boolean;
  onGreet: () => void;
  onSkip: () => void;
  onBlock: () => void;
}) {
  return (
    <PeerCard
      alias={card.alias}
      avatarSeed={card.avatarSeed}
      profile={card.profile}
      reasons={card.reasons}
      matchLabel={card.matchLabel}
      sharedActivities={card.sharedActivities}
      label={label}
    >
      {sent ? (
        <p role="status" className="peer-card-sent">
          Đã gửi lời mời kết nối
        </p>
      ) : (
        <>
          <Button disabled={busy} onClick={onGreet}>
            Gửi lời mời kết nối
          </Button>
          <Button variant="secondary" disabled={busy} onClick={onSkip}>
            Bỏ qua
          </Button>
        </>
      )}
      <Button variant="text" disabled={busy} onClick={onBlock}>
        Chặn
      </Button>
    </PeerCard>
  );
}
