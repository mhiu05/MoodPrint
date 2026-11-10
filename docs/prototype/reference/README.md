# MoodPrint — Visual references for UI/UX refinement

These are **AI-generated concept mockups**, not screenshots of Grok Bot and not evidence of implemented features. Images may have imperfect text, inconsistent UI details or placeholder labels. Treat them as **layout and mood references**, never pixel-perfect requirements or authoritative product copy. The actual product specification is `docs/prototype/` (01–08) plus the current frontend code.

## References

- `00-app-reference-board.png` — overall direction: onboarding, account, home, AI hub, chat and component states.
- `00-chat-reference-board.png` — onboarding + chat-focused board, including inline analysis card and design tokens.
- `00-onboarding-and-chat-details.png` — alternate directions for onboarding, account, chat, orb and menu.
- `01-onboarding-single-canvas.png` — single-canvas onboarding, illustration unclipped, CTA toward bottom.
- `02-chat-empty.png` — immersive empty chat: compact top bar, small AI identity, contextual starter chips, bottom composer.
- `03-chat-conversation.png` — conversation mode: user vs assistant message hierarchy, compact suggestion chips.
- `04-chat-analysis-card.png` — structured mock analysis result inline in transcript, with a detail CTA.
- `05-auth-compact.png` — reduce authentication-page intro and prioritize the demo persona selector.
- `06-home-no-global-header.png` — greeting and task entry points, no repeated global header.
- `07-ai-hub.png` — concise routing into Chat, Roleplay, Analysis and History.
- `08-thinking-orb-components.png` — subtle Idle/Processing/Responding/Error visual identity; **only show mock states that exist**.

## Design rules

1. Preserve the calm MoodPrint color identity and legible Vietnamese typography. Do not copy Grok visual assets or branding.
2. Single-canvas onboarding; never hard-split into rigid top/bottom halves. Respect short viewport and dynamic viewport height.
3. Remove repeated authenticated Student Workspace header only; keep emergency support reachable and preserve relevant demo/AI status disclosure.
4. Full-screen `/ai/chat` with compact top bar, scrollable message column and composer anchored above safe-area/keyboard. Hide bottom 4-tab nav only on immersive chat.
5. All AI, OCR, screenshots, voice and support submission remain mock. No actual model, tools, OCR or STT/TTS without separate authorization.
6. Preserve all existing flows, mock stores, app routes, school admin isolation, and test coverage. Avoid gratuitous visual decorations.
7. Screen text on the mockups is illustration, **not** final UX copy. Correct Vietnamese copy and accessibility in real components.
