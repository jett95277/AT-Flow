import { AtApiClient } from "./api/client";
import { AppShell } from "./components/AppShell";
import "./styles.css";

const api = new AtApiClient();

export function App() {
  return <AppShell client={api} />;
}
