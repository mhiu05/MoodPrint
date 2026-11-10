import { useRef } from "react";
import type { ReactNode } from "react";
import { gsap } from "gsap";
import { useGSAP } from "@gsap/react";
import { useLocation } from "react-router-dom";
import { useDemoStore } from "../app/store";
gsap.registerPlugin(useGSAP);
export function PageMotion({ children }: { children: ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const { pathname } = useLocation();
  const reduced = useDemoStore((s) => s.preferences.reducedMotion);
  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        if (!reduced)
          gsap.fromTo(
            ref.current,
            { y: 7, opacity: 0.7 },
            {
              y: 0,
              opacity: 1,
              duration: 0.26,
              ease: "power2.out",
              clearProps: "all",
            },
          );
      });
      return () => mm.revert();
    },
    { scope: ref, dependencies: [pathname, reduced], revertOnUpdate: true },
  );
  return <div ref={ref}>{children}</div>;
}
