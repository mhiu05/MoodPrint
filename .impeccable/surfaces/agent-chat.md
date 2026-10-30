# Agent chat

- **Mode:** Operate.
- **Target:** `/assistants/:botId`; `.bot-conversation.ai-conversation` in `frontend/src/features/real/RealApp.tsx`.
- **Status:** Implemented approved direction, 30 October 2026. Visual reviewer scored the narrow-screen status fix resolved, disposition **ship**; that verdict covers the scored fix.
- **Authority:** [approved design](../../docs/superpowers/specs/2026-10-30-natural-agent-chat-design.md), [scoped design system](../../DESIGN.md), `frontend/src/features/real/agent-chat.css` and `AIActivityStatus.tsx`.

## Intent and scope

Support a compact, natural exchange with an AI assistant. Reading, composing and requesting stop are the primary tasks. The user approved the full neutral AI chat direction inspired by Grok, using Thinking Orbs for working status and GSAP for the brief accepted-state entrance. This is an interpreted MoodPrint design; the interactive Grok demo was blocked by Cloudflare, so exact visual fidelity is not claimed.

Keep MoodPrint's names, avatars, content, conversation history, metadata/copy access, voice input, suggestions and conversation controls. Global tokens still govern all other screens, including human chat, the assistant roster and sidebar. No backend/API redesign or resume feature belongs to this surface change.

## Composition and behavior

The white conversation canvas holds open assistant prose and lightly filled user messages. Transcript and composer share the 720px reading axis. Empty-state introduction and suggestions recede once conversation begins. Compact inline arrow links replace large navigation-card frames.

One persistent primary button changes from send to pause for a cancellable accepted run. Pause requests server cancellation; it never promises resume or immediate completion. Pending submit, cancellation and reconciliation disable the relevant action. The draft remains available during the run. Provide one inline fallback stop only if the composer is absent.

Activity sits at the transcript's end. Its separate polite live region avoids duplicate message announcements. The 20px working orb and 160ms GSAP entrance yield to static icons under reduced motion, hidden-tab policy or visual-load failure. Terminal results show immediately. ResizeObserver preserves bottom anchoring only while already atBottom; scrolling up retains the reading position.

## Evidence and review

Current synthetic UI captures are under [archived captures](../../docs/ux-redesign/evidence/natural-agent-chat-2026-10-30/captures/agent-chat/):

- `empty-1440.png`, `empty-390.png`: initial state.
- `conversation-1440.png`, `conversation-390.png`: populated transcript.
- `working-360.png`, `working-390.png`, `working-666.png`, `working-1440.png`: accepted run with a multiline draft and stop control.

Responsive checks covered 360px, 390px, 666px and 1440px widths. These are UI fixtures, not evidence of production model behavior. The current 360px working capture shows the status above the composer with the full multiline draft and stop control visible.

| Fix list | Resolution | Verdict |
| --- | --- | --- |
| Working status could be clipped at 360px when the composer grew. | ResizeObserver anchors the log after resize while already atBottom; narrow-screen capture and regression check reviewed. Older-message reading remains unforced. | Ship |

The session's design hooks reported no deterministic findings. That result complements the responsive visual review; it does not establish untested product or brand claims.
