/**
 * Chooses and renders the active overlay cue using the layout the backend assigned to the viewer's persona.
 * Overlays are announced politely to screen readers as they appear.
 * Only one overlay is shown at a time, selected by priority and display window.
 */
import type { ReceivedCue } from "../../state/matchState";
import type { Point } from "../../types";
import { ExplainerCard, HypeBanner, LowerThird, PlayerTag, StatPanel } from "./Overlays";

interface OverlayLayerProps { active: ReceivedCue | null; ball: Point | null; teamColor: string }

export function OverlayLayer({ active, ball, teamColor }: OverlayLayerProps) {
  if (!active) return null;
  const { cue } = active;
  return (
    <div aria-live="polite" key={cue.cue_id}>
      {cue.layout === "stat_panel" && <StatPanel cue={cue} />}
      {cue.layout === "lower_third" && <LowerThird cue={cue} />}
      {cue.layout === "hype_banner" && <HypeBanner cue={cue} teamColor={teamColor} />}
      {cue.layout === "player_tag" && <PlayerTag cue={cue} ball={ball} />}
      {cue.layout === "explainer_card" && <ExplainerCard cue={cue} />}
    </div>
  );
}
