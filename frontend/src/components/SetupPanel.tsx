/**
 * Match setup form: choose two fictional clubs, a simulation seed, and replay speed, then kick off.
 * Labels are always visible and errors are shown next to the form.
 * The two club selectors prevent picking the same club twice.
 */
import { useState } from "react";
import type { ClubInfo } from "../types";
import type { CreateMatch } from "../api/client";

const SPEEDS = [{ value: 10, label: "10x (9 min match)" }, { value: 30, label: "30x (3 min match)" }, { value: 60, label: "60x (90 s match)" }];
const DEFAULT_SEED = 7;

interface SetupProps { clubs: ClubInfo[]; busy: boolean; error: string | null; onStart: (body: CreateMatch) => void }

export function SetupPanel({ clubs, busy, error, onStart }: SetupProps) {
  const [home, setHome] = useState("kestrel_bay");
  const [away, setAway] = useState("ironvale");
  const [seed, setSeed] = useState(DEFAULT_SEED);
  const [speed, setSpeed] = useState(SPEEDS[0].value);
  return (
    <form className="panel stack" onSubmit={(e) => { e.preventDefault(); onStart({ home, away, seed, speed }); }}>
      <h2 className="display">New match</h2>
      <label className="field">Home club
        <select value={home} onChange={(e) => setHome(e.target.value)}>
          {clubs.map((c) => <option key={c.key} value={c.key} disabled={c.key === away}>{c.name} ({c.style})</option>)}
        </select>
      </label>
      <label className="field">Away club
        <select value={away} onChange={(e) => setAway(e.target.value)}>
          {clubs.map((c) => <option key={c.key} value={c.key} disabled={c.key === home}>{c.name} ({c.style})</option>)}
        </select>
      </label>
      <label className="field">Seed
        <input type="number" value={seed} min={0} onChange={(e) => setSeed(Number(e.target.value))} />
      </label>
      <label className="field">Replay speed
        <select value={speed} onChange={(e) => setSpeed(Number(e.target.value))}>
          {SPEEDS.map((s) => <option key={s.value} value={s.value}>{s.label}</option>)}
        </select>
      </label>
      {error && <p className="error" role="alert">{error}</p>}
      <button className="button-primary" type="submit" disabled={busy}>{busy ? "Simulating..." : "Kick off"}</button>
    </form>
  );
}
