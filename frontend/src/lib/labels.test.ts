/**
 * Tests for moment kind labels.
 * They ensure internal identifiers are always replaced by readable text.
 * The labels module is pure.
 */
import { describe, expect, it } from "vitest";
import { momentLabel } from "./labels";

describe("momentLabel", () => {
  it("maps known kinds and spaces unknown ones", () => {
    expect(momentLabel("distance_threshold")).toBe("Long-range play");
    expect(momentLabel("tactical_pattern")).toBe("Tactical Scout flag");
    expect(momentLabel("threat_created")).toBe("Line-breaking pass");
    expect(momentLabel("shape_shift")).toBe("Shape shift");
    expect(momentLabel("new_kind")).toBe("new kind");
  });
});
