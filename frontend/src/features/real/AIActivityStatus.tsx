import { Component, lazy, Suspense, useRef, type ReactNode } from "react";
import { RefreshCw, Send, Sparkles, Square } from "lucide-react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { Button } from "../../components/UI";
import { useMotionPolicy } from "../../components/motion/useMotionPolicy";
import type { AIActivityPhase, AIActivityView } from "./aiActivityView";

const ThinkingOrbVisual = lazy(() => import("./ThinkingOrbVisual"));

/** A failed chunk or canvas leaves the static icon in place; the run is unaffected. */
class OrbBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

function StaticIcon({ phase }: { phase: AIActivityPhase }) {
  if (phase === "submitting") return <Send size={18} />;
  if (phase === "cancelling" || phase === "cancelled") return <Square size={16} />;
  if (phase === "reconciling") return <RefreshCw size={16} />;
  return <Sparkles size={18} />;
}

/**
 * One status row above the composer. The text region is always mounted so a
 * phase change is announced once; the visual and Dừng exist only while a run is
 * actually active. It never starts requests or waits for animation.
 */
export function AIActivityStatus({
  view,
  phase,
  identity,
  onStop,
  stopDisabled,
}: {
  view: AIActivityView;
  phase: AIActivityPhase;
  /** Request/run identity; a change re-mounts the visual so no stale loop survives. */
  identity: string;
  onStop?: () => void;
  stopDisabled?: boolean;
}) {
  const wrapper = useRef<HTMLDivElement>(null);
  const { animate } = useMotionPolicy();
  const loop = view.orbState === "working" && animate;
  const shown = Boolean(view.label);
  // M10: the wrapper (never the canvas or text) rises at most 4px only when an
  // accepted run begins. Sending stays static (14), and terminal/reconciling
  // changes coincide with the validated reply, which must render without extra work.
  const entering = phase === "accepted";
  useGSAP(
    () => {
      if (!shown || !entering) return;
      const media = gsap.matchMedia();
      media.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(wrapper.current, { y: 4, duration: 0.16, ease: "power2.out", clearProps: "transform" });
      });
      return () => media.revert();
    },
    { scope: wrapper, dependencies: [phase, shown], revertOnUpdate: true },
  );
  const icon = <StaticIcon phase={phase} />;
  return (
    <div className={`ai-status ${shown ? "is-shown" : ""}`} ref={wrapper} aria-busy={view.busy || undefined}>
      {shown ? (
        <span className="ai-status-visual" aria-hidden="true">
          {loop ? (
            <OrbBoundary key={identity} fallback={icon}>
              <Suspense fallback={icon}>
                <ThinkingOrbVisual />
              </Suspense>
            </OrbBoundary>
          ) : (
            icon
          )}
        </span>
      ) : null}
      <p role="status" aria-live="polite" aria-atomic="true">
        {view.label ?? ""}
      </p>
      {onStop ? (
        <Button variant="secondary" className="ai-status-stop" disabled={stopDisabled} onClick={onStop}>
          Dừng
        </Button>
      ) : null}
    </div>
  );
}
