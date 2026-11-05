import { useEffect, useRef, useState, type ReactNode } from "react";
import type { buildPublicProfileView } from "./discoveryProfile";

const HUES = [152, 24, 210, 280, 340, 48];
/** Same decorative pair-seed algorithm; never reads account identity. */
export function SeedAvatar({ seed, alias }: { seed: string; alias: string }) {
  const hue = HUES[parseInt(seed.slice(0, 2) || "0", 16) % HUES.length];
  return (
    <span
      className="seed-avatar"
      aria-hidden="true"
      style={{
        background: `hsl(${hue} 38% 88%)`,
        color: `hsl(${hue} 45% 26%)`,
      }}
    >
      {alias.replace("Bạn đồng hành ", "").slice(0, 2).toUpperCase()}
    </span>
  );
}
export function PublicProfileCard({
  view,
  mode,
  label,
  alias = "Bạn",
  avatarSeed = "00",
  heading,
  headingLevel = 3,
  reasons = [],
  matchLabel,
  sharedActivities = [],
  starter,
  children,
  publicationState,
}: {
  view: ReturnType<typeof buildPublicProfileView>;
  mode: "owner-local" | "owner-reviewed" | "peer";
  label: (id: string) => string;
  alias?: string;
  avatarSeed?: string;
  heading?: string;
  headingLevel?: 2 | 3;
  reasons?: string[];
  matchLabel?: "many" | "some";
  sharedActivities?: string[];
  starter?: string;
  children?: ReactNode;
  publicationState?: "live" | "needs_republish" | "stale";
}) {
  const Heading = headingLevel === 2 ? "h2" : "h3";
  const profile = view.profile;
  const owner = mode !== "peer";
  const list = (ids?: string[]) =>
    ids?.length ? ids.map(label).join(" · ") : "Chưa chọn";
  return (
    <article
      className="peer-card public-profile-card"
      aria-label={`Hồ sơ của ${alias}`}
    >
      <header className="peer-card-header">
        <SeedAvatar seed={avatarSeed} alias={alias} />
        <div>
          <Heading tabIndex={-1} data-peer-heading>
            {heading ?? alias}
          </Heading>
          <p className="card-status">
            {owner ? "Đang khám phá bản thân" : view.intention || view.goal}
          </p>
          {matchLabel && (
            <span className="match-label">
              {matchLabel === "many" ? "Nhiều điểm chung" : "Có vài điểm chung"}
            </span>
          )}
        </div>
      </header>
      {owner && (
        <p className="tag-hint">
          Khi kết nối, bạn dùng bí danh riêng cho từng người bạn.
        </p>
      )}
      {reasons.length > 0 && (
        <ul className="reason-chips" aria-label="Điểm chung">
          {reasons.slice(0, 3).map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      )}
      {owner && (
        <dl className="profile-highlights">
          <div>
            <dt>Mình đang tìm</dt>
            <dd>
              {view.intention || "Bạn muốn tìm một người bạn như thế nào?"}
            </dd>
          </div>
          <div>
            <dt>Những điều mình thích</dt>
            <dd>
              {view.featured.length
                ? view.featured.join(" · ")
                : "Sở thích của bạn sẽ hiện ở đây."}
            </dd>
          </div>
          <div>
            <dt>Cách mình kết nối</dt>
            <dd>{view.approach || "Chọn cách làm quen bạn thấy thoải mái."}</dd>
          </div>
        </dl>
      )}
      {starter && (
        <section
          className="conversation-starter"
          aria-label="Gợi ý bắt đầu câu chuyện"
        >
          <p className="starter-label">GỢI Ý BẮT ĐẦU CÂU CHUYỆN</p>
          <p>{starter}</p>
        </section>
      )}
      {children && <div className="peer-card-actions">{children}</div>}
      {owner && (
        <p className="tag-hint">
          {(profile.interests ?? []).length
            ? `Ngoài các mục nổi bật, hồ sơ còn có ${profile.interests!.length} sở thích, giá trị và tùy chọn bạn đã lưu.`
            : "Thông tin bổ sung sẽ được xem lại trước khi hiển thị."}
        </p>
      )}
      <details
        className="public-profile-details"
        open={mode === "owner-reviewed"}
      >
        <summary>
          {owner ? "Thông tin công khai khác" : "Thông tin công khai"}
        </summary>
        <dl className="peer-facts">
          <div>
            <dt>Sở thích</dt>
            <dd>{list(profile.interests)}</dd>
          </div>
          <div>
            <dt>Điều coi trọng</dt>
            <dd>{list(profile.values)}</dd>
          </div>
          <div>
            <dt>Ngôn ngữ</dt>
            <dd>{list(profile.languages)}</dd>
          </div>
          <div>
            <dt>Mục tiêu ghép bạn</dt>
            <dd>{view.goal}</dd>
          </div>
          <div>
            <dt>Cách trò chuyện</dt>
            <dd>{view.style}</dd>
          </div>
          <div>
            <dt>Muốn cùng thử</dt>
            <dd>
              {profile.activities?.length
                ? profile.activities
                    .map(
                      (id) =>
                        `${label(id)}${sharedActivities.includes(id) ? " (cả hai)" : ""}`,
                    )
                    .join(" · ")
                : "Chưa chọn"}
            </dd>
          </div>
          <div>
            <dt>Thời gian rảnh</dt>
            <dd>{list(profile.availability)}</dd>
          </div>
          <div>
            <dt>Cùng mục tiêu</dt>
            <dd>
              {profile.strictGoal
                ? "Chỉ gợi ý người có cùng mục tiêu với mình"
                : "Không bắt buộc"}
            </dd>
          </div>
          {!owner && (
            <>
              <div>
                <dt>Mình đang tìm</dt>
                <dd>{view.intention || view.goal}</dd>
              </div>
              <div>
                <dt>Cách mình kết nối</dt>
                <dd>{view.approach || view.style}</dd>
              </div>
            </>
          )}
        </dl>
      </details>
      {owner && (
        <footer className="profile-privacy">
          {publicationState && (
            <p>
              {publicationState === "live"
                ? "Hồ sơ đang hiển thị vẫn giữ nguyên cho đến khi bạn xác nhận cập nhật."
                : "Hồ sơ đang tạm ẩn. Chỉ hiển thị lại khi bạn xác nhận."}
            </p>
          )}
          <p>Đây chỉ là bản xem trước. Hồ sơ không tự động công khai.</p>
        </footer>
      )}
    </article>
  );
}
/** Sticky only when the complete preview fits; no independent scrolling surface. */
export function ProfilePreviewAside({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLElement>(null);
  const [fits, setFits] = useState(false);
  useEffect(() => {
    const measure = () =>
      setFits(
        window.innerHeight >= 700 &&
          (ref.current?.getBoundingClientRect().height ?? Infinity) <=
            window.innerHeight - 48,
      );
    const observer = new ResizeObserver(measure);
    if (ref.current) observer.observe(ref.current);
    window.addEventListener("resize", measure);
    measure();
    return () => {
      observer.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, []);
  return (
    <aside
      ref={ref}
      className="friendship-preview-aside"
      data-sticky={fits || undefined}
      aria-label="Xem trước hồ sơ"
    >
      {children}
    </aside>
  );
}
