import { useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, X } from "lucide-react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { Button, cx, Dialog } from "../../../components/UI";
import { ErrorNotice } from "../RealApp";
import { ActivitySummary } from "./ActivitySummary";
import { FocusPanel, FocusTimerChip } from "./FocusPanel";
import { IcebreakerPanel } from "./IcebreakerPanel";
import { QuizPanel } from "./QuizPanel";
import { KIND_TITLES, shortStatus } from "./activityView";
import type { ActivityState } from "./useActivity";
import "./activities.css";

/**
 * Hosts the running activity: bottom sheet below 1100 px (collapsible to a bar above
 * the composer), side panel from 1100 px. The composer stays usable throughout.
 */
export function ActivityDock({
  activity,
  alias,
  onContinue,
}: {
  activity: ActivityState;
  alias: string;
  onContinue: () => void;
}) {
  const { session, busy, act, clock } = activity;
  const [collapsed, setCollapsed] = useState(false);
  const [ending, setEnding] = useState(false);
  const toggle = useRef<HTMLButtonElement>(null);
  const dock = useRef<HTMLElement>(null);
  const visible = Boolean(session && session.state !== "invited");
  // M16: the dock wrapper (never its text or the timer) arrives with ≤16px
  // travel when it appears or expands. Server state, not the tween, drives it.
  useGSAP(
    () => {
      if (!visible || collapsed || !dock.current) return;
      const media = gsap.matchMedia();
      media.add(
        { side: "(min-width: 1100px) and (prefers-reduced-motion: no-preference)", sheet: "(max-width: 1099px) and (prefers-reduced-motion: no-preference)" },
        (context) => {
          const side = Boolean(context.conditions?.side);
          gsap.from(dock.current, { ...(side ? { x: 16 } : { y: 16 }), duration: 0.22, ease: "power2.out", clearProps: "transform" });
        },
      );
      return () => media.revert();
    },
    { dependencies: [visible, collapsed, session?.id], revertOnUpdate: true },
  );
  useEffect(() => {
    if (session?.state === "active" && session.progress.round === 1) setCollapsed(false);
  }, [session?.id, session?.state, session?.progress.round]);
  if (!session || session.state === "invited") return null;
  const terminal = !["active", "paused"].includes(session.state);
  const title = KIND_TITLES[session.kind];
  return (
    <section
      ref={dock}
      className="activity-dock"
      data-collapsed={collapsed || undefined}
      aria-label={`Hoạt động chung: ${title}`}
      onKeyDown={(event) => {
        if (event.key === "Escape" && !collapsed) {
          setCollapsed(true);
          toggle.current?.focus();
        }
      }}
    >
      <header className="activity-dock-bar">
        <div>
          <h2>{title}</h2>
          <p>
            {terminal ? "Đã kết thúc" : shortStatus(session)}
            {session.kind === "focus" && !terminal && (
              <>
                {" · "}
                <FocusTimerChip session={session} clock={clock} />
              </>
            )}
          </p>
        </div>
        {!terminal && session.kind !== "focus" && (
          <Button variant="text" disabled={busy} onClick={() => setEnding(true)}>
            Dừng
          </Button>
        )}
        <button
          ref={toggle}
          type="button"
          className="icon-button"
          aria-expanded={!collapsed}
          aria-label={collapsed ? "Mở hoạt động" : "Thu gọn hoạt động"}
          onClick={() => setCollapsed((value) => !value)}
        >
          {collapsed ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>
        {terminal && (
          <button
            type="button"
            className="icon-button"
            aria-label="Đóng hoạt động"
            onClick={() => {
              activity.dismiss();
              onContinue();
            }}
          >
            <X size={20} />
          </button>
        )}
      </header>
      {!collapsed && (
        <div className="activity-dock-body">
          {activity.notice && <p role="status">{activity.notice}</p>}
          <ErrorNotice error={activity.error} retry={() => void activity.refresh()} />
          {terminal ? (
            <ActivitySummary
              session={session}
              alias={alias}
              busy={busy}
              onRate={(rating) => void activity.feedback(rating)}
              onContinue={() => {
                activity.dismiss();
                onContinue();
              }}
            />
          ) : session.kind === "icebreaker" && session.current ? (
            <IcebreakerPanel session={session} alias={alias} busy={busy} act={act} />
          ) : session.kind === "coop_quiz" && session.current ? (
            <QuizPanel session={session} alias={alias} busy={busy} act={act} />
          ) : session.kind === "focus" && session.timer ? (
            <FocusPanel session={session} alias={alias} clock={clock} busy={busy} act={act} />
          ) : (
            <p role="status">Đang tải hoạt động…</p>
          )}
        </div>
      )}
      {ending && (
        <Dialog title="Dừng hoạt động này?" destructive onClose={() => setEnding(false)}>
          <p>Hoạt động sẽ dừng cho cả hai. Hai bạn vẫn có thể tiếp tục trò chuyện.</p>
          <div className={cx.actions}>
            <Button variant="secondary" data-cancel onClick={() => setEnding(false)}>
              Ở lại
            </Button>
            <Button
              variant="danger"
              disabled={busy}
              onClick={() => {
                setEnding(false);
                void act("end");
              }}
            >
              Dừng hoạt động
            </Button>
          </div>
        </Dialog>
      )}
    </section>
  );
}
