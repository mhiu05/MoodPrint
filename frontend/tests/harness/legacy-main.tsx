/** Isolated regression harness for preserved pre-migration source. Never a product entry. */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "../../src/App";
import "../../src/styles/tokens.css";
import "../../src/styles/global.css";
import "../../src/styles/me2we.css";
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
