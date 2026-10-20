/**
 * Tests for the instant replay analysis overlay labels and geometry.
 * They check the analyst and casual rows, the optional speed and assist, the labels, and the period flip.
 * All logic is pure.
 */
import { describe, expect, it } from "vitest";
import { analysisRows, assistLabel, buildUpLabel, coneScreen, pathIndex, pathScreen } from "./replayAnalysis";
import type { ReplayAnalysis, ReplayKeyframe } from "../types";

const analysis: ReplayAnalysis = {
  shot_event_id: "s1", shooter_id: "h11", team_id: "kba",
  card: { result: "goal", xg: 0.07, speed_kmh: 81.8, distance_m: 10.9, angle_deg: 35.4, placement_y: 1.69,
    placement_z: 1.75, keeper_y: 0.76 },
  xg: 0.075, goal_chance_pct: 8, under_pressure: false, cone: [[94.77, 37.78], [105, 30.34], [105, 37.66]],
  defenders_in_cone: 0, keeper_in_cone: true,
  build_up: { passes: 6, duration_s: 31.4, xt_added: 0.029, path: [[84.58, 7.56], [99, 3.64], [94.77, 37.78]] },
  assist: { passer_id: "h9", length_m: 34.4, difficulty: 49.1, xt_added: 0.019, opponents_bypassed: 5,
    lines_broken: ["defence"], breaks_line: true },
};
const names = { h9: "Theo Marsh", h11: "Ari Vale" };
const labels = (rows: [string, string][]) => rows.map(([label]) => label);

describe("replay analysis", () => {
  it("gives the analyst the full set of shot facts", () => {
    const rows = analysisRows(analysis, "analyst", names);
    expect(labels(rows)).toEqual(["Result", "xG", "Goal chance", "Distance", "Angle", "Speed", "In the cone",
      "Pressure", "Build-up", "xT built", "Assist"]);
    const value = Object.fromEntries(rows);
    expect(value.xG).toBe("0.075");
    expect(value["Goal chance"]).toBe("8%");
    expect(value["In the cone"]).toBe("0 defenders, keeper");
    expect(value["Build-up"]).toBe("6 passes in 31 s");
    expect(value["xT built"]).toBe("+0.029");
    expect(value.Assist).toBe("Theo Marsh, 34 m, xT +0.019, broke the defence line, 5 bypassed");
  });

  it("gives other personas exactly the plain subset", () => {
    const rows = analysisRows(analysis, "casual", names);
    expect(labels(rows)).toEqual(["Goal chance", "Distance", "Speed", "Build-up", "Assist"]);
    expect(Object.fromEntries(rows).Assist).toBe("Theo Marsh");
    expect(Object.fromEntries(rows)["Build-up"]).toBe("6 passes");
  });

  it("omits speed and assist when they are null", () => {
    const bare = { ...analysis, card: { ...analysis.card, speed_kmh: null }, assist: null };
    expect(labels(analysisRows(bare, "casual", names))).toEqual(["Goal chance", "Distance", "Build-up"]);
    expect(labels(analysisRows(bare, "analyst", names))).not.toContain("Speed");
    expect(labels(analysisRows(bare, "analyst", names))).not.toContain("Assist");
  });

  it("labels the build-up and an assist without a line break or stored threat", () => {
    expect(buildUpLabel({ ...analysis, build_up: { ...analysis.build_up, passes: 1, duration_s: 4.4 } }))
      .toBe("1 pass in 4 s");
    const plain = { ...analysis.assist!, xt_added: null, breaks_line: false, opponents_bypassed: null, lines_broken: [] };
    expect(assistLabel({ ...analysis, assist: plain }, {})).toBe("h9, 34 m");
    expect(assistLabel({ ...analysis, assist: null }, names)).toBeNull();
  });

  it("draws the cone and path as they are in the first half and flipped in the second", () => {
    expect(coneScreen(analysis, 1)[1]).toEqual({ x: 105, y: 30.34 });
    expect(coneScreen(analysis, 2)[1].x).toBeCloseTo(0);
    expect(coneScreen(analysis, 2)[1].y).toBeCloseTo(37.66);
    expect(pathScreen(analysis, 1, 1)).toEqual([{ x: 84.58, y: 7.56 }, { x: 99, y: 3.64 }]);
    const flipped = pathScreen(analysis, 2, 0);
    expect(flipped).toHaveLength(1);
    expect(flipped[0].x).toBeCloseTo(20.42);
    expect(flipped[0].y).toBeCloseTo(60.44);
  });

  it("keeps a pass's path point through its reception keyframe", () => {
    const keyframe = (event_type: string, phase: ReplayKeyframe["phase"] = "build_up"): ReplayKeyframe => ({
      period: 1, match_second: 0, phase, event_type, player_id: null, receiver_id: null, ball: [0, 0], positions: [],
    });
    const frames = [keyframe("pass"), keyframe("reception"), keyframe("carry"), keyframe("pass"),
      keyframe("reception"), keyframe("shot", "shot")];
    expect(frames.map((_, i) => pathIndex(frames, i))).toEqual([0, 0, 1, 2, 2, 3]);
  });

  it("shows the replay xG at three decimals, the same value goal chance is computed from", () => {
    const value = Object.fromEntries(analysisRows(analysis, "analyst", names));
    expect(value.xG).toBe("0.075");
    expect(value["Goal chance"]).toBe("8%");
    expect(Math.round(Number(value.xG) * 100)).toBe(analysis.goal_chance_pct);
  });
});
