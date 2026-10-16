/**
 * Human-readable labels for key moment kinds, shared by the producer console and other views.
 * Internal identifiers such as distance_threshold never reach the screen.
 * Unknown kinds fall back to a spaced version of the identifier.
 */
const MOMENT_LABELS: Record<string, string> = {
  goal: "Goal", big_chance_missed: "Big chance missed", great_save: "Great save", speed_threshold: "Thunderous strike",
  distance_threshold: "Long-range play", difficult_pass: "Defence-splitting pass", momentum_swing: "Momentum swing",
  chaos_spell: "Chaotic spell", milestone: "Milestone", tactical_pattern: "Tactical Scout flag",
};

export function momentLabel(kind: string): string {
  return MOMENT_LABELS[kind] ?? kind.replace(/_/g, " ");
}
