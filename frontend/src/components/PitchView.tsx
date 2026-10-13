/**
 * Chooses how the pitch is drawn for a camera: the SVG pitch for the broadcast and tactical cameras, or the 3D
 * broadcast view, loaded on demand so three.js stays out of the main bundle until a viewer asks for it.
 */
import { lazy, Suspense, type ReactNode } from "react";
import type { Point } from "../types";
import type { ShotTrace, TrailPoint } from "../state/matchState";
import type { Tactics } from "../lib/tactics";
import { Pitch, type BallAnchor, type PlayerDot } from "./Pitch";

const Pitch3D = lazy(() => import("./pitch3d/Pitch3D"));

export type Camera = "broadcast" | "tactical" | "3d";

interface PitchViewProps {
  camera: Camera; ball: Point | null; trail: TrailPoint[]; players: PlayerDot[]; moveMs: number; homeColor: string;
  awayColor: string; label: string; shot: ShotTrace | null; onBallAnchor: (anchor: BallAnchor) => void;
  children?: ReactNode;
  /** Instant replay framing: a 2D crop and the goal the 3D camera sits behind; omitted for live play. */
  replay?: { zoom: [number, number, number, number]; behindGoal: "left" | "right" } | null;
  /** Live tactical overlay; omitted or null draws none. */
  tactics?: Tactics | null;
}

export function PitchView({ camera, children, replay = null, tactics = null, ...rest }: PitchViewProps) {
  if (camera !== "3d") {
    return <Pitch camera={camera} zoom={replay?.zoom ?? null} tactics={tactics} {...rest}>{children}</Pitch>;
  }
  const { ball, players, moveMs, homeColor, awayColor, label, onBallAnchor } = rest;
  return (
    <Suspense fallback={<div className="pitch-wrap pitch3d-loading">Loading the 3D view...</div>}>
      <Pitch3D ball={ball} players={players} moveMs={moveMs} homeColor={homeColor} awayColor={awayColor} label={label}
        onBallAnchor={onBallAnchor} behindGoal={replay?.behindGoal ?? null} tactics={tactics}>{children}</Pitch3D>
    </Suspense>
  );
}
