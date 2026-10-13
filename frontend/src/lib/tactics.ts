/**
 * Pure live tactical analysis from the 22 tracked positions, in the screen frame (the frame the pitch draws):
 * the defending team's offside line and defensive block (width and depth of its outfield players; both teams'
 * shapes when nobody has the ball), pressure on the
 * ball carrier, and the carrier's passing options with a simple completion chance from distance and how many
 * opponents stand near the passing lane.
 */
import type { PlayerDot } from "./playerDots";
import type { Point } from "../types";

/** Opponents within this distance of the carrier count as pressing. */
export const PRESSURE_RADIUS_M = 5;
/** Opponents within this distance of a passing lane count as able to intercept. */
export const LANE_RADIUS_M = 2.5;
/** How many passing options to show. */
export const MAX_OPTIONS = 3;
const BASE_LOGIT = 3.2;
const DISTANCE_LOGIT = 0.07;
const INTERCEPT_LOGIT = 1.3;
const SECOND_PERIOD = 2;

/** A team's outfield block: left and top corner, depth along the pitch, and width across it, in metres. */
export interface ShapeBox { x: number; y: number; depthM: number; widthM: number }
/** A passing option from the carrier with its completion chance in 0..1. */
export interface PassOption { from: Point; to: Point; playerId: string; chance: number }
/** Everything the tactical overlay draws for one frame. */
export interface Tactics {
  offsideX: number | null; shapes: { home: ShapeBox | null; away: ShapeBox | null };
  carrier: { position: Point; pressers: number } | null; options: PassOption[];
}

/** Whether a side attacks toward the right of the screen in a period (teams change ends at half-time). */
export function attacksRight(side: "home" | "away", period: number): boolean {
  return (side === "home") === (period < SECOND_PERIOD);
}

/** The offside line: the second-deepest defender (keeper included) of the defending side, or null without two. */
export function offsideLine(players: PlayerDot[], defending: "home" | "away", period: number): number | null {
  const own = players.filter((p) => p.side === defending).map((p) => p.position.x);
  if (own.length < 2) return null;
  const deepFirst = attacksRight(defending, period) ? own.sort((a, b) => a - b) : own.sort((a, b) => b - a);
  return deepFirst[1];
}

/** The bounding box of a side's outfield players, or null when none are tracked. */
export function shapeBox(players: PlayerDot[], side: "home" | "away"): ShapeBox | null {
  const outfield = players.filter((p) => p.side === side && !p.goalkeeper).map((p) => p.position);
  if (!outfield.length) return null;
  const xs = outfield.map((p) => p.x);
  const ys = outfield.map((p) => p.y);
  const x = Math.min(...xs);
  const y = Math.min(...ys);
  return { x, y, depthM: Math.max(...xs) - x, widthM: Math.max(...ys) - y };
}

function distance(a: Point, b: Point): number {
  return Math.hypot(a.x - b.x, a.y - b.y);
}

/** Shortest distance from a point to the segment from a to b. */
export function distanceToSegment(p: Point, a: Point, b: Point): number {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const length2 = dx * dx + dy * dy;
  const t = length2 ? Math.min(Math.max(((p.x - a.x) * dx + (p.y - a.y) * dy) / length2, 0), 1) : 0;
  return distance(p, { x: a.x + t * dx, y: a.y + t * dy });
}

/** Completion chance for a pass of a length with some opponents near the lane. */
export function passChance(length: number, interceptors: number): number {
  return 1 / (1 + Math.exp(-(BASE_LOGIT - DISTANCE_LOGIT * length - INTERCEPT_LOGIT * interceptors)));
}

/** The carrier's best passing options, most likely first. */
export function passOptions(carrier: PlayerDot, players: PlayerDot[]): PassOption[] {
  const opponents = players.filter((p) => p.side !== carrier.side).map((p) => p.position);
  return players
    .filter((p) => p.side === carrier.side && p.id !== carrier.id && !p.goalkeeper)
    .map((mate) => {
      const lane = opponents.filter((o) => distanceToSegment(o, carrier.position, mate.position) < LANE_RADIUS_M).length;
      return { from: carrier.position, to: mate.position, playerId: mate.id,
               chance: passChance(distance(carrier.position, mate.position), lane) };
    })
    .sort((a, b) => b.chance - a.chance)
    .slice(0, MAX_OPTIONS);
}

/** Full tactical picture for a frame; carrierId is the player on the ball, and the other side is defending. */
export function analyseFrame(players: PlayerDot[], carrierId: string | null, period: number): Tactics {
  const carrier = players.find((p) => p.id === carrierId) ?? null;
  const defending = carrier ? (carrier.side === "home" ? "away" : "home") : null;
  return {
    offsideX: defending ? offsideLine(players, defending, period) : null,
    shapes: {
      home: defending === "away" ? null : shapeBox(players, "home"),
      away: defending === "home" ? null : shapeBox(players, "away"),
    },
    carrier: carrier ? {
      position: carrier.position,
      pressers: players.filter((p) => p.side !== carrier.side && distance(p.position, carrier.position) < PRESSURE_RADIUS_M).length,
    } : null,
    options: carrier ? passOptions(carrier, players) : [],
  };
}

/** Colour band for a completion chance: safe, risky, or unlikely. */
export function chanceBand(chance: number): "safe" | "risky" | "unlikely" {
  return chance >= 0.75 ? "safe" : chance >= 0.5 ? "risky" : "unlikely";
}

/** The player on the ball after an event: a successful pass's receiver, otherwise the actor. */
export function carrierAfter(event: { player_id: string | null; receiver_id: string | null; outcome: string | null;
                                      event_type: string } | null): string | null {
  if (!event) return null;
  if (event.event_type === "pass" && event.outcome === "success" && event.receiver_id) return event.receiver_id;
  return event.player_id;
}
