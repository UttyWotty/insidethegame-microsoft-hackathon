/**
 * Tests for the 3D Tactical Scout zone plane built from a screen-frame zone rectangle.
 * They check that the plane lies flat on the grass, covers exactly the zone, and is centred on it in world space.
 * The mesh is built without a renderer, so the test needs no WebGL context.
 */
import { describe, expect, it } from "vitest";
import * as THREE from "three";
import { buildScoutZone } from "./scoutObjects";
import { zoneRect } from "../../lib/scout";

describe("buildScoutZone", () => {
  it("lays a translucent plane flat over the flagged zone's centre", () => {
    const zone = zoneRect("left", "final", false, 1);
    const mesh = buildScoutZone(zone, "#ff8800");
    const params = (mesh.geometry as THREE.PlaneGeometry).parameters;
    expect(params.width).toBeCloseTo(zone.width);
    expect(params.height).toBeCloseTo(zone.height);
    expect(mesh.rotation.x).toBeCloseTo(-Math.PI / 2);
    expect(mesh.position.x).toBeCloseTo(zone.x + zone.width / 2 - 105 / 2);
    expect(mesh.position.z).toBeCloseTo(zone.y + zone.height / 2 - 68 / 2);
    expect(mesh.position.y).toBeGreaterThan(0);
    const material = mesh.material as THREE.MeshBasicMaterial;
    expect(material.transparent).toBe(true);
    expect(material.opacity).toBeLessThan(1);
  });
});
