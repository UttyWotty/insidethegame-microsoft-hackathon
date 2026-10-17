<!--
This file records all notable changes to the project in Keep a Changelog format.
Entries are added under Unreleased by each feature pull request.
Releases move those entries under a versioned, dated heading.
-->

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Degraded-path resilience: `degraded_broadcast` now guards each template separately. If the explanation
  template raises, a minimal grounded explanation (`<minute> <kind title>` plus a fixed sentence, no evidence) is used;
  a failing commentary template falls back to the explanation headline; a failing persona card template affects only
  that viewer, who gets a minimal headline card fitted to the persona's budget. Each fallback is logged with its
  traceback and noted as `template failed` on the outcome (source stays fallback), so a moment is never lost when
  both the workflow and a template fail. Pure builders live in `orchestration/minimal_outputs.py`.
- Demo-story scorer and seed search: the pure `datasets/demo_story.py` checks eight hard rules a demo match must
  meet (at most 9 Scout flags; a home go-ahead goal from 6 m or more linked to a home flank flag 3 to 12 minutes
  earlier; a later dropped shape shift by the leader with falling control; a replayed big save; a passing build-up;
  and the winner's auto replay not dropped at 30x, using the frontend's replay drop rule) and scores preferences
  (held winner, comeback, late goal, quick payoff, exploited weak flank, save replay, build-up). The CLI
  `python -m insidegame.datasets.demo_search --start-seed 1 --end-seed 4000 --top 10` prints a deterministic
  Markdown table of the passing seeds; 3 of 4000 passed under the old replay drop rule (6 under the replay queue),
  and seed 1407 is the demo seed.
- `tests/test_finishing_realism.py`: permanent realism checks over seeds 1-60 (carry stop bound, walk-in shots at
  most 1% of shots and 2% of goals, goal share under 6 m at most 25%, 6-18 m at least 60%) and a tracked check
  over seeds 1-20 that the keeper stands nearer the goal line than a close shooter (99.0% of shots within 20 m).

- Team shape and shape shifts: pure shape metrics per team (`analytics/shape.py`: back-line height, length, width,
  compactness, and a high, mid, or low block) measured out of possession from the tracked positions before each
  event; a deterministic `ShapeTracker` (`analytics/shape_tracker.py`) that compares the last 10 minutes with the 10
  before and raises a new `shape_shift` key moment when the back line moves 6 m or more for 4 minutes (15-minute
  cooldown per team, reset each period; about 1.1 per match over Kestrel Bay vs Ironvale seeds 1-20). Its facts
  (`analytics/shape_moments.py`) give the line, block, length, and width before and after, the team's space-control
  and possession shares over the same two windows, the score, the goal that triggered it, and who has momentum; on
  the demo match Kestrel Bay's back line drops from 30.9 m to 20.2 m at 88' after going ahead at 77'. The Tactical
  Scout explains shape shifts (routing, one instruction sentence, template, glossary "Defensive line", labels,
  "Shape shift" reel title, excluded from the reel). The snapshot carries each team's `shape` reading, the new MCP
  tool `get_team_shape` (also allowed for the Foundry hosted agent) returns both readings and the last five shifts,
  the Match Companion's context includes each team's line height and block, and the studio payload adds a
  whole-match `shape` timeline with shift marks. The broadcast draws the back line before and now with the block
  outline when a shift airs (labels in the mid-pitch band, clear of the shot card and the offside label), the studio
  shows a back-line height timeline (period-aware, so first-half stoppage minutes sit before the half-time divider),
  and analysts' match stats add back-line and block rows. The tracker treats an empty positions map like no
  positions, leaves unknown players and non-finite points out of space control, and returns no reading for a team
  id outside the match. `docs/DEMO_SCRIPT.md` gains the "Shape shift at 88'" beat.

- Expected threat (xT) possession value: a 12 x 8 grid fitted by value iteration to 480 of our own simulated
  matches (`python -m insidegame.datasets.xt_fit`, generated `analytics/xt_grid.py`, mirror-symmetrised, shots valued
  by our xG model, tackles counted as failed moves) credits every completed pass and carry with the xT it added to
  the player and team (`xt_added` in statistics, snapshots, agent context, and dataset event rows). Line-breaking
  passes: live tracking positions from before each pass give `opponents_bypassed` and the midfield or defensive
  lines broken (strictly from behind every player in the line to beyond every one); counters
  `line_breaking_passes` and `opponents_bypassed` reach the snapshot. A new `threat_created` key moment fires for a
  completed line-breaking pass adding 0.025 xT or more (importance 0.50, one per 5 minutes within a half, about 2.9
  per match over Kestrel Bay vs Ironvale seeds 1-30), with templates, glossary, labels, a "Line-breaking pass" reel
  title, and analyst prompt guidance; difficult and long-pass moments also carry `xt_added`. The snapshot carries a
  `threat_leaders` danger leaderboard, the new MCP tool `get_threat_leaderboard` (also allowed for the Foundry
  hosted agent) returns team xT and the top players, and the Match Companion's context includes the top three. The
  broadcast shows a LINE BREAKER card (top-right, 6 seconds, xT rows for analysts only), a Danger panel beside the
  Physical panel, and analyst-only xT and line-breaking pass rows in the match stats. The calibration report gains
  an expected threat sanity section (four checks, all holding); the reference bands are unchanged.

- Tactical Scout: a deterministic pattern miner (`analytics/patterns.py`, pure rules in
  `analytics/pattern_rules.py`, shared pitch zones in `core/zones.py`) watches a rolling 15-minute window of
  final-third entries and ball wins and raises a new `tactical_pattern` key moment for a flank exposed (6 or more
  completed entries down one wide channel at 85% or more, naming the beaten full-back), a channel overload (7 or more
  successful entries, 60% of them down one channel), or a turnover zone (5 or more ball wins in one zone outside the
  winner's defensive third). Flags are at least 10 minutes apart and the same pattern cools down for 15 minutes,
  about 7 per match. A goal or big chance that comes from a flagged pattern within 15 minutes carries
  `flagged_minute`, `flagged_moment_id`, `flagged_pattern`, and `flagged_summary`. An eighth agent, the Tactical
  Scout (`tactical_scout`), explains the flags: the workflow routes `tactical_pattern` jobs from intake to the
  `scout` executor instead of the Match Analyst, with the same narrator, personalizer, fact-check, and template
  fallback path, and the producer console trace names it. Templates, the newcomer glossary, and recaps know the new
  kind, and the highlights reel never clips a flag. The broadcast shows a Scout card (bottom-right, 8 seconds), the
  flagged zone on the 2D and 3D pitch (15 seconds), and "Scout flagged 31': ..." on the goal banner of a linked goal.

- Live win probability and stat graphics: pure `analytics/win_probability.py` gives home win, draw, and away win
  after every event (`win` in the event message) from the score, the time left, and Poisson goal rates that blend
  a prior (1.55 home, 1.25 away per match) with each team's xG rate so far, weighted by time played; kick-off odds
  are about 45%, 27%, and 28%. The score bug shows it as a three-part bar. Event pop-ups (TACKLE WON,
  INTERCEPTION, SAVE) flash over the player for 1.8 seconds on the 2D and 3D pitch, and a Physical panel ranks
  the top five for distance covered and top speed, accumulated by the tracking model and sent with each snapshot
  (`physical`).
- Live tactics overlay: computed in the browser from the 22 tracked positions (pure `lib/tactics.ts`): the defending
  side's offside line (second-deepest defender, ends swapping at half-time), its outfield block with depth and
  width (both teams when nobody has the ball), a pressure ring when opponents are within 5 m of the ball carrier,
  and arrows to the carrier's three best passing options with a completion chance from length and opponents within
  2.5 m of the lane, coloured safe, risky, or unlikely. Drawn as SVG on the 2D pitch and as flat strips on the 3D
  grass; a Tactics toggle (on by default) hides it.
- Shot card: every shot event now carries a broadcast shot card (`shot` in the event message) with xG, shot speed,
  distance, goal angle, where it crossed the goal line, and the keeper's dive. The simulator decides only the
  outcome, so placement and dive are derived deterministically from the event id with a local random generator,
  consistent with the result (goals beat the keeper in the frame, saves meet the keeper, misses go wide on the
  traced side or over); seeded matches are unchanged. The broadcast shows it as a goal-mouth card for 6.5 seconds,
  with persona overlays stepping aside.
- Instant replays: 3.5 seconds after every goal and every shot of 0.25 xG or more, the broadcast replays the
  stored frames from 6 seconds before to 2.5 seconds after the shot in slow motion (0.6x) from another angle: a
  camera behind the goal the action finished at in the 3D view, or a zoomed crop on the 2D pitch. A REPLAY bug
  wipes in, a caption shows the result, shooter, and xG, the commentator says a short replay line, and live voice
  pauses until it returns to live (or the viewer skips). Served by `GET /api/matches/{id}/replay?period=&at=`;
  an Auto replays toggle turns them off.
- 3D broadcast view: a "3D" camera renders the match with three.js (0.186.1, lazy-loaded into its own chunk, so the
  main bundle is unchanged): striped pitch with markings, goals with nets, raked stands with a crowd, player
  figures in club colours whose legs run with the distance covered and who turn to face their direction of travel,
  and a touchline camera that pans smoothly to follow the ball. Name and sprint tags float above the players in
  the action, overlays stay anchored to the ball, highlights replay in 3D, and browsers without WebGL get a notice.
- Live agent trace in the producer console: the moment workflow now runs as an Agent Framework event stream, and
  executor invoked, completed, and failed events become a per-agent timeline (Intake, Match Analyst, Lead
  Commentator and Personalization Producer in parallel, Standards Editor, Broadcast Translator) with start and
  duration, the outcome read from cue provenance (AI or template, attempts, fact-check verdicts, translations), and
  each agent's handoffs. The newest 12 moments are kept and stream to the console with its state.
- Studio analysis visuals: a Studio view draws space control (nearest-team ownership of a 21 x 14 grid from the
  latest tracking frame, with the players and a summary of each team's share by third), pass networks (players at
  their average pass position, links of three or more completed passes), heat maps of on-ball actions, and
  pressing maps of pressures, tackles, and interceptions, per team, for the whole match or the last 15 minutes.
  "Follow the Analyst" (on by default) lets the Match Analyst's latest tactical theme pick the visual, shown
  beside its explanation with an AI or Template chip. Served by `GET /api/matches/{id}/studio?window=`.
- Automated highlights package: the live session keeps every tracking frame, and
  `GET /api/matches/{id}/highlights?stage=half_time|full_time` (409 until that recap is published) returns a reel
  of every goal plus the most important other moments (up to six, in match order), each cut from 10 seconds
  before to 4 seconds after the moment, with the player named in its facts and the best narration available:
  the viewer segment's own commentary, the produced commentary, or a grounded caption. The broadcast view replays
  the reel on the pitch at real match pace with a broadcast caption and spoken narration (live voice pauses
  meanwhile), opened from "Watch highlights" in the recap dialog or the highlights chips, with pause, previous,
  next, replay, and back to live.
- Realistic player motion and sprint tags: synthetic tracking caps every step at the player's pace-based top speed
  (27 to 35 km/h, three quarters of it off the ball), and players about to act start running so they arrive on
  time (lookahead of up to 8 match seconds), replacing actors teleporting to the ball. On seed 7, no movement now
  exceeds 34 km/h (9% exceeded 36 km/h before), the player on the ball is within 3.4 m of it 90% of the time,
  and players cover about 11.7 km. Live events carry the fastest involved player at 25.2 km/h or more, shown as
  an amber speed tag on the pitch, and the tracking export adds `sprint_player_id` and `sprint_kmh`. Players
  glide over the real time between events, so motion is continuous at any replay speed.
- Excited commentary: play-by-play now calls every goal ("GOAL! ... It's 1-0!") and close calls (big chances saved,
  wide, or blocked), always on air; every line and cue carries an intensity (normal, raised, peak). The Lead
  Commentator matches its energy to the moment, and its template adds the punctuation to match. The voice speeds up
  and lifts its pitch for raised and peak lines (browser speech and Azure SSML prosody), goals interrupt whatever is
  being said, and the ticker emphasises close calls and goals. The client's duplicate "GOAL -" line is removed.
- Simulator calibration: `insidegame.datasets.calibrate` compares goals, xG agreement, shots, on-target share,
  conversion, pass accuracy, and result shares with approximate top-flight reference bands and writes
  `docs/CALIBRATION.md` (all 10 within band over 480 matches); every dataset card now includes the same table.
- Azure AI Speech for spoken commentary: `/api/matches/{id}/speech` returns MP3 from a neural voice per language,
  only for lines the match produced (looked up by reference, never arbitrary text), cached and rate-limited per
  client; keyless via the app's managed identity with the Cognitive Services Speech User role on the existing AI
  Services account (`SPEECH_ENDPOINT` in Bicep). The Voice toggle prefers it and falls back to browser speech.
- Spoken commentary: a Voice toggle on the commentary panel reads lines aloud with the browser's speech synthesis,
  choosing a voice for the viewer's language and speaking only lines in that language, with a two-line queue that
  drops play-by-play first so speech keeps up. Overlay cues now carry `commentary_language`, so an untranslated
  line is never read with a foreign voice.
- Per-client rate limit on starting matches (`MATCH_CREATE_MAX_PER_MINUTE`, default 6): clients are identified by
  the last `X-Forwarded-For` entry (the one the Container Apps proxy appends), so a forged header cannot reset the
  budget; the MCP `start_match` tool shares one budget.
- Backpressure for moment production: moments queue in order for `PARALLEL_MOMENTS` production slots (default 2),
  non-goal moments that fall more than five match minutes behind while queued are skipped, and the producer console
  shows Queued and Skipped (stale) moments plus a skipped count. Previously every moment started at once, so with a
  slow model they all finished late together.
- Dataset export writes `tracking.jsonl`: ball and all 22 player positions every fifth event, in the same absolute
  home frame as the events; the dataset card documents it, and the two-match sample in `data/sample/` is refreshed.
- Landing screen with the value proposition, four differentiators, and a one-click demo match.
- Shot traces on the pitch (xG bubble sized by chance quality, result label) and a full-width GOAL banner in the
  scoring club's colours; the half-time recap closes itself after 15 seconds so play is not covered.
- Producer console: pipeline health tiles, a timeline of every detected moment with air status, full broadcast
  records (analyst reasoning, commentary, every audience's overlay with source and fact-check verdict), and
  human-in-the-loop hold and release of AI overlays, with an optional producer key.
- Standards Editor (fact-checker) agent: a roster rule rejects invented players, then the agent checks
  attribution and outcomes of model-written cards and commentary; rejected cards go back to the personalizer with
  the issues for one revision, then a grounded template replaces anything still wrong. Verdicts are recorded in
  cue provenance and shown as "Fact-checked" or "Corrected by editor" chips.
- Synthetic 22-player tracking: formation-aware positions after every event (teams push and spread in possession,
  compact and shift when defending, press higher by style; actors placed on the ball), streamed with each event.
  Distance covered is realistic (about 11 km per outfield player).
- Broadcast pitch: all 22 players with shirt numbers and live name tags for the players in the action, a ringed
  tracked player, and a broadcast camera mode tilting the pitch like a TV angle (with a flat tactical mode).

### Changed

- Recap vocabulary moved below the agents layer: `RecapStage`, `MIN_TURNING_POINT_IMPORTANCE`, and `moment_actor`
  now live in `analytics/recap_basis.py`, so `highlights/reel.py` no longer imports `agents.recap_context`; every
  importer uses the new home and reel output is unchanged (reel digests for seeds 1407 and 194 match develop).

- Auto replays queue instead of being dropped: a goal or big chance whose replay comes due while another replay is
  rolling waits in a queue of at most 2 (`REPLAY_QUEUE_MAX`; a goal replaces the oldest non-goal when it is full, a
  non-goal is dropped), and a queued replay is skipped, goals included, if its shot is more than 600 match seconds
  behind live by its turn (`REPLAY_MAX_LAG_MATCH_S`). Pure rules in `frontend/src/lib/replayQueue.ts`. Turning Auto
  replays off clears the queue; "Back to live" skips only the replay on screen. A recap that arrives while a replay
  is rolling, queued, or scheduled opens once none is left (opening a recap from its chip is unchanged). Seed
  1407 now replays its 34' equaliser after the 28' opener.
- `datasets/demo_story.py` models the replay queue (`played_replays` with the same constants, timed on the live
  stream clock with the half-time break) instead of the drop rule; seed 1407 still passes every rule, and 6 of
  seeds 1-4000 now pass (3 before).
- Realistic finishing: forward carries no longer pile up at the old `CARRY_MAX_X_M` limit (x = 103, 2 m out); a
  carry that would end beyond 93 m stops at a depth drawn from `CARRY_STOP_X_M` (93 to 102 m, 3 to 12 m from the
  goal line) and never moves behind its start (`carry_stop_x`). Over seeds 1-60 of Kestrel Bay vs Ironvale, shots
  from 2.5 m or less off the line fall from 8.3% of shots and 35.1% of goals to 0.1% and 0.6%, and 67.5% of goals
  now come from 6-12 m. Shot volume and finishing are re-tuned so every calibration band still holds (13 of 13):
  `SHOT_BASE_SCALE` 0.20 -> 0.18, `SHOT_DECAY_M` 22 -> 23, simulator `XG_INTERCEPT` -2.35 -> -1.90.
- Keeper positioning: a new pure `tracking/keeper.py` (`keeper_spot`) places the tracked keeper on the line from the
  goal centre to the ball, 30% of the way out, whenever the ball is within 20 m of goal (the old step-out formula
  beyond), and at a shot the keeper sets against the strike point rather than where the ball ends up, so replays
  show the keeper between a close shooter and the goal (99.0% of shots within 20 m, up from 85.8%).
- The analytics xG model's intercept moves from -2.35 to -2.00 so goals minus xG stays about 0 now that tap-ins are
  rare; every displayed xG (cards, replay analysis, recaps, Scout payoff text) rises slightly as a result.
- Regenerated with the project's own commands: the xT grid (`analytics/xt_grid.py`, peak 0.051), the calibration
  report (`docs/CALIBRATION.md`), and the two-match sample in `data/sample/`.
- Demo seed 201 -> 1407 (`DEMO_SEED` and the Landing button): Kestrel Bay Athletic 2-1 Ironvale United, the 58'
  Scout flank flag paid off by Zane Brekke's 65' winner from 9.4 m, and a shape shift at 83' (back line 27.1 m to
  17.8 m). `docs/DEMO_SCRIPT.md`, the README examples, and the seed-pinned replay, reel, API, and MCP tests move to
  the new seed; the reel test's milestone check runs on seed 28 (a half-time brace), since the demo match has none.

- Analysed instant replay: the replay of a goal or big chance now re-plays the real build-up and the shot instead
  of the stored frames around it. A pure server builder (`highlights/replay_story.py`) turns the shooting team's
  last 4 or fewer completed passes and carries (within 12 s), the strike, and the ball's flight to where the shot
  card says it crossed the line into keyframes, with the ball at each action's true start point. Its analysis block
  (`highlights/replay_analysis.py`) reuses existing analytics only: xG, goal chance, distance, angle, shot speed, the
  shot cone to both posts (`analytics/shot_cone.py`) with the defenders and keeper inside it, pressure, the
  build-up's pass count, time, and xT, and the assist with its xT and line break. `GET /api/matches/{id}/replay`
  returns the story (`frames` plus `analysis`) and 404 when no played shot matches. The broadcast plays the
  build-up at real pace and the strike in slow motion, draws the build-up path and the shot cone on the 2D pitch
  during the replay only, and holds on an analysis card: the full set for the analyst, a plain subset otherwise.
  The 2D crop (`lib/replayFraming.ts`) grows from the zoomed size to contain every build-up point, the shot
  origin, the goal mouth, and the final ball with a 3 m margin, keeping the shot cone in the half nearest the
  attacked goal; the card and caption sit on the other half, so they never cover the cone, goal mouth, shooter, or
  ball. The card shows xG at three decimals, the same value goal chance comes from (xG 0.075, 8% for the 77').
  A blocked shot's flight stops at the first defender within 1.5 m of the line to goal and at least 0.5 m in front
  of the shooter (`analytics/shot_block.py`), or 2 m out when nobody is in the lane, instead of flying into the
  goal. The ball flies at least 0.5 m and always stops at least 1 m short of the goal line.
- Saved shots in the instant replay stop at the keeper: the ball flies along the line to the shot card's placement
  but stops where it reaches the keeper's distance off the line in the shot frame (clamped to 0.3 to 3 m, 1 m when
  the keeper is not tracked; at least 0.5 m of flight, never closer than 0.3 m to the line), and the final replay
  frame shows the defending keeper at the save point (`analytics/shot_save.py`). Previously a save flew to its spot
  on the goal line and looked like a goal. Goals, off-target, and blocked shots are unchanged.
- Demo script rewritten around one story: the 69' Scout flag, the 77' winner from there, and two fans' views of it.
- Tracking protect drop: from 70' a leading team now defends 10 m deeper out of possession
  (`tracking/game_state.py`, sharing `PROTECT_START_SECOND` with the simulator's protect-the-lead rule; keeper and
  in-possession shapes unchanged), so late leads show up in the back line. Only tracked positions move: events,
  scorelines, the calibration report, and the event, match, player, and moment sample files are unchanged, and
  `data/sample/tracking.jsonl` regenerates identically because neither sample match has a late lead.

- Every club now has a weak defensive flank (Brookhaven and Kestrel Bay left, Ironvale and Silverlake right,
  `TeamStyle.weak_flank`): in the attacking half, opponents' passes drift 5 m toward it, passes into it in the final
  third complete 4 points more often, and tackles on dribbles down it succeed 2 points less often
  (`simulation/flanks.py`), without changing the number of random draws per action. This gives the Tactical Scout
  real signal: over Kestrel Bay vs Ironvale seeds 1 to 30, about 95% of wide flank flags point at the configured weak
  flank. Every seeded match changes, so seed 20 is no longer the 3-2 demo match; the demo match is now seed 201
  (`DEMO_SEED`), a 4-3 Kestrel Bay comeback whose 35' and 77' goals are linked to Scout flags at 31' and 69'. The
  calibration report (now 13 of 13 metrics in band over 480 matches), README table, and `data/sample/` are
  regenerated.
- Agent trace handoffs in the producer console only name executors that ran for the moment, so a Scout flag shows
  Intake to Tactical Scout and a goal shows Intake to Match Analyst.

- Demo script and submission text cover the 3D broadcast view, studio visuals, live agent trace, and automated
  highlights, with current test counts (194 backend, 52 frontend).
- Documentation refreshed: README status (as of PR #47, deployment not yet verified), calibration table from the
  480-match report, "Stack" instead of "Planned Stack", and project structure; architecture diagrams add the
  tracking model, play-by-play voice, and Azure AI Speech, with live-delivery notes on backpressure, sprints, and
  the producer stream; submission text and demo script cover spoken commentary and sprint tags with current test
  counts; `techdebt.md` gains a suggested order for the remaining work.
- Producer console is pushed, not polled: `GET /api/matches/{id}/producer/stream` sends the console state as a
  server-sent event whenever it changes (sampled every 0.5 s, heartbeats while quiet) and ends when the match
  finishes. The console subscribes once and falls back to 2-second polling only if the stream fails.
- Commentary energy: long passes, defence-splitting passes, and long runs are now raised moments, so their lines
  open with a reaction ("Look at that range! ... from 41 metres!") and are spoken with lifted pace and pitch.
  Commentary lines say measurements as words (41 metres, kilometres an hour). Raised and peak lines lift pitch
  audibly again (raised +12%, peak +22% in browser speech and Azure SSML).
- Voice choice: the viewer's system voice and male commentator voices are preferred over online and female voices,
  restoring the on-device voice (Daniel on macOS) that follows pitch and rate reliably.
- The scene-setting line now airs in the first lull of the first half and is shorter, so it no longer talks over
  the opening play.
- Commentary pace follows the replay speed: natural at real time and up to 25% quicker for fast replays (browser and
  Azure voices), and play-by-play spacing keeps about one line per five seconds of viewing time (more often at real
  time, less often at 60x). New 1x (real time) and 3x replay speeds.
- Home advantage in the simulator: home sides take more shots and away sides fewer (shot-volume factors 1.25 and
  0.78), moving results from about 33/35/32 to 43/29/28 home/draw/away; seeded matches differ from earlier builds.
- Submission text and demo script describe the seven agents, fact-checking, the producer console, tracking, and
  the Copilot-via-MCP segment; the script requires real AI output before recording and uses the exact UI labels.
- Agent evaluation takes one moment per kind (instead of the first few in time order) so every persona, the
  translator, and the fact-checker are exercised, and the report tallies fact-check verdicts.
- The Lead Commentator uses the right verb for the action (passes are not strikes) and avoids repeated words.
- Continuous play-by-play commentary from kick-off (kick-offs, final-third attacks, long passes, dribbles, tackles,
  interceptions, high pressing, long spells, half-time and full-time), paced at about one line per match minute and
  shared by every viewer.
- Switching persona or language keeps match-wide state (commentary, momentum, trail, stats) and swaps only
  persona-specific overlays and recaps; moment commentary is de-duplicated across segments.
- Moment commentary is translated for non-English viewers, and recap takes are written in the viewer's language
  when a model is available.
- The viewer panel explains what persona and language change, and says when translation is unavailable offline.
- "Ask the analyst" fallback now answers the question: a deterministic engine recognises best-player, who-is-on-top,
  momentum, named-player, and score questions and answers from live statistics in each persona's voice (the
  superfan in first person, the player tracker with their player's numbers, the newcomer with a term explained).
- Half-time and full-time recaps are personalized: each viewer segment receives a persona take (model-written when
  available, grounded template otherwise) above the shared recap.

### Fixed

- Template persona cards always fit the persona's word budget (`max_words` x `WORD_BUDGET_TOLERANCE`, the card
  validator's bound): the new pure `agents/card_text.py` keeps the prefix plus the leading whole sentences of
  `why_it_matters` that fit, or cuts a single long first sentence at a word boundary with a trailing `...`. It is
  used by the analyst, superfan, and player tracker templates. Superfan cards for goals linked to a `flank_exposed`
  Scout flag were 53 words against a 52-word bound (208 cards on 102 of seeds 1-4000, including the demo seed
  1407's 65' winner); a sweep of every persona card on every goal over seeds 1-4000 now has 0 over-limit cards and 0 validator
  or grounding failures, and the card title still carries the Scout link.

- The highlights caption no longer covers a shot clip's action: in story clips it goes to whichever of the bottom
  and top bands is clear of every keyframe ball and the acting player's dot at every playback tick and covers
  fewer players (on the default Broadcast cam that is usually the empty band above the tilted pitch), and only
  when neither band is clear becomes a compact, side-anchored caption away from the action. A placement is used
  only if the caption fits fully inside the pitch view, with each layout's height measured on its own (hidden
  full-width and compact twins); when nothing that fits is clear, the caption keeps today's full-width lower
  third, so at phone width it is never cut off or worse than before. Pure rules in
  `frontend/src/lib/captionPlacement.ts` with the camera projection in `lib/viewProjection.ts` (the broadcast
  tilt and perspective from `app.css`); frame clips and the 3D camera keep the lower third. Narration, timing, and
  voice are unchanged.
- An auto replay no longer starts under an open recap dialog (seed 194's 47' save under the half-time recap): due
  replays wait in the queue while the dialog is open and roll when it closes, with the queue cap and the 10-minute
  staleness drop unchanged (`recapOpened` and `recapClosed` in `lib/replayQueue.ts`). `datasets/demo_story.py` has
  no recap dialogs and documents that it assumes each recap is closed promptly; its model is unchanged.
- Highlights clips of shots now replay the real build-up and the ball's flight into the goal (goals, big chances,
  great saves, thunderous strikes, and brace or hat-trick milestones): they reuse the instant replay's
  story keyframes (`highlights/reel_story.py`, `playback: "story"` in the `/highlights` payload) and its timeline
  (build-up at real pace, the strike in slow motion, then the caption hold, `lib/reelPlayback.ts`). Before, every
  goal clip ended with the ball snapping back to the scorer's feet and passes ran up to 34 m ahead of the players.
  Other clips keep their stored frames (`playback: "frames"`); narration, captions, and clip order are unchanged.
- Instant replays never showed the ball going in: the shot and goal frames share a match second, so the shot's
  flight was skipped and the goal frame reset the ball to the scorer's feet, while the short window cut off the
  build-up (the 77' winner's 34.4 m assist was never seen). The new replay story fixes both.
- Unrealistic shot locations: 55% of simulated shots came from the byline (some from the corner flag at a
  near-zero angle) because shot probability ignored the angle and play piled up against the goal line. Shots are
  now weighted by how square-on the shooter is to goal, wide byline positions produce cutbacks and crosses into the
  box (completed less often than normal passes) and carries that cut inside, and passes stop short of the byline.
  Byline shots fell to 1.8%; the calibration report adds shots from inside the box, mean shot distance, and byline
  shots (all within band), with 11 of 13 metrics within band over 480 matches (home wins 38.8% and draws 32.1% sit
  just outside). Every seeded match changes, so the demo match is now seed 20 (3-2). A play-by-play wording that
  was chosen but not aired no longer counts against the no-repeat window.
- Players and their tags no longer leave the frame near the edges: the pitch has a runoff strip on every side
  (deeper behind the score bug), tags move inward near the touchlines and goal lines, and the broadcast camera
  zooms out slightly so the near touchline fits.
- TypeScript build info (`*.tsbuildinfo`) is ignored and no longer tracked.
- Speech lagging behind play: queued calm lines older than 4 seconds (raised lines 8 seconds) are skipped, and a
  close call cuts off a calm line in progress, so the commentator no longer describes earlier play over new action.
- Silent opening: the kick-off call was never spoken because Voice started off for every match and the toggle only
  appears once play has begun, and at real time the next line came about 27 seconds later. Voice now remembers the
  viewer's choice, switching it on speaks the latest line at once, a scene-setting line on both sides' styles
  follows kick-off, and quiet spells get everyday possession lines (median gap about 21 seconds at real time,
  unchanged at 10x).
- Commentary repetition: play-by-play had two wordings per action, so lines such as "X reads it and intercepts."
  aired up to five times; each action now has four or five wordings in rotation, no exact line repeats within 30
  lines, and the same kind of action is not called twice in a row. Chaotic-spell and momentum moments air at most
  once per half (they aired up to three times with identical wording) and their headlines, like big chances and
  saves, now vary.
- Goals were shouted twice ("GOAL!" from play-by-play, then "GOAL! ..." from the commentator); the commentator now
  reacts without repeating it.
- Robotic voice: the browser voice could fall back to macOS novelty or legacy voices and used a strong pitch lift;
  natural voices (enhanced or neural, then Google's) are preferred with the British locale for English, novelty
  voices are never chosen, and excitement now mostly lifts pace. A short settle after cancelling and a watchdog
  stop goal calls from being silently dropped or the queue from stalling.
- Found in a browser test: shot and ball speeds showed two decimals ("120.82 km/h") and now show one; the skip
  link now moves focus into the main region; at phone width, player name tags were about 6 px and are enlarged, the
  view switcher no longer wraps, and the venue line wraps below the camera toggle instead of beside it.
- Accessibility review (WCAG 2.2 AA): chip buttons were 22 px tall (now at least 32 px); form control borders were
  1.5:1 (new 3:1 border token); three club colours fell below 3:1 on the pitch stripes (lightened); the view switcher
  claimed tab semantics without arrow-key support (now toggle buttons); overlays and goal banners were inserted as new
  live regions that screen readers may skip (now persistent regions); no skip link; shirt numbers became unreadable
  at phone width (hidden there, name tags remain).
- The recap dialog re-ran its focus effect on every match event, pulling focus back repeatedly; it now runs once
  per opening, keeps Tab inside, returns focus on close, and does not auto-open while the viewer is typing.
- Shots on target ran above the reference band (40%) because too many unscored, unblocked shots were saved; the
  save share is now 32%, giving about 35% on target.
- The producer console showed moments whose agents were still working as "Not aired"; they now show as
  "In production" until their broadcast record arrives.
- Player surnames are unique within a fixture (surname pool enlarged to 56), so short names such as "Varga" in
  agent output always identify one player; seeded rosters and matches differ from earlier releases.
- The full-time drain could spin forever on finished tasks awaiting removal; it now waits only on unfinished work.
- A failing background task (agent workflow or recap) could stop a match from ever ending; failures now degrade
  to grounded templates and the end message is always sent.
- Viewers joining during the full-time drain could lose their backfilled cues; the session now drains until no
  work remains.
- Brace and hat-trick milestones rarely aired because the goal on the same event started the overlay gap; all now air.
- Replayed history cues (on reconnect or language switch) and stale late cues were shown as live overlays.
- Starting a second match kept the first match's recap state and questions.
- Analyst tools could cite statistics and moments from after the moment being explained.
- Unvalidated club and player ids created unlimited viewer segments; ids are validated, unused preferences
  dropped, and segments capped at 10 per match.
- Decimal commas (for example 0,38) broke grounding and translation checks.
- Reconnecting re-produced cues the segment already had.
- Shutdown hung while live streams were open; a five-second graceful timeout applies and agent work is cancelled.

### Added

- `techdebt.md` tracking Azure go-live steps, submission tasks, and engineering follow-ups.
- Foundry Agent Service hosted agent: definition builder restricted to read and question MCP tools, registration
  CLI with an optional test question, `AZURE_AI_PROJECT_ENDPOINT` deployment output, and `foundry` extra.
- README screenshots of the broadcast view and five-persona multiview.
- Metadata loading with exponential backoff and a visible retry banner when the service is unreachable.

### Changed

- Mobile layout: wrapping header, full-width view tabs, live pitch first, overlays sized for phones.
- Recap turning points only include moments with importance of at least 0.45, with readable labels.
- Carry milestone headline reads "tops 300 m carried with the ball".

## [0.1.0] - 2026-10-02

### Added

- Sliding-window rate limit (default 20 questions per match per minute) on `/ask` and the MCP companion tool,
  returning 429 with a retry hint.

- Distance indicators for player tagging: completed passes of 40 m or more and players passing 300 m and 400 m
  carried, with explanation templates and a newcomer glossary entry.

- Architecture documentation with Mermaid diagrams, submission text, and a timed two-minute demo script.

- Synthetic dataset generator: matches, enriched events (absolute coordinates, xG, pass difficulty, momentum,
  rhythm, triggered moments), player statistics, and labelled key moments as JSON Lines, with a generated
  dataset card; two-match sample in `data/sample/`.

- MCP server at `/mcp` (streamable HTTP, MCP SDK 2) with eight tools over the live session registry, including
  starting matches and questioning the Match Companion; optional bearer-token guard and host allow-list, wired
  into the Bicep deployment.

- Match Companion agent and "Ask the analyst" panel: grounded answers to viewer questions in the viewer's persona
  and language, with statistics tools, supporting stats, follow-up suggestions, and a grounded fallback.
- `POST /api/matches/{id}/ask` endpoint with input validation.

- Azure deployment: multi-stage Dockerfile serving API and frontend from one non-root container, azd project,
  and Bicep for Microsoft Foundry (account, project, model deployment), Container Apps, Container Registry,
  managed identity with least-privilege roles, Log Analytics, and Application Insights.
- Keyless Foundry provider using managed identity (`DefaultAzureCredential`), with optional key auth.
- OpenTelemetry export of Agent Framework traces to Application Insights.
- GitHub Actions CI (backend tests, frontend typecheck/tests/build, container build) and OIDC deploy workflow.
- Deployment guide in `docs/DEPLOYMENT.md`.

- MLX model provider (mlx_lm.server) with inline JSON schema prompting for servers without structured output.
- Per-runtime concurrency gate; local providers default to one call at a time, timed after the gate.
- Agent evaluation harness (`insidegame.evaluation`) reporting per-role model, corrected, and fallback rates,
  latency percentiles, rejection reasons, and persona samples; first MLX report in `docs/evaluations/`.
- Tracked players' live statistics in moment context and point-of-view framing for the Player Tracker.

- Broadcast frontend (React, TypeScript, Vite): live pitch, score bug, five persona overlay layouts with
  provenance, team stats, momentum chart, commentary ticker, recap dialog, and five-persona multiview.
- Backfill of recent relevant moments when a viewer segment joins mid-match.
- Broadcast minute labels with added time (45+3') shared by recaps, prompts, and the UI.

- FastAPI service with lifespan startup, lightweight health, model diagnostics, and metadata endpoints.
- Live match sessions replaying simulated matches at configurable speed, with background agent work.
- Personalized server-sent event streams per viewer segment (event, snapshot, cue, recap, end).
- Offline model provider that serves grounded templates without any model server.

- Multi-agent moment workflow on Microsoft Agent Framework: intake, analyst, parallel narrator and
  personalizer (with per-viewer translation), and assembler joined through shared workflow state.
- Timed overlay cues per viewer with layout, timing, priority, stat callouts, and per-agent provenance.
- Producer policy pacing overlays (goals always air, 45-second gap otherwise, two moments per event cap).
- Automated half-time and full-time recaps with grounded standout-player validation.
- Match intelligence service running the full pipeline per event, with a degraded template path when the
  workflow fails.

- Five Microsoft Agent Framework agents (analyst, commentator, personalization producer, translator, editor)
  with structured Pydantic outputs.
- Five personas (Analyst, Casual Fan, Superfan, Player Tracker, Newcomer) with distinct voice, vocabulary,
  word budget, statistical focus, relevance rules, and overlay style.
- Numeric grounding check with an evidence ledger for analyst tool results.
- Resilient agent runner with timeout, self-correcting retry, and deterministic template fallbacks.
- Analyst statistics tools and environment-driven model client adapter (Ollama locally, Foundry in deployment).

- Streaming match analyzer (stage 2) combining xG, pass difficulty, running player/team statistics,
  possession share, rolling momentum/control/chaos, and rule-based key moment detection.
- Explainable pass difficulty rating with per-factor breakdown.
- Key moments with importance scores and structured facts: goals, big chances, great saves, speed alerts,
  difficult passes, momentum swings, chaos spells, and milestones.
- Synthetic match engine: seeded possession-chain simulator producing full 90-minute event streams
  (passes, carries, shots, goals, saves, pressure, tackles, interceptions, fouls, possession changes).
- Fictional club presets with distinct tactical styles that adapt to game state and fatigue.
- Immutable, JSON-serialisable domain models for matches, teams, players, and events.
- Test suite covering geometry, probability models, roster generation, and statistical realism.
- Repository scaffolding: README, changelog, license, and ignore rules.

### Changed

- All API routes are served under `/api`; `/api/diagnostics` now makes one minimal real model call.
- Default local provider is MLX instead of Ollama.
- Momentum and chaos moments wait five minutes into each period before firing.
- Fallback commentary no longer repeats the minute.
- Match service split into fast interpretation and background production with dynamic viewer segments.
- Superfan fallback tone distinguishes own-club setbacks from successes.
- Cues for fallback translations are labelled English.
- Recalibrated simulator tackle and scoring rates toward realistic top-flight averages.

### Fixed

- A viewer joining a finished match received the end of the stream before its backfilled cues; the end
  message now follows that viewer's backfill (found by CI timing).
- The first viewer of a match nobody had watched received no cues, because backfill only drew on moments
  already aired to someone; the session now keeps recent key moments regardless of audience.
- Fenced JSON from local models was rejected because the framework's lazy structured value raised before the
  runner's own parser ran; the runner now falls back to its parser.
- Template punctuation no longer doubles a trailing period from model headlines.
- `httpx` pinned below 1.0 to avoid an incompatible pre-release.

[Unreleased]: https://github.com/UttyWotty/insidethegame-microsoft-hackathon/compare/v0.1.0...develop
[0.1.0]: https://github.com/UttyWotty/insidethegame-microsoft-hackathon/releases/tag/v0.1.0
