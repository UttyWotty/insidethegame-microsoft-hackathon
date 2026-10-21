/**
 * Builders for the 3D broadcast scene's objects: a striped pitch with markings, goals with nets, raked stands with
 * a crowd, player figures in club colours with legs that can run, and the ball. They only create three.js objects; the Pitch3D component owns their lifecycle.
 */
import * as THREE from "three";
import { PITCH_LENGTH, PITCH_WIDTH, RUNOFF_M } from "../../lib/pitch";

const TEXTURE_PX_PER_M = 12;
const STRIPES = 10;
const LINE_M = 0.14;
const CENTRE_CIRCLE_M = 9.15;
const PENALTY_AREA = { depth: 16.5, top: 13.84, width: 40.32 };
const GOAL_AREA = { depth: 5.5, top: 24.84, width: 18.32 };
const PENALTY_SPOT_M = 11;
const SPOT_RADIUS_M = 0.25;
const GOAL_WIDTH = 7.32;
const GOAL_HEIGHT = 2.44;
const GOAL_DEPTH = 1.6;
const POST_RADIUS = 0.07;
const HIP_HEIGHT = 0.85;
const HIP_SPREAD = 0.12;
const LEG_RADIUS = 0.09;
const SHORTS_HEIGHT = 0.22;
const TORSO_RADIUS = 0.26;
const TORSO_LENGTH = 0.45;
const HEAD_RADIUS = 0.17;
const SHORTS = "#14181f";
/** Figures are drawn larger than life, as broadcast graphics do, so they read at the wide camera distance. */
const FIGURE_SCALE = 1.5;
const STAND = "#0d1620";
const STAND_DEPTH = 26;
const STAND_RAKE = 0.6;
const STAND_GAP = 7;
const STAND_BASE = 0.5;
const STAND_TEXTURE_PX = 256;
const CROWD_PX_PER_M = 6;
const CROWD_ROW_PX = 6;
const CROWD_SEAT_PX = 4;
const CROWD_SEED = 7;
const CROWD_COLOURS = ["#1e2a38", "#2b3a4d", "#3a4a5e", "#4b5563", "#6b7280", "#1f3b4d", "#3b2f2f", "#2d3b2d"];
const BALL_RADIUS = 0.4;
const GRASS = "#1d6b34";
const GRASS_STRIPE = "#237a3d";
const RUNOFF = "#174f29";
const LINE = "rgba(255,255,255,0.85)";
const SKIN = "#d9b38c";
const KEEPER = "#facc15";
const NET_OPACITY = 0.25;

function spot(ctx: CanvasRenderingContext2D, x: number, y: number, radius: number): void {
  ctx.beginPath();
  ctx.arc(x, y, radius, 0, Math.PI * 2);
  ctx.fillStyle = LINE;
  ctx.fill();
}

function drawMarkings(ctx: CanvasRenderingContext2D, s: number): void {
  const length = PITCH_LENGTH * s;
  const width = PITCH_WIDTH * s;
  ctx.strokeStyle = LINE;
  ctx.lineWidth = LINE_M * s;
  ctx.strokeRect(0, 0, length, width);
  ctx.beginPath();
  ctx.moveTo(length / 2, 0);
  ctx.lineTo(length / 2, width);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(length / 2, width / 2, CENTRE_CIRCLE_M * s, 0, Math.PI * 2);
  ctx.stroke();
  for (const [x, dir] of [[0, 1], [length, -1]] as const) {
    for (const area of [PENALTY_AREA, GOAL_AREA]) {
      ctx.strokeRect(dir > 0 ? x : x - area.depth * s, area.top * s, area.depth * s, area.width * s);
    }
    spot(ctx, x + dir * PENALTY_SPOT_M * s, width / 2, SPOT_RADIUS_M * s);
  }
  spot(ctx, length / 2, width / 2, SPOT_RADIUS_M * s);
}

/** The grass with runoff, mowing stripes, and markings, lying flat at y = 0. */
export function buildPitch(): THREE.Mesh {
  const s = TEXTURE_PX_PER_M;
  const fullLength = PITCH_LENGTH + 2 * RUNOFF_M;
  const fullWidth = PITCH_WIDTH + 2 * RUNOFF_M;
  const canvas = document.createElement("canvas");
  canvas.width = fullLength * s;
  canvas.height = fullWidth * s;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = RUNOFF;
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.translate(RUNOFF_M * s, RUNOFF_M * s);
    const stripe = (PITCH_LENGTH / STRIPES) * s;
    for (let i = 0; i < STRIPES; i += 1) {
      ctx.fillStyle = i % 2 ? GRASS_STRIPE : GRASS;
      ctx.fillRect(i * stripe, 0, stripe, PITCH_WIDTH * s);
    }
    drawMarkings(ctx, s);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  texture.anisotropy = 8;
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(fullLength, fullWidth),
    new THREE.MeshStandardMaterial({ map: texture }));
  mesh.rotation.x = -Math.PI / 2;
  mesh.receiveShadow = true;
  return mesh;
}

function post(length: number, material: THREE.Material): THREE.Mesh {
  const mesh = new THREE.Mesh(new THREE.CylinderGeometry(POST_RADIUS, POST_RADIUS, length, 10), material);
  mesh.castShadow = true;
  return mesh;
}

/** A goal frame with a translucent net, its mouth on the goal line at world x, the net behind the line. */
export function buildGoal(x: number, facing: 1 | -1): THREE.Group {
  const group = new THREE.Group();
  const white = new THREE.MeshStandardMaterial({ color: "#ffffff" });
  for (const z of [-GOAL_WIDTH / 2, GOAL_WIDTH / 2]) {
    const upright = post(GOAL_HEIGHT, white);
    upright.position.set(0, GOAL_HEIGHT / 2, z);
    group.add(upright);
  }
  const bar = post(GOAL_WIDTH, white);
  bar.rotation.x = Math.PI / 2;
  bar.position.set(0, GOAL_HEIGHT, 0);
  group.add(bar);
  const net = new THREE.Mesh(new THREE.BoxGeometry(GOAL_DEPTH, GOAL_HEIGHT, GOAL_WIDTH),
    new THREE.MeshBasicMaterial({ color: "#ffffff", wireframe: true, transparent: true, opacity: NET_OPACITY }));
  net.position.set(-facing * GOAL_DEPTH / 2, GOAL_HEIGHT / 2, 0);
  group.add(net);
  group.position.x = x;
  return group;
}

/** Names of a figure's parts the animation loop moves. */
export const LEFT_LEG = "left-leg";
export const RIGHT_LEG = "right-leg";

function leg(name: string, side: number, material: THREE.Material): THREE.Group {
  const pivot = new THREE.Group();
  pivot.name = name;
  pivot.position.set(0, HIP_HEIGHT, side * HIP_SPREAD);
  const limb = new THREE.Mesh(new THREE.CylinderGeometry(LEG_RADIUS, LEG_RADIUS * 0.8, HIP_HEIGHT, 8), material);
  limb.position.y = -HIP_HEIGHT / 2;
  limb.castShadow = true;
  pivot.add(limb);
  return pivot;
}

/** A player figure facing +z: kit-coloured shirt, dark shorts, legs that can swing, and a head. */
export function buildPlayer(color: string, goalkeeper: boolean): THREE.Group {
  const group = new THREE.Group();
  const shirt = new THREE.MeshStandardMaterial({ color: goalkeeper ? KEEPER : color, roughness: 0.6 });
  const dark = new THREE.MeshStandardMaterial({ color: SHORTS, roughness: 0.7 });
  const torso = new THREE.Mesh(new THREE.CapsuleGeometry(TORSO_RADIUS, TORSO_LENGTH, 4, 10), shirt);
  torso.position.y = HIP_HEIGHT + SHORTS_HEIGHT + TORSO_LENGTH / 2;
  torso.castShadow = true;
  const shorts = new THREE.Mesh(new THREE.CylinderGeometry(TORSO_RADIUS, TORSO_RADIUS * 1.05, SHORTS_HEIGHT, 10), dark);
  shorts.position.y = HIP_HEIGHT + SHORTS_HEIGHT / 2;
  shorts.castShadow = true;
  const head = new THREE.Mesh(new THREE.SphereGeometry(HEAD_RADIUS, 12, 10),
    new THREE.MeshStandardMaterial({ color: SKIN, roughness: 0.8 }));
  head.position.y = HIP_HEIGHT + SHORTS_HEIGHT + TORSO_LENGTH + TORSO_RADIUS + HEAD_RADIUS;
  head.castShadow = true;
  group.add(torso, shorts, head, leg(LEFT_LEG, -1, dark), leg(RIGHT_LEG, 1, dark));
  group.scale.setScalar(FIGURE_SCALE);
  return group;
}

function crowdTexture(width: number, height: number): THREE.CanvasTexture {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.fillStyle = STAND;
    ctx.fillRect(0, 0, width, height);
    let seed = CROWD_SEED;
    for (let y = 2; y < height; y += CROWD_ROW_PX) {
      for (let x = 1; x < width; x += CROWD_SEAT_PX) {
        seed = (seed * 16807) % 2147483647;
        ctx.fillStyle = CROWD_COLOURS[seed % CROWD_COLOURS.length];
        ctx.fillRect(x, y, CROWD_SEAT_PX - 1, CROWD_ROW_PX - 2);
      }
    }
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function stand(length: number): THREE.Mesh {
  const mesh = new THREE.Mesh(new THREE.PlaneGeometry(length, STAND_DEPTH),
    new THREE.MeshStandardMaterial({ map: crowdTexture(Math.round(length * CROWD_PX_PER_M), STAND_TEXTURE_PX),
                                     roughness: 1 }));
  mesh.rotation.x = -STAND_RAKE;
  return mesh;
}

/** Raked stands with a crowd behind the far touchline and both goal lines. */
export function buildStands(): THREE.Group {
  const group = new THREE.Group();
  const lift = Math.sin(STAND_RAKE) * STAND_DEPTH / 2;
  const back = Math.cos(STAND_RAKE) * STAND_DEPTH / 2;
  const far = stand(PITCH_LENGTH + 2 * STAND_GAP);
  far.position.set(0, lift + STAND_BASE, -(PITCH_WIDTH / 2 + STAND_GAP + back));
  group.add(far);
  for (const side of [-1, 1]) {
    const end = stand(PITCH_WIDTH + 2 * STAND_GAP);
    end.rotation.set(-STAND_RAKE, 0, 0, "YXZ");
    end.rotation.y = side * -Math.PI / 2;
    end.position.set(side * (PITCH_LENGTH / 2 + STAND_GAP + back), lift + STAND_BASE, 0);
    group.add(end);
  }
  return group;
}

/** The ball, resting on the grass. */
export function buildBall(): THREE.Mesh {
  const ball = new THREE.Mesh(new THREE.SphereGeometry(BALL_RADIUS, 16, 12),
    new THREE.MeshStandardMaterial({ color: "#ffffff", emissive: "#444444", roughness: 0.4 }));
  ball.position.y = BALL_RADIUS;
  ball.castShadow = true;
  return ball;
}

/** Height above the ground where a player's name tag is anchored. */
export const TAG_HEIGHT = (HIP_HEIGHT + SHORTS_HEIGHT + TORSO_LENGTH + TORSO_RADIUS + HEAD_RADIUS * 2) * FIGURE_SCALE + 0.5;

/** Free every geometry and material under an object. */
export function disposeTree(root: THREE.Object3D): void {
  root.traverse((node) => {
    if (node instanceof THREE.Mesh) {
      node.geometry.dispose();
      const materials = Array.isArray(node.material) ? node.material : [node.material];
      materials.forEach((m: THREE.Material & { map?: THREE.Texture | null }) => {
        m.map?.dispose();
        m.dispose();
      });
    }
  });
}
