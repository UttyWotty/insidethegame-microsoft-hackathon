/**
 * Pure summary of the problems recorded on a moment's cue provenance, one labelled line per output, for the producer.
 * Shared outputs such as the explanation and commentary appear once, however many audiences received them.
 * Per-viewer outputs (card, translation) are grouped by problems, named by segment (persona, language, club, player)
 * only when not all are hit, and every line carries a unique stable id for list rendering.
 */
import type { OverlayCue } from "../types";

/** Outputs whose provenance can carry problems, in display order, with their on-screen labels. */
export const PROBLEM_OUTPUTS: readonly { key: string; label: string; perViewer: boolean }[] = [
  { key: "explanation", label: "Explanation", perViewer: false },
  { key: "commentary", label: "Commentary", perViewer: false },
  { key: "card", label: "Card", perViewer: true },
  { key: "translation", label: "Translation", perViewer: true },
];

/**
 * One labelled line, e.g. label "Card", audiences ["casual fr"], problems ["template failed"].
 * The id names the output and every segment in the group (shown or not), so it is unique within a moment.
 */
export interface ProblemLine { id: string; key: string; label: string; audiences: string[]; problems: string[] }

const PROBLEM_SEPARATOR = "; ";
const LIST_SEPARATOR = ", ";
const AUDIENCE_SEPARATOR = " ";
const ID_SEPARATOR = "|";
/** Separator between parts of a segment id ("persona-language-club-player"). */
const SEGMENT_SEPARATOR = "-";
/** Segment id token for an unset club or player. */
const NONE_TOKEN = "none";

function unique(values: string[]): string[] {
  return [...new Set(values)];
}

/** Region suffix of a language code in a segment id, e.g. "GB" in "en-GB". */
const REGION_PATTERN = /^[A-Z]{2}$/;

/**
 * Language, club and player tokens of a segment id "persona-language-club-player", or null for other ids.
 * The segment's language is used rather than the cue's, because untranslated (degraded) cues report English.
 */
function segmentParts(cue: OverlayCue): string[] | null {
  const prefix = `${cue.persona}${SEGMENT_SEPARATOR}`;
  if (!cue.viewer_id.startsWith(prefix)) return null;
  const tokens = cue.viewer_id.slice(prefix.length).split(SEGMENT_SEPARATOR);
  if (!tokens[0]) return null;
  const regionLength = tokens.length > 1 && REGION_PATTERN.test(tokens[1]) ? 2 : 1;
  const language = tokens.slice(0, regionLength).join(SEGMENT_SEPARATOR);
  return [language, ...tokens.slice(regionLength).filter((t) => t && t !== NONE_TOKEN)];
}

/** The cue's audience as the console names segments, e.g. "superfan es kba" or "analyst fr". */
export function audience(cue: OverlayCue): string {
  const parts = segmentParts(cue) ?? [cue.language];
  return [cue.persona.replace(/_/g, " "), ...parts].join(AUDIENCE_SEPARATOR);
}

function linesFor(cues: OverlayCue[], output: (typeof PROBLEM_OUTPUTS)[number]): ProblemLine[] {
  const groups = new Map<string, { problems: string[]; audiences: string[]; viewers: string[] }>();
  const affected = cues.filter((c) => (c.provenance[output.key]?.problems ?? []).length > 0);
  for (const cue of affected) {
    const problems = unique(cue.provenance[output.key]?.problems ?? []);
    const id = output.perViewer ? problems.join("\n") : "";
    const group = groups.get(id) ?? { problems: [], audiences: [], viewers: [] };
    group.viewers = unique([...group.viewers, cue.viewer_id]);
    group.problems = unique([...group.problems, ...problems]);
    group.audiences = unique([...group.audiences, audience(cue)]);
    groups.set(id, group);
  }
  const withOutput = cues.filter((c) => c.provenance[output.key] !== undefined).length;
  return [...groups.values()].map((g) => ({
    id: [output.key, ...g.viewers].join(ID_SEPARATOR), key: output.key, label: output.label, problems: g.problems,
    audiences: output.perViewer && g.audiences.length < withOutput ? g.audiences : [],
  }));
}

/** Labelled problem lines for a moment's cues; empty when no output recorded any problem. */
export function outcomeProblems(cues: OverlayCue[]): ProblemLine[] {
  return PROBLEM_OUTPUTS.flatMap((output) => linesFor(cues, output));
}

/** The line's label with any affected audiences, e.g. "Card (analyst fr, casual fr)". */
export function problemLabel(line: ProblemLine): string {
  return line.audiences.length ? `${line.label} (${line.audiences.join(LIST_SEPARATOR)})` : line.label;
}

/** The line's problems as one string, e.g. "workflow degraded; template failed". */
export function problemText(line: ProblemLine): string {
  return line.problems.join(PROBLEM_SEPARATOR);
}
