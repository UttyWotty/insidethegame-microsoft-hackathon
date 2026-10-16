/**
 * Landing panel shown before a match starts: what the product is, why it is different, and a one-click demo.
 * It frames the four differentiators judges and broadcasters care about in a few seconds of reading.
 * The demo button starts a preset fixture at a speed suited to a short walkthrough.
 */
import type { CreateMatch } from "../api/client";

const DEMO_MATCH: CreateMatch = { home: "kestrel_bay", away: "ironvale", seed: 1407, speed: 30 };

const PILLARS = [
  { title: "Explains why it matters", text: "Agents turn xG, pass difficulty, momentum, and control versus chaos into the story behind each moment." },
  { title: "Five audiences, one feed", text: "Analyst, casual fan, superfan, player tracker, and newcomer each get their own voice, overlays, and language." },
  { title: "Fact-checked before air", text: "Every number is grounded, a Standards Editor agent reviews each card, and producers can hold overlays." },
  { title: "Broadcast-ready", text: "Timed overlay cues, live tracking of all 22 players, recaps, and an MCP server for other agents." },
];

export function Landing({ busy, onDemo }: { busy: boolean; onDemo: (match: CreateMatch) => void }) {
  return (
    <section className="panel landing" style={{ gridColumn: "span 2" }} aria-label="About Inside the Game">
      <span className="chip">Synthetic data - no footage or licences needed</span>
      <h2 className="display landing-title">Every match, made for every fan.</h2>
      <p className="landing-lead">
        Explainable, fact-checked match intelligence from synthetic football events, personalized live for five
        audiences in any language, and ready to sit on screen alongside the match.
      </p>
      <div className="pillars">
        {PILLARS.map((p) => (
          <article className="pillar" key={p.title}>
            <h3 className="display">{p.title}</h3>
            <p>{p.text}</p>
          </article>
        ))}
      </div>
      <button className="button-primary landing-cta" disabled={busy} onClick={() => onDemo(DEMO_MATCH)}>
        {busy ? "Simulating..." : "Watch a demo match"}
      </button>
    </section>
  );
}
