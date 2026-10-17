/**
 * React hook that places the highlights caption clear of a story clip's action in the measured pitch view.
 * It measures the overlay layer and two hidden twins of the caption, one full width and one compact, so each layout's
 * height is read on its own (re-measuring on resize), and hands them to the pure captionPlacement rule.
 * Measurements are taken in a layout effect, so a moved caption is never painted in its old place first.
 */
import { type RefObject, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { HighlightClip } from "../types";
import {
  type CaptionCamera, type CaptionHeights, type CaptionTargets, type CaptionPlacement, captionPlacement, storyTargets,
} from "./captionPlacement";
import type { ViewSize } from "./viewProjection";

/** Class the caption carries while compact. */
export const COMPACT_CLASS = "compact";
/** Class of the hidden twins the hook measures: laid out like the caption but never seen or read out. */
export const MEASURE_CLASS = "caption-measure";

/** No clip on screen: nothing to avoid. */
const NO_TARGETS: CaptionTargets = { action: [], players: [] };

interface Measured { view: ViewSize; caption: CaptionHeights }

/** Nothing measured yet: the rule keeps the default placement until the first layout pass. */
const UNMEASURED: Measured = { view: { widthPx: 0, heightPx: 0 }, caption: { fullPx: 0, compactPx: 0 } };

function sameMeasure(a: Measured, b: Measured): boolean {
  return a.view.widthPx === b.view.widthPx && a.view.heightPx === b.view.heightPx
    && a.caption.fullPx === b.caption.fullPx && a.caption.compactPx === b.caption.compactPx;
}

/** Refs for the two hidden twins: the caption laid out full width and laid out compact. */
export interface MeasureRefs {
  fullRef: RefObject<HTMLDivElement | null>;
  compactRef: RefObject<HTMLDivElement | null>;
}

/**
 * The twin refs to attach and the placement for a clip (null clip: default placement), measured before paint.
 * tickMs is the reel player's tick, so the action points match the moments it draws.
 */
export function useCaptionPlacement(clip: HighlightClip | null, camera: CaptionCamera, tickMs: number):
  MeasureRefs & { placement: CaptionPlacement } {
  const fullRef = useRef<HTMLDivElement | null>(null);
  const compactRef = useRef<HTMLDivElement | null>(null);
  const [measured, setMeasured] = useState<Measured>(UNMEASURED);
  const targets = useMemo(() => (clip ? storyTargets(clip, tickMs) : NO_TARGETS), [clip, tickMs]);

  useLayoutEffect(() => {
    const full = fullRef.current;
    const compact = compactRef.current;
    const layer = full?.parentElement;
    if (!full || !compact || !layer) return undefined;
    const measure = () => {
      const next: Measured = {
        view: { widthPx: layer.clientWidth, heightPx: layer.clientHeight },
        caption: { fullPx: full.offsetHeight, compactPx: compact.offsetHeight },
      };
      setMeasured((current) => (sameMeasure(current, next) ? current : next));
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(layer);
    observer.observe(full);
    observer.observe(compact);
    return () => observer.disconnect();
  }, [clip, camera]);

  const placement = useMemo(() => captionPlacement(targets, camera, measured.view, measured.caption),
    [targets, camera, measured]);
  return { fullRef, compactRef, placement };
}
