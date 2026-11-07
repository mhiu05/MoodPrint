# MoodPrint UI refinement implementation plan

Date: 2026-11-07. Scope: the user's targeted refinement brief; existing PRD 01–08 and frontend/DESIGN.md remain the product baseline.

Goal: recover mobile reading space and make onboarding and chat feel coherent without replacing the working mock workflows.

Architecture: keep React Router, Zustand, fixture matching, analysis confirmation and existing service boundaries. Give chat an immersive shell and reusable presentation components. Persist optional composer drafts on existing owner-scoped ChatSession records; remain compatible with stored v1 records.

Constraints: local changes only, no commits, deployment, infrastructure, backend, agent configuration, secrets, new production services or .gitignore changes. Preserve all four tabs outside chat and the independent School Admin layout.

- [ ] Capture baseline Welcome, Auth, Home, AI Hub, empty/conversation Chat and Support at 390 and 1440px.
- [ ] Add failing regression checks for immersive navigation, draft recovery, typing during replies, composition-safe Enter and retry.
- [ ] Replace onboarding split with a single responsive canvas; retain four steps, Skip/Back/Next and brand art. Compact authentication spacing.
- [ ] Remove student topbar/demo strip; preserve contextual mock disclosures, Support settings and urgent routes. Tighten student spacing without changing Admin.
- [ ] Extract chat topbar, composer, suggestions and scrollable messages; move scenario/case/history/secondary actions into accessible dialogs. Preserve Findings, evidence and confirmed case handoffs.
- [ ] Verify typecheck, lint, build, complete unit/component/store and existing/new E2E suites; cover all eight requested widths, short/keyboard viewports, manual scrolling, reduced motion, console/network and accessibility.
- [ ] Capture final screenshots, independently review the changed source, and deliver refinement/test reports with limitations.

Review focus: interrupted mock replies after reload, source context across routes, owner-scoped draft/reset behavior, mobile keyboard and manual scroll position, IME/Shift+Enter, dialog focus and emergency access.

Direction: preserve the green/ivory identity and incumbent flower. Use an unclipped centered onboarding composition. Chat has quiet message bubbles, a narrow desktop reading column, a small status orb and a composer in normal flex flow. Reference principles: Grok Bot's conversational hierarchy and restrained presence, Impeccable's task-oriented spacing, Thinking Orbs' truthful lifecycle states, and scoped/reduced-motion GSAP. No branding or remote assets copied.
