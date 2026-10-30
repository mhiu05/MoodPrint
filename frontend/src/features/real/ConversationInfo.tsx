import { useEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { Button } from "../../components/UI";

const DESKTOP = "(min-width: 1100px)";
const TABLET = "(min-width: 768px)";

function useMedia(query: string) {
  const [matches, setMatches] = useState(() => window.matchMedia(query).matches);
  useEffect(() => {
    const media = window.matchMedia(query);
    const change = () => setMatches(media.matches);
    change();
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, [query]);
  return matches;
}

export type ConversationInfoProps = {
  open: boolean;
  /** A dialog opened from the panel is in charge; a compact sheet must not stack over it. */
  suspended?: boolean;
  /** Close; `restoreFocus` returns focus to the trigger (Escape, close button). */
  onClose: (restoreFocus: boolean) => void;
  triggerRef: RefObject<HTMLButtonElement | null>;
  panelId: string;
  title: string;
  botName: string;
  persistent: boolean;
  modeLabel: string;
  retentionLabel: string;
  historyStatus: string;
  pendingProposals: number;
  manageBusy: boolean;
  manageError?: ReactNode;
  newDisabledReason?: string;
  onHistory: () => void;
  onRename: () => void;
  onDelete: () => void;
  onNew: () => void;
};

/** Whether the panel is in the DOM: open, and not suspended behind a child dialog on a compact layout. */
function panelMounted(open: boolean, suspended: boolean | undefined, desktop: boolean) {
  return open && !(suspended && !desktop);
}

/** For the trigger's aria-controls, which may only name a panel that is actually mounted. */
export function useInfoPanelMounted(open: boolean, suspended: boolean | undefined) {
  return panelMounted(open, suspended, useMedia(DESKTOP));
}

/**
 * Secondary conversation details and actions, outside the transcript so opening
 * it never resizes or scrolls the log. Desktop (≥1100px): modeless overlay, no
 * focus trap. Smaller: native modal (420px tablet, full-width phone).
 */
export function ConversationInfo(props: ConversationInfoProps) {
  const desktop = useMedia(DESKTOP);
  const tablet = useMedia(TABLET);
  const mode = desktop ? "desktop" : tablet ? "tablet" : "phone";
  // The entrance plays when the panel opens, not again when a resize swaps the mode.
  const [openedMode, setOpenedMode] = useState<string | null>(null);
  useEffect(() => {
    if (!props.open) setOpenedMode(null);
    else setOpenedMode((value) => value ?? mode);
  }, [props.open, mode]);
  // One media subscription decides both this and the layout below: two could disagree for a frame.
  if (!panelMounted(props.open, props.suspended, desktop)) return null;
  const animate = openedMode === null || openedMode === mode;
  return desktop ? (
    <ModelessPanel {...props} animate={animate} />
  ) : (
    <ModalPanel {...props} animate={animate} mode={tablet ? "tablet" : "phone"} />
  );
}

function usePanelEntrance(ref: RefObject<HTMLElement | null>, animate: boolean, travel: { x?: number; y?: number }) {
  // M08/M09: wrapper transform only (≤24px desktop, ≤16px compact), 260ms, text opaque.
  useGSAP(
    () => {
      if (!animate) return;
      const media = gsap.matchMedia();
      media.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(ref.current, { ...travel, duration: 0.26, ease: "power2.out", clearProps: "transform" });
      });
      return () => media.revert();
    },
    { scope: ref },
  );
}

function ModelessPanel(props: ConversationInfoProps & { animate: boolean }) {
  const ref = useRef<HTMLElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const headingId = useId();
  const { onClose, triggerRef } = props;
  usePanelEntrance(ref, props.animate, { x: 24 });
  useEffect(() => {
    heading.current?.focus();
  }, []);
  useEffect(() => {
    // Clicking elsewhere closes the overlay without taking focus from what was chosen.
    const outside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (ref.current?.contains(target) || triggerRef.current?.contains(target)) return;
      if (target instanceof Element && target.closest("dialog[open]")) return;
      onClose(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [onClose, triggerRef]);
  return (
    <section
      ref={ref}
      id={props.panelId}
      className="conversation-info is-modeless"
      role="region"
      aria-labelledby={headingId}
      onKeyDown={(event) => {
        if (event.key === "Escape" && !event.defaultPrevented) {
          event.preventDefault();
          onClose(true);
        }
      }}
    >
      <InfoHeader headingId={headingId} heading={heading} onClose={() => onClose(true)} />
      <InfoContent {...props} />
    </section>
  );
}

function ModalPanel(props: ConversationInfoProps & { animate: boolean; mode: "tablet" | "phone" }) {
  const ref = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const headingId = useId();
  const closeRef = useRef(props.onClose);
  closeRef.current = props.onClose;
  usePanelEntrance(ref, props.animate, props.mode === "phone" ? { y: 16 } : { x: 16 });
  useEffect(() => {
    const dialog = ref.current!;
    dialog.showModal();
    heading.current?.focus();
    return () => dialog.close();
  }, []);
  return (
    <dialog
      ref={ref}
      id={props.panelId}
      className={`conversation-info is-modal is-${props.mode}`}
      aria-labelledby={headingId}
      onCancel={(event) => {
        event.preventDefault();
        closeRef.current(true);
      }}
      onClick={(event) => {
        if (event.target === event.currentTarget) closeRef.current(true);
      }}
      onKeyDown={(event) => {
        if (event.key !== "Tab") return;
        const nodes = Array.from(
          ref.current!.querySelectorAll<HTMLElement>("button:not(:disabled),a[href],input:not(:disabled),[tabindex='0']"),
        ).filter((node) => node.getClientRects().length > 0);
        const first = nodes[0], last = nodes.at(-1);
        if (event.shiftKey && (document.activeElement === first || document.activeElement === heading.current)) {
          event.preventDefault();
          last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault();
          first?.focus();
        }
      }}
    >
      <InfoHeader headingId={headingId} heading={heading} onClose={() => closeRef.current(true)} />
      <InfoContent {...props} />
    </dialog>
  );
}

function InfoHeader({ headingId, heading, onClose }: { headingId: string; heading: RefObject<HTMLHeadingElement | null>; onClose: () => void }) {
  return (
    <div className="conversation-info-header">
      <h2 id={headingId} ref={heading} tabIndex={-1}>
        Thông tin cuộc trò chuyện
      </h2>
      <Button variant="text" aria-label="Đóng thông tin cuộc trò chuyện" onClick={onClose}>
        <X size={20} />
      </Button>
    </div>
  );
}

function InfoContent(props: ConversationInfoProps) {
  const reasonId = useId();
  return (
    <div className="conversation-info-body">
      <section>
        <h3>Cuộc trò chuyện</h3>
        <p className="conversation-info-title">{props.title}</p>
        <p>
          {props.botName} · <span>{props.modeLabel}</span>
        </p>
      </section>
      <section>
        <h3>Dữ liệu</h3>
        <p>{props.retentionLabel}</p>
      </section>
      <section>
        <h3>Lịch sử</h3>
        <p>{props.historyStatus}</p>
        <div className="conversation-info-actions">
          <Button variant="secondary" onClick={props.onHistory}>Mở lịch sử trò chuyện</Button>
        </div>
      </section>
      {props.persistent ? (
        <section>
          <h3>Quản lý</h3>
          {props.manageError}
          <div className="conversation-info-actions">
            <Button variant="secondary" disabled={props.manageBusy} onClick={props.onRename}>Đổi tên</Button>
            <Button variant="secondary" disabled={props.manageBusy} onClick={props.onDelete}>Xóa cuộc trò chuyện</Button>
          </div>
        </section>
      ) : null}
      <section>
        <h3>Ghi nhớ</h3>
        <p>
          Trợ lý chỉ lưu ghi nhớ sau khi bạn duyệt từng đề xuất.
          {props.pendingProposals > 0 ? ` Có ${props.pendingProposals} đề xuất đang chờ bạn duyệt.` : ""}
        </p>
        <Link to="/memory">Xem đề xuất và ghi nhớ đã duyệt</Link>
      </section>
      <section>
        <Button
          disabled={Boolean(props.newDisabledReason)}
          aria-describedby={props.newDisabledReason ? reasonId : undefined}
          onClick={props.onNew}
        >
          Cuộc trò chuyện mới
        </Button>
        {props.newDisabledReason ? <p id={reasonId} className="conversation-info-note">{props.newDisabledReason}</p> : null}
      </section>
    </div>
  );
}
