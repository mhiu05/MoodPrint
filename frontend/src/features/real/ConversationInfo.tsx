import { useEffect, useLayoutEffect, useId, useRef, useState, type ReactNode, type RefObject } from "react";
import { Link } from "react-router-dom";
import { X } from "lucide-react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { Button } from "../../components/UI";
import type { BotId } from "../../companions/registry";
import "./conversation-info.css";

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
  botId: BotId;
  botDescription?: string;
  agentSettings?: ReactNode;
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

/** Whether the panel is visible; suspended compact DOM stays mounted to retain child editors. */
function panelMounted(open: boolean, suspended: boolean | undefined, _desktop: boolean) {
  return open && !suspended;
}

/** For the trigger's aria-controls, which only names the currently visible panel. */
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
  if (!props.open) return null;
  const animate = openedMode === null || openedMode === mode;
  // One stable host preserves draft editor state, portals and focus across breakpoint changes.
  return <InfoPanel {...props} animate={animate} mode={mode} desktop={desktop} />;
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

export function infoFocusables(root: HTMLElement) {
  return Array.from(root.querySelectorAll<HTMLElement>(
    "button:not(:disabled),a[href],input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex='0']",
  )).filter((node) => node.getClientRects().length > 0);
}

function InfoPanel(props: ConversationInfoProps & { animate: boolean; mode: string; desktop: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const headingId = useId();
  const lastFocused = useRef<HTMLElement | null>(null);
  const { onClose, triggerRef, desktop, suspended } = props;
  usePanelEntrance(ref, props.animate, props.mode === "phone" ? { y: 16 } : { x: desktop ? 24 : 16 });
  useLayoutEffect(() => {
    const dialog = ref.current!;
    const before = document.activeElement as HTMLElement | null;
    const retainedFocus = before && dialog.contains(before);
    if (retainedFocus) lastFocused.current = before;
    // Native modal state must be closed before changing between modal and modeless.
    dialog.close();
    if (suspended) return;
    if (desktop) dialog.show();
    else dialog.showModal();
    if (!suspended) {
      const target = retainedFocus ? before : lastFocused.current;
      if (target?.isConnected && dialog.contains(target)) {
        target.focus();
        // A closing child dialog restores focus in its passive cleanup, after this layout
        // effect. Return to the panel action once that cleanup has finished.
        requestAnimationFrame(() => { if (dialog.open && !dialog.hidden && target.isConnected) target.focus(); });
      } else heading.current?.focus();
    }
  }, [desktop, suspended]);
  useEffect(() => {
    const dialog = ref.current!;
    return () => dialog.close();
  }, []);
  useEffect(() => {
    if (!desktop || suspended) return;
    const outside = (event: PointerEvent) => {
      const target = event.target as Node;
      if (ref.current?.contains(target) || triggerRef.current?.contains(target)) return;
      if (target instanceof Element && target.closest("dialog[open]")) return;
      onClose(false);
    };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [desktop, suspended, onClose, triggerRef]);
  return (
    <dialog
      ref={ref}
      id={props.panelId}
      data-bot-id={props.botId}
      hidden={suspended || undefined}
      className={`conversation-info ${desktop ? "is-modeless" : `is-modal is-${props.mode}`}`}
      role={desktop ? "region" : undefined}
      aria-labelledby={headingId}
      onCancel={(event) => {
        if (event.target !== event.currentTarget) return;
        event.preventDefault(); onClose(true);
      }}
      onClick={(event) => {
        if (!desktop && event.target === event.currentTarget) onClose(true);
      }}
      onKeyDown={(event) => {
        // Portaled child dialogs own their own Escape and Tab events.
        if (!ref.current?.contains(event.target as Node)) return;
        if (desktop) {
          if (event.key === "Escape" && !event.defaultPrevented) { event.preventDefault(); onClose(true); }
          return;
        }
        if (event.key !== "Tab") return;
        const nodes = infoFocusables(ref.current);
        const first = nodes[0], last = nodes.at(-1);
        if (event.shiftKey && (document.activeElement === first || document.activeElement === heading.current)) {
          event.preventDefault(); last?.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first?.focus();
        }
      }}
    >
      <InfoHeader headingId={headingId} heading={heading} onClose={() => onClose(true)} />
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
        {props.botDescription ? <p>{props.botDescription}</p> : null}
      </section>
      {props.agentSettings}
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
