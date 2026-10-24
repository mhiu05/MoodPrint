import { BrandMark } from "../companions/Avatar";
import {
  useEffect,
  useId,
  useRef,
  type ReactNode,
  type ButtonHTMLAttributes,
} from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { X, ArrowRight, ShieldCheck } from "lucide-react";
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
export function Go({
  to,
  children,
  secondary = false,
}: {
  to: string;
  children: ReactNode;
  secondary?: boolean;
}) {
  return (
    <Link
      className={`${styles.button} ${secondary ? styles.secondary : styles.primary}`}
      to={to}
    >
      {children}
      <ArrowRight size={17} aria-hidden="true" />
    </Link>
  );
}
export function Badge({ children }: { children: ReactNode }) {
  return <span className={styles.badge}>{children}</span>;
}
export function Intro({
  eyebrow,
  title,
  children,
}: {
  eyebrow?: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <header className={styles.intro}>
      {eyebrow && <p className={styles.eyebrow}>{eyebrow}</p>}
      <h1 tabIndex={-1}>{title}</h1>
      {children && <p className={styles.lede}>{children}</p>}
    </header>
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
          opacity: 0,
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
export function Tabs({
  tabs,
  defaultTab,
}: {
  tabs: Record<string, string>;
  defaultTab: string;
}) {
  const [params, setParams] = useSearchParams();
  const value = params.get("tab") || defaultTab;
  return (
    <nav className={styles.tabs} aria-label="Các phần nội dung">
      {Object.entries(tabs).map(([key, label]) => (
        <button
          type="button"
          key={key}
          aria-current={key === value ? "page" : undefined}
          onClick={() => setParams({ tab: key })}
        >
          {label}
        </button>
      ))}
    </nav>
  );
}
export function useTab(
  tabs: string[],
  fallback: string,
  extraKeys: string[] = [],
) {
  const [p, set] = useSearchParams();
  const v = p.get("tab") || fallback;
  useEffect(() => {
    if (
      !tabs.includes(v) ||
      Array.from(p.keys()).some((k) => k !== "tab" && !extraKeys.includes(k))
    )
      set({ tab: tabs.includes(v) ? v : fallback }, { replace: true });
  }, [v, p, set, tabs.join(","), extraKeys.join(",")]);
  return tabs.includes(v) ? v : fallback;
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
      Me2We<span className={styles.brandDot}>.</span>
    </span>
  );
}
export function Avatar({
  name,
  color = "sage",
}: {
  name: string;
  color?: string;
}) {
  return (
    <span className={`${styles.avatar} ${styles[color]}`} aria-hidden="true">
      <svg viewBox="0 0 100 110" width="100%" height="100%" fill="none">
        <path
          d="M9 115c1-32 16-43 41-43s40 11 41 43"
          fill={
            color === "blue"
              ? "#607f9b"
              : color === "peach"
                ? "#b76543"
                : "#487664"
          }
        />
        <path d="M40 70v14q10 9 20 0V70" fill="#d99c72" />
        <ellipse cx="50" cy="46" rx="27" ry="32" fill="#efbc92" />
        <path
          d={
            name.startsWith("Mầm")
              ? "M22 51c-10-10-10-25-2-29-2-12 10-20 20-17C50-4 62 1 66 8c15-2 24 13 18 24l-7 19-5-22c-8 5-13-4-17-1-9 7-15-5-21-1L22 51Z"
              : name.startsWith("Đồi")
                ? "M21 52C7 12 40 1 61 9c20 2 27 22 17 43l-4-25-47 1-6 24Z"
                : color === "peach"
                  ? "M23 61C5 9 37 4 50 8c32-8 44 38 26 59l-4-36c-18 7-28-3-34-10L23 61Z"
                  : color === "blue"
                    ? "M23 50C5 9 36 1 53 9c26-4 33 20 24 41l-8-26c-14 12-24 1-31 4L23 50Z"
                    : "M22 51C5 10 39 1 55 9c25-4 34 23 23 44L67 29c-16 11-25 4-32-3L22 51Z"
          }
          fill="#303d33"
        />
        <path
          d="M38 49h2m20 0h2"
          stroke="#303d33"
          strokeWidth="4"
          strokeLinecap="round"
        />
        <path
          d="M44 63q6 6 12 0"
          stroke="#994c3d"
          strokeWidth="2"
          strokeLinecap="round"
        />
        {color === "blue" && (
          <g stroke="#303d33" strokeWidth="1.5">
            <circle cx="37" cy="49" r="9" />
            <circle cx="63" cy="49" r="9" />
            <path d="M46 49h8" />
          </g>
        )}
        <path
          d="M22 110V94m56 16V94"
          stroke="#f8f4ed"
          strokeOpacity=".4"
          strokeWidth="2"
        />
      </svg>
    </span>
  );
}
export function Garden({ connection = false }: { connection?: boolean }) {
  return (
    <svg
      className={styles.garden}
      viewBox="0 0 460 230"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="356" cy="58" r="28" fill="#e8c5a8" />
      <path
        d="M28 206c85-55 156-35 219-14 71 25 137 7 191-22"
        stroke="#c1ccbb"
        strokeWidth="2"
      />
      <path
        d="M139 201v-89m0 50c-52-4-63-40-61-62 37 0 62 24 61 62Zm0-20c42-5 53-35 50-59-34 3-51 26-50 59Z"
        fill="#93ad91"
        stroke="#285c4b"
        strokeWidth="2"
      />
      <path
        d="M278 200V91m0 58c-40-5-53-27-51-54 31 3 51 23 51 54Zm0-13c45-6 60-36 57-65-37 4-57 30-57 65Z"
        fill="#d9b39a"
        stroke="#795744"
        strokeWidth="2"
      />
      <path
        d="M109 203h63l-7 22h-49l-7-22Zm138 0h65l-8 22h-49l-8-22Z"
        fill="#285c4b"
      />
      {connection && (
        <path
          d="M181 103c28-30 45-27 60-1"
          stroke="#b74f39"
          strokeWidth="2"
          strokeDasharray="4 6"
        />
      )}
      <path d="m44 60 4 8 8 4-8 4-4 8-4-8-8-4 8-4 4-8Z" fill="#b74f39" />
      <circle cx="207" cy="50" r="4" fill="#285c4b" />
    </svg>
  );
}
