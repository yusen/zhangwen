import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./App.css";
import "./styles/visual-system.css";
import "./styles/visual-workspace.css";
import "./styles/visual-settings.css";
import "./styles/visual-hardware-project.css";
import "./styles/visual-auth.css";
import "./styles/visual-right-panel.css";
import "./styles/v2-tokens.css";
import "./styles/v2-shell.css";
import "./styles/v2-workspace.css";
import "./styles/v2-overlays.css";
import "./styles/device-lab.css";
import "./creator/creator.css";
import { HostAdapterProvider } from "./platform";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <HostAdapterProvider>
      <App />
    </HostAdapterProvider>
  </StrictMode>
);
