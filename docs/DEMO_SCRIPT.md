<!--
Shot-by-shot script for the demo video, which must run under two minutes, told as one story about one goal.
Each beat lists the screen, the action, and the voice-over, with contiguous timing and every match fact taken from the demo fixture.
Record the demo match at 30x and cut the beats from it, so each one shows the app exactly as it plays.
-->

# Demo Video Script (1:57)

Setup before recording: deployed app (or local with a Foundry model). Press **Watch a demo match** for the demo
fixture: seed 1407, Kestrel Bay vs Ironvale (2-1, goals at 28', 34', and 65'), played as Kestrel Bay Athletic vs
Ironvale United at 30x (one match minute is two seconds). Oskar Pereira (28') puts Kestrel Bay ahead, Ansel Juarez
(34') levels for Ironvale United, and Zane Brekke (65') wins it. Broadcast cam on, Voice on, Analyst persona,
English. Turn **Auto replays** off for the take that supplies beats 0:00-0:08 and 2b: with it on, the replay covers the pitch
3.5 s after the shot, so a goal banner is readable for only about 3.5 s, and the 28' replay hides the 34' banner. At 58' a shot card ("Blocked", Kofi Quintero)
is on screen next to the Tactical Scout card; frame or crop the shot on the Scout card. Every chip must show **AI**,
not **Template**, before recording, and the 65' Analyst card must cite the 58' Scout flag (the template wording
always does; re-record if a model answer drops it). In every take, including the Spanish one,
open **All personas** at 63', before the 65' goal: a persona column opened later is backfilled with only the two
most recent moments, so the goal card never arrives live in it. Beat 2b therefore comes from a separate pass that
stays on the broadcast view through 65'. In the All personas view cards are newest first, so each column's first
card is the 65' goal (in the Analyst and Casual Fan columns the 58' Scout card sits under it); zoom on it in the
Analyst and the Casual Fan columns. Record a second take with the Casual Fan persona and Language set to Spanish
before kick-off; the same seed replays the same match, so beat 2d and the highlights cut to it. Shape shift at 83':
after going ahead at 65', Kestrel Bay Athletic's back line drops from 27.1 m to 17.8 m; capture it before the
full-time recap opens. VS Code open with GitHub Copilot agent mode and the project's MCP server configured
(`.vscode/mcp.json`, see README). No real club names, crests, footage, or copyrighted music.

Story: Kestrel Bay Athletic and Ironvale United are level at 1-1, and at 58' the Tactical Scout notices Kestrel Bay
keep beating Wes Thorne down Ironvale's right flank, the same flank it flagged at 14' before Oskar Pereira's opener.
At 65' Zane Brekke scores the winner from that attack, and the AI explains the goal through that earlier flag, in
depth for the analyst and in one line, in Spanish, for the casual fan. Everything after the arc is the same goal seen
through another part of the system, ending with Kestrel Bay sitting deeper to protect it.

| Time | Screen | Action | Voice-over |
|---|---|---|---|
| 0:00-0:08 | Landing screen, then broadcast view | Hold "Every match, made for every fan." for 3 s, press Watch a demo match, cut to 34' (from the Auto replays off take) as the GOAL banner reads "ANSEL JUAREZ 1-1" | "Fans see the score. They rarely see why it happened. Inside the Game explains every match, live, for every fan." |
| 0:08-0:21 | Broadcast view, broadcast cam (arc: pattern flagged) | At 58' the Tactical Scout card appears: "Flank exposed", "Kestrel Bay Athletic beat Wes Thorne down Ironvale United's right flank: 6 of 7 final-third entries in 15 minutes", "6 entries, 86%"; the flagged zone, the left channel of the final third Kestrel Bay attack, lights up on the pitch, labelled "Flank exposed" | "It is 1-1. At 58 minutes the Tactical Scout agent spots a pattern: Kestrel Bay keep beating Wes Thorne down Ironvale's right flank, six of seven final-third entries in fifteen minutes." |
| 0:21-0:31 | Broadcast view (arc: goal) | Auto replays off; start the cut at 63' so the shot is in frame. At 65' Zane Brekke scores; the GOAL banner reads "ZANE BREKKE 2-1" with "Scout flagged 58': Kestrel Bay Athletic beat Wes Thorne down Ironvale United's right flank: 6 of 7 final-third entries in 15 minutes" | "Seven minutes later the winner comes from that flank. Zane Brekke makes it 2-1, and the goal banner links straight back to the Scout's flag." |
| 0:31-0:42 | All personas view (arc: the AI connects them) | All personas opened at 63', before the goal, in this and the Spanish take; zoom on the Analyst column's first card, the 65' goal, "Zane Brekke puts their side in front, just as the Scout flagged at 58'", whose explanation ends with "The finish came from a chance worth 0.136 xG. The Tactical Scout flagged it at 58': Kestrel Bay Athletic beat Wes Thorne down Ironvale United's right flank: 6 of 7 final-third entries in 15 minutes."; the commentator says the card headline on air | "The AI connects the two. The Analyst agent's explanation names the 58th-minute flag as the reason, and the commentator says it on air." |
| 0:42-0:55 | All personas view, then the Spanish take (arc: analyst vs casual fan) | Pan from the Analyst card (xG 0.136, 2-1, the Scout's 6 of 7) to the Casual Fan column's first card, the 65' goal, "Zane Brekke puts their side in front, just as the Scout flagged at 58'. It is 2-1."; cut to the Spanish take's Casual Fan column on the same 65' card | "Same goal, two fans. The analyst gets the evidence: a 0.136 xG chance and the Scout's numbers. The casual fan gets one line, and with one switch, in Spanish." |
| 0:55-1:04 | All personas view | Hover the AI and Fact-checked chips on the 65' Analyst card | "Behind that one goal, Agent Framework agents on Microsoft Foundry handed off in turn, and a Standards Editor fact-checked every number." |
| 1:04-1:12 | Broadcast view, Danger leaderboard | At the 65' goal the leaderboard reads Umar Ulloa 0.228, Luca Baptiste 0.186, Dario Halloran 0.177 xT added | "Expected threat shows who builds the danger: all three leaders play for Ironvale, yet Kestrel Bay are the ones ahead." |
| 1:12-1:23 | Broadcast view, then studio | Shape shift at 83': the shape layer draws Kestrel Bay's back line "Before 27.1 m" and "Now 17.8 m" with "Low block"; cut to the studio back-line height timeline with the 83' mark | "Second act: ahead after the 65th-minute winner, Kestrel Bay sit deeper. Their back line drops from 27 to 18 metres, and their possession falls from 61 to 49 percent." |
| 1:23-1:32 | Producer console | Select the 65' Goal row: its agent trace (Intake, Match Analyst, Lead Commentator, Personalization Producer, Standards Editor, Broadcast Translator) and broadcast record show; toggle "Holding AI overlays for approval", then back to "AI overlays airing live" | "In the control room the producer sees every agent handoff behind the winner, and can hold AI overlays until a human releases them." |
| 1:32-1:40 | VS Code, Copilot agent mode | Ask "How has Kestrel Bay Athletic's shape changed since they went ahead?"; Copilot calls `get_team_shape` and answers with the 83' shift, back line 27.1 m to 17.8 m after going ahead at 65' | "It is also an MCP server, so GitHub Copilot can query the live match: how did Kestrel Bay change after scoring?" |
| 1:40-1:48 | Full-time highlights, Spanish take | In the full-time recap press "Watch highlights" (not "Back to the match"), then press Next to the fifth of six clips, the 65' winner, narrated in Spanish | "At full time the highlights cut themselves, from the big save to Brekke's winner, narrated in each viewer's language." |
| 1:48-1:57 | Architecture diagram, then app | Show the diagram, end on the broadcast with an overlay | "All from a seeded synthetic match. Agent Framework, Foundry, Azure AI Speech, MCP, and Azure Container Apps: explainable, personalized match intelligence for live broadcast." |
