/**
 * Application shell: loads metadata, starts matches, and switches between the broadcast view and multiview.
 * Viewer preferences are resolved into a valid segment before any stream is opened.
 * The header shows which model provider powers the agents.
 */
import { useCallback, useEffect, useMemo, useState } from "react";
import { api, ApiError, type CreateMatch, type Health } from "./api/client";
import { BroadcastView } from "./components/BroadcastView";
import { MultiView } from "./components/MultiView";
import { SetupPanel } from "./components/SetupPanel";
import { ViewerControls } from "./components/ViewerControls";
import { withRetry } from "./lib/retry";
import { resolveViewer } from "./lib/viewer";
import type { ClubInfo, PersonaInfo, SessionInfo, ViewerSettings } from "./types";

type View = "broadcast" | "multiview";

export function App() {
  const [clubs, setClubs] = useState<ClubInfo[]>([]);
  const [personas, setPersonas] = useState<PersonaInfo[]>([]);
  const [languages, setLanguages] = useState<Record<string, string>>({ en: "English" });
  const [health, setHealth] = useState<Health | null>(null);
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<View>("broadcast");
  const [rawViewer, setRawViewer] = useState<ViewerSettings>({ persona: "analyst", language: "en", team: null, player: null });

  const [loadFailed, setLoadFailed] = useState(false);
  const loadMetadata = useCallback(() => {
    setLoadFailed(false);
    withRetry(() => Promise.all([api.clubs(), api.personas(), api.languages(), api.health()]))
      .then(([c, p, l, h]) => { setClubs(c); setPersonas(p); setLanguages(l); setHealth(h); })
      .catch(() => setLoadFailed(true));
  }, []);
  useEffect(loadMetadata, [loadMetadata]);

  const match = session?.match ?? null;
  const viewer = useMemo(() => resolveViewer(rawViewer, match), [rawViewer, match]);

  const start = async (body: CreateMatch) => {
    setBusy(true);
    setError(null);
    try {
      setSession(await api.createMatch(body));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start the match");
    } finally {
      setBusy(false);
    }
  };

  return (
    <>
      <header className="app-header">
        <div className="brand">
          <h1 className="display">Inside the Game</h1>
          <span className="muted tagline">Explainable match intelligence</span>
        </div>
        <div className="tabs" role="tablist" aria-label="View">
          {(["broadcast", "multiview"] as View[]).map((v) => (
            <button key={v} role="tab" className="tab" aria-selected={view === v} onClick={() => setView(v)}>
              {v === "broadcast" ? "Broadcast" : "All personas"}
            </button>
          ))}
        </div>
        {health && <span className="chip provider">Agents: {health.model_provider}</span>}
      </header>
      {loadFailed && (
        <div className="banner" role="alert">
          The match service is not reachable yet.
          <button className="chip" onClick={loadMetadata}>Retry</button>
        </div>
      )}
      {view === "broadcast" || !session || !match ? (
        <main className="layout">
          <div className="stack controls">
            <SetupPanel clubs={clubs} busy={busy} error={error} onStart={start} />
            <ViewerControls aiOnline={health?.model_provider !== "offline"} personas={personas} languages={languages} match={match} viewer={viewer} onChange={setRawViewer} />
          </div>
          {session
            ? <BroadcastView key={session.session_id} sessionId={session.session_id} viewer={viewer} />
            : <div className="panel empty" style={{ gridColumn: "span 2" }}>Pick two clubs and kick off a synthetic match.</div>}
        </main>
      ) : (
        <main><MultiView sessionId={session.session_id} personas={personas} language={viewer.language} match={match} /></main>
      )}
    </>
  );
}
