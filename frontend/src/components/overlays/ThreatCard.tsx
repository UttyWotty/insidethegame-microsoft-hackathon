/**
 * Line-breaker card: a glass broadcast card that appears when a pass breaks the opponent's lines and adds expected
 * threat (xT). It shows the kicker, passer to receiver, and stat rows that depend on the viewer's persona.
 * It takes the top-right slot of the shot card, which it never overlaps because it hides while a shot card shows.
 */
import { threatCardRows, type ThreatFlash } from "../../lib/threat";
import type { PersonaKey } from "../../types";

export function ThreatCard({ flash, color, persona }: { flash: ThreatFlash; color: string; persona: PersonaKey }) {
  return (
    <aside className="glass threat-card" style={{ borderTopColor: color }}
      aria-label={`Line breaker: ${flash.passer} to ${flash.receiver}`}>
      <div className="shot-card-head">
        <span className="scout-kicker">LINE BREAKER</span>
      </div>
      <strong className="display threat-card-pass">{flash.passer} to {flash.receiver}</strong>
      <dl className="threat-card-rows">
        {threatCardRows(flash, persona).map(([label, value]) => (
          <div key={label}><dt>{label}</dt><dd>{value}</dd></div>
        ))}
      </dl>
    </aside>
  );
}
