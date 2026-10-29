# Design system and GSAP

Status: NOT_STARTED. Preserve existing `frontend/src/styles/tokens.css`, `components/UI.tsx`, companion assets and `components/motion` conventions. Impeccable context launcher ran once successfully; no PRODUCT.md/DESIGN.md exists, but source tokens and six approved references establish the visual world. This is an Operate surface extension, not a new-brand workflow.

## Direction contract

Bright warm page, calm sage selected states, dark green primary actions, clear Vietnamese body text. Main task progresses mood → details → influences → moment → save; discovery follows naturally below on narrow screens. Keep section heading gaps larger than internal label gaps. Avoid nested-card stacks, decorative gradients, fake stats, inert tools and excessive mascot size.

| Element | Existing token / rule |
| --- | --- |
| Page / surface | `--color-bg`, `--color-surface`, `--color-surface-soft` |
| Primary / selected | `--color-primary`, `--color-selected-bg`; selected border and aria state |
| Text / help / errors | `--color-ink`, `--color-muted`, `--color-danger` |
| Type | `--font-body`, 16px body,14px supporting; headings adapt without overflow |
| Spacing / corners | `--space-*`, `--radius-md`; one border or restrained elevation |
| Targets | `--target-min`44px; visible focus and reduced-motion CSS |

## Motion

Reuse installed GSAP3 and `@gsap/react`; consult `useMotionPolicy` before animation. Context-scoped hook cleanup, no layout-critical opacity hidden by default. Short panel/attachment entrances and selection/save feedback only; no animation at every text keystroke. Form validity and save state never depend on animation completion. Reduced motion removes travel and keeps feedback immediate. No heavy ScrollTrigger or scroll hijacking.

Review references: [Impeccable](https://github.com/pbakaus/impeccable), [GSAP](https://github.com/greensock/gsap), [context cleanup](https://gsap.com/docs/v3/GSAP/gsap.context()/). Apply local Impeccable craft-floor before UI edits and audit/polish after rendered checks. Capture actual app states, not only static similarity.
