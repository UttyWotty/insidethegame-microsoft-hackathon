/**
 * Chooses and renders the active overlay cue using the layout the backend assigned to the viewer's persona.
 * Overlays are announced politely to screen readers through one live region that stays mounted, so each new
 * overlay is a content change the reader announces rather than a freshly inserted region it may ignore.
 * Only one overlay is shown at a time, selected by priority and display window.
 */
import type { ReceivedCue } from "../../state/matchState";
import type { BallAnchor } from "../Pitch";
import { ExplainerCard, HypeBanner, LowerThird, PlayerTag, StatPanel } from "./Overlays";

interface OverlayLayerProps { active: ReceivedCue | null; anchor: BallAnchor; teamColor: string }

export function OverlayLayer({ active, anchor, teamColor }: OverlayLayerProps) {
  const cue = active?.cue;
  return (
    <div aria-live="polite">
      {cue && (
        <div key={cue.cue_id}>
          {cue.layout === "stat_panel" && <StatPanel cue={cue} />}
          {cue.layout === "lower_third" && <LowerThird cue={cue} />}
          {cue.layout === "hype_banner" && <HypeBanner cue={cue} teamColor={teamColor} />}
          {cue.layout === "player_tag" && <PlayerTag cue={cue} anchor={anchor} />}
          {cue.layout === "explainer_card" && <ExplainerCard cue={cue} />}
        </div>
      )}
    </div>
  );
}
