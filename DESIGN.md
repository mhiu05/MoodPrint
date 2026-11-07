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

