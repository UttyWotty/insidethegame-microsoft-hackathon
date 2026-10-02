/**
 * Browser entry point that mounts the React application.
 * Global styles and design tokens are imported once here.
 * Strict mode surfaces unsafe effects during development.
 */
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles/app.css";

createRoot(document.getElementById("root") as HTMLElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
