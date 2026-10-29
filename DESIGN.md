---
name: MoodPrint — AI conversation
description: Scoped neutral conversation world for MoodPrint AI chat.
colors:
  chat-bg: "#fff"
  chat-ink: "#252629"
  chat-muted: "#64666b"
  chat-border: "#c5c7ca"
  chat-divider: "#ececee"
  chat-surface-soft: "#f5f5f6"
  chat-selected-bg: "#ededf0"
  chat-disabled-bg: "#e8e8eb"
  chat-disabled-text: "#72747a"
  chat-action: "#27282b"
  chat-action-hover: "#414247"
  chat-input: "#f7f7f8"
  chat-self: "#f0f0f2"
  chat-selection: "#dce8e2"
  primary: "#285c4b"
typography:
  title:
    fontFamily: '"Segoe UI", system-ui, -apple-system, Arial, sans-serif'
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.5
  body:
    fontFamily: '"Segoe UI", system-ui, -apple-system, Arial, sans-serif'
    fontSize: "1rem"
    lineHeight: 1.65
  input:
    fontFamily: '"Segoe UI", system-ui, -apple-system, Arial, sans-serif'
    fontSize: "1rem"
    lineHeight: 1.5
  support:
    fontFamily: '"Segoe UI", system-ui, -apple-system, Arial, sans-serif'
    fontSize: "0.875rem"
    lineHeight: 1.5
  metadata:
    fontFamily: '"Segoe UI", system-ui, -apple-system, Arial, sans-serif'
    fontSize: "0.8125rem"
rounded:
  composer: "28px"
  self-message: "20px"
  avatar: "12px"
  tag: "4px"
  round: "50%"
spacing:
  space-1: "0.25rem"
  space-2: "0.5rem"
  space-3: "0.75rem"
  space-4: "1rem"
  space-6: "1.5rem"
components:
  send-button:
    backgroundColor: "{colors.chat-action}"
    textColor: "{colors.chat-bg}"
    rounded: "{rounded.round}"
  send-button-hover:
    backgroundColor: "{colors.chat-action-hover}"
  send-button-disabled:
    backgroundColor: "{colors.chat-disabled-bg}"
    textColor: "{colors.chat-disabled-text}"
  composer:
    backgroundColor: "{colors.chat-input}"
    textColor: "{colors.chat-ink}"
    rounded: "{rounded.composer}"
    padding: "6px"
  self-message:
    backgroundColor: "{colors.chat-self}"
    textColor: "{colors.chat-ink}"
    rounded: "{rounded.self-message}"
    padding: "10px 16px"
  inline-link:
    textColor: "{colors.primary}"
    typography: "{typography.support}"
---

# Design System: MoodPrint — AI conversation

## Overview

**Creative North Star: "Natural agent chat"**

The approved AI conversation world puts reading and writing first: a white canvas, charcoal text, open assistant responses and softly filled user messages. Its restrained controls and system typography support a compact, natural exchange.

This document applies only inside `.bot-conversation.ai-conversation`, implemented in `frontend/src/features/real/agent-chat.css`. It records the approved replacement of the AI chat surface. `frontend/src/styles/tokens.css` remains authoritative for the rest of MoodPrint, including human chat, the assistant roster and the sidebar. Shared typography, semantic colors and motion tokens still inherit from that global system.

**Key Characteristics:**

- Open assistant prose and quiet user-message fills.
- One aligned reading column and composer.
- One primary send/stop action with truthful server status.
- Existing MoodPrint names, avatars and semantic green links.

## Colors

### Primary

The inherited MoodPrint green identifies links and semantic accents. The main chat action uses charcoal. Preserve the existing semantic error, warning and success colors where those states occur.

### Neutral

White is the conversation canvas. Charcoal carries content and the primary action; muted gray carries status and metadata. Light neutral fills distinguish the composer, user messages, hover and disabled controls. Dividers are quieter than control borders. The frontmatter records the exact scoped values; it does not replace global values.

**The Scoped World Rule.** Apply the neutral chat overrides only inside the AI conversation; preserve the incumbent visual system outside it.

## Typography

Use the existing Segoe UI/system font stack, including its Vietnamese coverage. Body and input text use the body-sized role (16px at the default root size); prose has more leading than controls. Header titles are semibold. Supporting labels and metadata remain subordinate. The empty-state title uses the implemented responsive size `clamp(1.25rem, 2vw, 1.5rem)` and letter spacing `-0.025em`.

## Layout

Transcript and composer share a centered reading column (720px). Assistant content is capped at 72ch; user content is capped at `min(85%, 65ch)`. The desktop header is 68px high; below 768px it is 64px plus the top safe area. The AI chat's phone transcript gutter is 16px; the composer region uses 12px side padding. Bottom padding respects the bottom safe area.

Keep the transcript flexible and scrollable while the composer grows. When already at the bottom, ResizeObserver preserves bottom anchoring through textarea or viewport resizing. When the person scrolls up, preserve that reading position and expose the existing jump-to-latest action. Verification sizes and capture references belong to the [surface brief](.impeccable/surfaces/agent-chat.md).

## Elevation & Depth

The core transcript, user messages and composer use flat fills and borders rather than new shadows. A clear outline signals composer focus. Existing shared overlays retain their global depth rules.

## Shapes

The composer is broadly rounded; self messages use a smaller soft radius. Assistant prose has no enclosing bubble border, background or rounding. Send, stop and microphone controls are circular. Keep the inherited assistant avatar artwork and its scoped corner treatment.

## Components

### Primary action

The circular action has a 44px target, a white icon, a darker hover fill, a brief press scale and a visible focus outline (2px, offset 3px). Its disabled colors come from the scoped disabled tokens. Keep the same DOM button as it changes from send to pause.

The pause glyph means **Dừng phản hồi**: request server cancellation. It does not offer pause/resume. Enable it only for a cancellable accepted run, disable it while requesting cancellation or reconciling, and return to send after the terminal result. Preserve drafts during a run. When the composer is unavailable, provide the single fallback stop control beside status; never show two stop controls.

### Composer

Use the light input fill, thin divider border and frontmatter shape. Focus-within changes the border and adds a charcoal outline (2px, offset 2px). The multiline textarea has a 44px minimum height, transparent fill and body-sized text. Preserve Enter to send, Shift+Enter for a new line, IME composition and the existing voice control.

### Messages and links

Assistant text sits directly on the canvas. User messages receive the self-message fill and content-sized width. Metadata and copy actions remain available through hover, keyboard focus and touch; retain their reserved space. Navigation cards appear as compact green text links with an inline arrow rather than a second large container. Empty-state introductions and suggestions give way to the conversation once messages exist.

### Activity status

Place the status after the messages, aligned with assistant prose. Keep its polite, atomic status region mounted separately from message announcements; do not mark the transcript busy or announce the status twice. A working orb (20px) represents an accepted run with known identity, without invented reasoning/search stages.

The accepted status enters with GSAP (160ms, 4px rise, opacity 0.6 to 1, `power2.out`). Control feedback uses the inherited feedback duration (100ms) and state easing. Reduced motion, hidden tabs and orb chunk/canvas failures use a static icon. Remove the orb immediately on terminal state; animation must never delay content or affect requests.

## Do's and Don'ts

### Do:

- **Do** keep body and input text at the documented body-sized role and action targets at least 44px.
- **Do** preserve scroll position when reading older messages and anchor resizing only when already at the bottom.
- **Do** show cancellation as pending until the server supplies a terminal result.
- **Do** retain keyboard focus, metadata access, voice input and existing conversation controls.

### Don't:

- **Don't** propagate the scoped white/gray palette to human chat, the roster or the sidebar.
- **Don't** add assistant bubble frames or restore large containers around single navigation links on this surface.
- **Don't** promise resume, invent server phases or wait for animation before showing a response.
- **Don't** animate transcript height, individual response tokens or auto-scroll with a timeline.
