/**
 * Builds the 3D highlight of the Tactical Scout's flagged zone: one translucent plane lying on the grass.
 * The zone rectangle is in the screen frame in metres, converted to world space with the shared scene helpers.
 * It sits just below the tactical strips' lift so the strips stay readable on top of it.
 */
import * as THREE from "three";
import type { ZoneRect } from "../../lib/scout";
import { pitchToWorld } from "../../lib/scene3d";

const LIFT = 0.03;
const OPACITY = 0.22;

/** A translucent plane covering the flagged zone, in the beneficiary team's colour. */
export function buildScoutZone(zone: ZoneRect, color: string): THREE.Mesh {
  const centre = pitchToWorld({ x: zone.x + zone.width / 2, y: zone.y + zone.height / 2 }, LIFT);
  const material = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: OPACITY, depthWrite: false,
                                                 side: THREE.DoubleSide });
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(zone.width, zone.height), material);
  mesh.rotation.x = -Math.PI / 2;
  mesh.position.set(centre.x, LIFT, centre.z);
  return mesh;
}
