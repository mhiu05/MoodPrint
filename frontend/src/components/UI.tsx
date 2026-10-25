import { BrandMark } from "../companions/Avatar";
import {
  useEffect,
  useId,
  useRef,
  type ReactNode,
  type ButtonHTMLAttributes,
} from "react";
import { X, ShieldCheck } from "lucide-react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import styles from "../styles/App.module.css";
gsap.registerPlugin(useGSAP);
export const cx = styles;
export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "text" | "danger";
}) {
  return (
    <button
      className={`${styles.button} ${styles[variant]} ${className}`}
      type="button"
      {...props}
    />
  );
}
export function StatePanel({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <section className={styles.statePanel}>
      <ShieldCheck size={30} aria-hidden="true" />
      <h2>{title}</h2>
      {children && <p>{children}</p>}
      {action}
    </section>
  );
}
export function Dialog({
  title,
  children,
  onClose,
  destructive = false,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
  destructive?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null),
    id = useId();
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useGSAP(
    () => {
      const media = gsap.matchMedia();
      media.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(ref.current, {
          y: 14,
          duration: 0.22,
          ease: "power2.out",
          clearProps: "all",
        });
      });
      return () => media.revert();
    },
    { scope: ref },
  );
  useEffect(() => {
    const before = document.activeElement as HTMLElement;
    const el = ref.current!;
    el.showModal();
    const first = destructive
      ? el.querySelector<HTMLElement>("[data-cancel]")
      : el.querySelector<HTMLElement>("button,input,textarea,select");
    first?.focus();
    return () => {
      el.close();
      if (before?.isConnected) before.focus();
      else document.querySelector<HTMLElement>("h1")?.focus();
    };
  }, [destructive]);
  return (
    <dialog
      ref={ref}
      className={styles.dialog}
      aria-labelledby={id}
      onKeyDown={(e) => {
        if (e.key !== "Tab") return;
        const nodes = Array.from(
          ref.current!.querySelectorAll<HTMLElement>(
            "button:not(:disabled),input:not(:disabled),textarea:not(:disabled),select:not(:disabled),a[href]",
          ),
        ).filter((n) => n.getClientRects().length > 0);
        const first = nodes[0],
          last = nodes.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }}
      onCancel={(e) => {
        e.preventDefault();
        closeRef.current();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) closeRef.current();
      }}
    >
      <div className={styles.dialogHeader}>
        <h2 id={id}>{title}</h2>
        <Button variant="text" aria-label="Đóng hộp thoại" onClick={onClose}>
          <X size={21} />
        </Button>
      </div>
      {children}
    </dialog>
  );
}
export function Motion({
  children,
  motionKey,
  kind = "page",
  className = "",
}: {
  children: ReactNode;
  motionKey: string | number;
  kind?: "page" | "mood" | "cards" | "success" | "activity";
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        const targets = kind === "cards" ? ref.current!.children : ref.current;
        gsap.from(targets, {
          opacity: kind === "mood" ? 1 : 0,
          y: ["page", "cards"].includes(kind) ? 6 : 0,
          x: kind === "activity" ? 6 : 0,
          scale: kind === "mood" ? 0.97 : kind === "success" ? 0.98 : 1,
          duration: kind === "mood" ? 0.14 : kind === "page" ? 0.18 : 0.22,
          stagger: kind === "cards" ? 0.035 : 0,
          ease: "power1.out",
          clearProps: "all",
        });
      });
      return () => mm.revert();
    },
    { scope: ref, dependencies: [motionKey], revertOnUpdate: true },
  );
  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
export function Typing() {
  const ref = useRef<HTMLSpanElement>(null);
  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        const tween = gsap.to("[data-dot]", {
          opacity: 0.35,
          repeat: -1,
          yoyo: true,
          duration: 0.45,
          stagger: 0.12,
          ease: "sine.inOut",
        });
        const visibility = () => {
          if (document.hidden) tween.pause();
          else tween.resume();
        };
        document.addEventListener("visibilitychange", visibility);
        return () =>
          document.removeEventListener("visibilitychange", visibility);
      });
      return () => mm.revert();
    },
    { scope: ref },
  );
  return (
    <p className={styles.typing} role="status">
      Đang trả lời{" "}
      <span ref={ref} aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <span data-dot key={i}>
            ·
          </span>
        ))}
      </span>
    </p>
  );
}
export function Brand() {
  return (
    <span className={styles.brand}>
      <BrandMark />
      MoodPrint<span className={styles.brandDot}>.</span>
    </span>
  );
}
