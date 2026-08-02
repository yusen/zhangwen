import { AppShell } from "./components/layout/AppShell";
import { AuthGate } from "./components/auth/AuthGate";
import { V2AppShell } from "./components/v2/V2AppShell";
import { CreatorApp } from "./creator/CreatorApp";

export function App() {
  const useCreator = import.meta.env.DEV
    && import.meta.env.VITE_ZHANGWEN_CREATOR_UI !== "0"
    && import.meta.env.MODE !== "test";
  const useV2 = import.meta.env.VITE_ZHANGWEN_V2_UI !== "0"
    && import.meta.env.MODE !== "test";
  return (
    <AuthGate>
      {({ account, logout }) => (
        useCreator
          ? <CreatorApp account={account} onLogout={logout} />
          : useV2
          ? <V2AppShell account={account} onLogout={logout} />
          : <AppShell account={account} onLogout={logout} />
      )}
    </AuthGate>
  );
}
