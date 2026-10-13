/**
 * 3D broadcast view of the synthetic match: players as figures in club colours, the ball, goals, and a TV camera
 * on the near touchline that pans to follow the ball. Players glide between tracking frames like the 2D pitch,
 * name and sprint tags float above the players in the action, and overlays sit on top anchored to the ball.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import * as THREE from "three";
import type { BallAnchor, PlayerDot } from "../Pitch";
import { PITCH_LENGTH } from "../../lib/pitch";
import {
  approach, approachAngle, behindGoalCamera, broadcastCamera, CAMERA_HALF_LIFE_MS, glideAt, heading, legSwing, pitchToWorld, type Glide,
} from "../../lib/scene3d";
import type { Point } from "../../types";
import {
  buildBall, buildGoal, buildPitch, buildPlayer, buildStands, disposeTree, LEFT_LEG, RIGHT_LEG, TAG_HEIGHT,
} from "./sceneObjects";
import { buildTactics } from "./tacticsObjects";
import type { Tactics } from "../../lib/tactics";

const FOV = 34;
const NEAR = 0.5;
const FAR = 400;
const ASPECT = 16 / 9;
const ANCHOR_EVERY_MS = 200;
const PERCENT = 100;
const SHADOW_SIZE = 2048;
const SHADOW_EXTENT = 70;
const TURN_HALF_LIFE_MS = 120;
/** Running cadence: radians of leg phase per metre covered. */
const STRIDE_PER_M = 2.4;

interface Pitch3DProps {
  ball: Point | null; players: PlayerDot[]; moveMs: number; homeColor: string; awayColor: string; label: string;
  onBallAnchor: (anchor: BallAnchor) => void; children?: ReactNode;
  /** Replay angle: the camera sits behind this goal instead of on the touchline; null (default) is live. */
  behindGoal?: "left" | "right" | null;
  /** Tactical overlay drawn on the grass; null (default) draws none. */
  tactics?: Tactics | null;
}

interface Figure { group: THREE.Group; glide: Glide; facing: number; colorKey: string; phase: number; last: Point }

interface SceneState {
  renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera; ball: THREE.Mesh;
  ballGlide: Glide; figures: Map<string, Figure>; aim: THREE.Vector3; frame: number; lastFrame: number;
  lastAnchor: number; observer: ResizeObserver; tactics: THREE.Group | null;
}

function stillGlide(point: Point): Glide {
  return { from: point, to: point, startedAt: 0, durationMs: 0 };
}

function setupScene(mount: HTMLDivElement): SceneState {
  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  mount.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  scene.background = new THREE.Color("#0a1622");
  scene.fog = new THREE.Fog("#0a1622", 120, 260);
  scene.add(new THREE.HemisphereLight("#dfefff", "#1b3a22", 1.1));
  const sun = new THREE.DirectionalLight("#ffffff", 1.6);
  sun.position.set(-30, 60, 25);
  sun.castShadow = true;
  sun.shadow.mapSize.set(SHADOW_SIZE, SHADOW_SIZE);
  Object.assign(sun.shadow.camera, { left: -SHADOW_EXTENT, right: SHADOW_EXTENT, top: SHADOW_EXTENT, bottom: -SHADOW_EXTENT });
  scene.add(sun);
  scene.add(buildPitch(), buildStands(), buildGoal(-PITCH_LENGTH / 2, 1), buildGoal(PITCH_LENGTH / 2, -1));
  const ball = buildBall();
  scene.add(ball);
  const camera = new THREE.PerspectiveCamera(FOV, ASPECT, NEAR, FAR);
  const start = broadcastCamera(null);
  // The camera eases to its target every frame, so a replay angle cuts in smoothly from wherever it starts.
  camera.position.set(start.position.x, start.position.y, start.position.z);
  const aim = new THREE.Vector3(start.target.x, start.target.y, start.target.z);
  camera.lookAt(aim);
  const observer = new ResizeObserver(() => {
    const width = mount.clientWidth;
    renderer.setSize(width, width / ASPECT);
  });
  observer.observe(mount);
  return { renderer, scene, camera, ball, ballGlide: stillGlide({ x: PITCH_LENGTH / 2, y: 34 }), figures: new Map(),
           aim, frame: 0, lastFrame: performance.now(), lastAnchor: 0, observer, tactics: null };
}

/** Move the camera toward its live broadcast position, or a replay angle behind a goal, smoothly. */
function steerCamera(state: SceneState, ball: Point, elapsed: number, behindGoal: "left" | "right" | null): void {
  const want = behindGoal ? behindGoalCamera(ball, behindGoal) : broadcastCamera(ball);
  const { camera, aim } = state;
  const ease = (from: number, to: number) => approach(from, to, elapsed, CAMERA_HALF_LIFE_MS);
  camera.position.set(ease(camera.position.x, want.position.x), ease(camera.position.y, want.position.y),
                      ease(camera.position.z, want.position.z));
  aim.set(ease(aim.x, want.target.x), 0, ease(aim.z, want.target.z));
  camera.lookAt(aim);
}

function project(state: SceneState, point: Point, height: number): { x: number; y: number } {
  const world = pitchToWorld(point, height);
  const v = new THREE.Vector3(world.x, world.y, world.z).project(state.camera);
  return { x: (v.x + 1) / 2, y: (1 - v.y) / 2 };
}

export default function Pitch3D(props: Pitch3DProps) {
  const { ball, players, moveMs, homeColor, awayColor, label, children } = props;
  const mountRef = useRef<HTMLDivElement>(null);
  const stateRef = useRef<SceneState | null>(null);
  const tagRefs = useRef(new Map<string, HTMLSpanElement>());
  const anchorRef = useRef(props.onBallAnchor);
  anchorRef.current = props.onBallAnchor;
  const angleRef = useRef(props.behindGoal ?? null);
  angleRef.current = props.behindGoal ?? null;
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;
    let state: SceneState;
    try {
      state = setupScene(mount);
    } catch {
      setFailed(true);
      return undefined;
    }
    stateRef.current = state;
    const loop = () => {
      const now = performance.now();
      const elapsed = now - state.lastFrame;
      state.lastFrame = now;
      for (const figure of state.figures.values()) {
        const at = glideAt(figure.glide, now);
        const world = pitchToWorld(at);
        figure.group.position.set(world.x, 0, world.z);
        const step = Math.hypot(at.x - figure.last.x, at.y - figure.last.y);
        figure.phase += step * STRIDE_PER_M;
        figure.last = at;
        const swing = legSwing(figure.phase, step > 0.001);
        figure.group.getObjectByName(LEFT_LEG)?.rotation.set(swing, 0, 0);
        figure.group.getObjectByName(RIGHT_LEG)?.rotation.set(-swing, 0, 0);
        const turn = heading(figure.glide.from, figure.glide.to);
        if (turn !== null) figure.facing = approachAngle(figure.facing, turn, elapsed, TURN_HALF_LIFE_MS);
        figure.group.rotation.y = figure.facing;
      }
      const ballAt = glideAt(state.ballGlide, now);
      const ballWorld = pitchToWorld(ballAt, state.ball.position.y);
      state.ball.position.set(ballWorld.x, ballWorld.y, ballWorld.z);
      steerCamera(state, ballAt, elapsed, angleRef.current);
      state.renderer.render(state.scene, state.camera);
      for (const [id, element] of tagRefs.current) {
        const figure = state.figures.get(id);
        if (!figure) continue;
        const spot = project(state, glideAt(figure.glide, now), TAG_HEIGHT);
        element.style.left = `${spot.x * PERCENT}%`;
        element.style.top = `${spot.y * PERCENT}%`;
      }
      if (now - state.lastAnchor > ANCHOR_EVERY_MS) {
        state.lastAnchor = now;
        const spot = project(state, ballAt, 0);
        anchorRef.current({ left: `${spot.x * PERCENT}%`, top: `${spot.y * PERCENT}%` });
      }
      state.frame = requestAnimationFrame(loop);
    };
    state.frame = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(state.frame);
      state.observer.disconnect();
      disposeTree(state.scene);
      state.renderer.dispose();
      state.renderer.domElement.remove();
      stateRef.current = null;
    };
  }, []);

  useEffect(() => {
    const state = stateRef.current;
    if (!state) return;
    const now = performance.now();
    const seen = new Set<string>();
    for (const dot of players) {
      seen.add(dot.id);
      const color = dot.side === "home" ? homeColor : awayColor;
      const colorKey = `${color}-${dot.goalkeeper}`;
      let figure = state.figures.get(dot.id);
      if (figure && figure.colorKey !== colorKey) {
        state.scene.remove(figure.group);
        disposeTree(figure.group);
        figure = undefined;
      }
      if (!figure) {
        figure = { group: buildPlayer(color, dot.goalkeeper), glide: stillGlide(dot.position), facing: 0, colorKey,
                   phase: 0, last: dot.position };
        state.scene.add(figure.group);
        state.figures.set(dot.id, figure);
      }
      figure.glide = { from: glideAt(figure.glide, now), to: dot.position, startedAt: now, durationMs: moveMs };
    }
    for (const [id, figure] of state.figures) {
      if (!seen.has(id)) {
        state.scene.remove(figure.group);
        disposeTree(figure.group);
        state.figures.delete(id);
      }
    }
    if (ball) state.ballGlide = { from: glideAt(state.ballGlide, now), to: ball, startedAt: now, durationMs: moveMs };
  }, [players, ball, moveMs, homeColor, awayColor]);

  const { tactics = null } = props;
  useEffect(() => {
    const state = stateRef.current;
    if (!state) return;
    if (state.tactics) {
      state.scene.remove(state.tactics);
      disposeTree(state.tactics);
      state.tactics = null;
    }
    if (tactics) {
      state.tactics = buildTactics(tactics, homeColor, awayColor);
      state.scene.add(state.tactics);
    }
  }, [tactics, homeColor, awayColor]);

  const tagged = players.filter((p) => p.tagged || p.tracked || p.sprintKmh !== null || p.popup);
  return (
    <div className="pitch-wrap cam-3d" role="img" aria-label={label}>
      <div ref={mountRef} className="pitch3d-canvas" />
      {failed && <p className="pitch3d-fallback">The 3D view needs WebGL; switch to the broadcast or tactical camera.</p>}
      <div className="pitch3d-tags" aria-hidden="true">
        {tagged.map((p) => (
          <span key={p.id} className="pitch3d-tag" ref={(el) => {
            if (el) tagRefs.current.set(p.id, el);
            else tagRefs.current.delete(p.id);
          }}>
            {p.popup && <span className="pitch3d-popup">{p.popup}</span>}
            {p.sprintKmh !== null && <span className="pitch3d-speed">{p.sprintKmh.toFixed(1)} km/h</span>}
            {p.shortName}
          </span>
        ))}
      </div>
      {children}
    </div>
  );
}
