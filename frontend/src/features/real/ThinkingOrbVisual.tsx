import { ThinkingOrb } from "thinking-orbs";

/**
 * The only Thinking Orbs mount in the app: one 20px "working" canvas for the
 * current accepted AI run. The canvas is decorative; the adjacent text status
 * is what assistive technology reads. Thinking Orbs © Jakub Antalik, MIT.
 */
export default function ThinkingOrbVisual() {
  return <ThinkingOrb state="working" size={20} theme="light" paused={false} role="presentation" aria-hidden="true" />;
}
