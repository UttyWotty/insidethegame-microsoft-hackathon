/**
 * Builds the 3D tactical overlay on the grass: shape boxes, the offside line, the pressure ring around the ball
 * carrier, and passing-option arrows. Lines are thin flat strips because WebGL ignores line widths.
 */
import * as THREE from "three";
import { PITCH_WIDTH } from "../../lib/pitch";
import { pitchToWorld } from "../../lib/scene3d";
import { chanceBand, PRESSURE_RADIUS_M, type Tactics } from "../../lib/tactics";
import type { Point } from "../../types";

const LIFT = 0.04;
const STRIP = 0.22;
const ARROW_LENGTH = 1.6;
const ARROW_WIDTH = 1.1;
const BAND_COLORS = { safe: "#4ade80", risky: "#fbbf24", unlikely: "#f87171" } as const;
const OFFSIDE = "#facc15";
const PRESSURE = "#f87171";

function material(color: string, opacity = 0.85): THREE.MeshBasicMaterial {
  return new THREE.MeshBasicMaterial({ color, transparent: true, opacity, depthWrite: false, side: THREE.DoubleSide });
}

/** A flat strip on the grass from a to b. */
function strip(a: Point, b: Point, color: string, width = STRIP, opacity = 0.85): THREE.Mesh {
  const from = pitchToWorld(a, LIFT);
  const to = pitchToWorld(b, LIFT);
  const length = Math.hypot(to.x - from.x, to.z - from.z);
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(length, width), material(color, opacity));
  mesh.rotation.set(-Math.PI / 2, 0, -Math.atan2(to.z - from.z, to.x - from.x));
  mesh.position.set((from.x + to.x) / 2, LIFT, (from.z + to.z) / 2);
  return mesh;
}

function arrowHead(a: Point, b: Point, color: string): THREE.Mesh {
  const shape = new THREE.Shape();
  shape.moveTo(0, 0);
  shape.lineTo(-ARROW_LENGTH, ARROW_WIDTH / 2);
  shape.lineTo(-ARROW_LENGTH, -ARROW_WIDTH / 2);
  shape.closePath();
  const mesh = new THREE.Mesh(new THREE.ShapeGeometry(shape), material(color));
  const tip = pitchToWorld(b, LIFT);
  const tail = pitchToWorld(a, LIFT);
  mesh.rotation.set(-Math.PI / 2, 0, -Math.atan2(tip.z - tail.z, tip.x - tail.x));
  mesh.position.set(tip.x, LIFT, tip.z);
  return mesh;
}

/** Ground overlay for one frame of tactics, coloured by team where it belongs to one. */
export function buildTactics(tactics: Tactics, homeColor: string, awayColor: string): THREE.Group {
  const group = new THREE.Group();
  for (const side of ["home", "away"] as const) {
    const box = tactics.shapes[side];
    if (!box) continue;
    const color = side === "home" ? homeColor : awayColor;
    const corners: Point[] = [{ x: box.x, y: box.y }, { x: box.x + box.depthM, y: box.y },
      { x: box.x + box.depthM, y: box.y + box.widthM }, { x: box.x, y: box.y + box.widthM }];
    corners.forEach((c, i) => group.add(strip(c, corners[(i + 1) % 4], color, STRIP * 0.7, 0.6)));
  }
  if (tactics.offsideX !== null) {
    group.add(strip({ x: tactics.offsideX, y: 0 }, { x: tactics.offsideX, y: PITCH_WIDTH }, OFFSIDE, STRIP * 1.2));
  }
  if (tactics.carrier && tactics.carrier.pressers > 0) {
    const ring = new THREE.Mesh(new THREE.RingGeometry(PRESSURE_RADIUS_M - 0.25, PRESSURE_RADIUS_M, 48), material(PRESSURE));
    const at = pitchToWorld(tactics.carrier.position, LIFT);
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(at.x, LIFT, at.z);
    group.add(ring);
  }
  for (const option of tactics.options) {
    const color = BAND_COLORS[chanceBand(option.chance)];
    group.add(strip(option.from, option.to, color), arrowHead(option.from, option.to, color));
  }
  return group;
}
