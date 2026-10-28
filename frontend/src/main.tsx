import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { AppEntry } from "./AppEntry";
import { readAuthCallback } from "./features/auth/callback";
import "./styles/tokens.css";
import "./styles/global.css";
import "./styles/me2we.css";

// Evaluated exactly once at module bootstrap, before React mounts: StrictMode's double render can
// therefore never parse (or lose) tokens that were already removed from the address bar.
const callback = readAuthCallback();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppEntry callback={callback} />
  </StrictMode>,
);
