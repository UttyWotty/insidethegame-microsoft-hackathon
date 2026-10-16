<!--
Shot-by-shot script for the demo video, which must run under two minutes, told as one story about one goal.
Each beat lists the screen, the action, and the voice-over, with contiguous timing and every match fact taken from the demo fixture.
Record the demo match at 30x and cut the beats from it, so each one shows the app exactly as it plays.
-->

# Demo Video Script (1:57)

Setup before recording: deployed app (or local with a Foundry model). Press **Watch a demo match** for the demo
fixture: seed 201, Kestrel Bay vs Ironvale (4-3, goals at 15', 19', 35', 36', 52', 62', and 77'), played as Kestrel
Bay Athletic vs Ironvale United at 30x (one match minute is two seconds). Mateo Rasmus puts Ironvale United 0-3 up
with the first three; Hugo Drummond (36'), Rafael Gunnarsson (52'), and Idris Bellamy (62' and 77') bring Kestrel
Bay back. Broadcast cam on, Voice on, Analyst persona, English. Turn **Auto replays** off for the take that
supplies beat 2b: with it on, the replay covers the pitch 3.5 s after the shot and the goal banner is readable for
only about 3.5 s. At 69' a distance card ("Deniz Okafor tops 300 m carried with the ball") is on screen next to the
Tactical Scout card; frame or crop the shot on the Scout card. Every chip must show **AI**, not **Template**,
before recording, and the 77' Analyst card must cite the 69' Scout flag (the template wording always does;
re-record if a model answer drops it). In every take, including the Spanish one, open **All personas** at 75',
before the 77' goal: a persona column opened later is backfilled with only the two most recent moments, so a late
join shows the milestone card but never the goal card. Beat 2b therefore comes from a separate pass that stays on
the broadcast view through 77'. In the All personas view each 77' column holds two cards, newest first: the
first is "Idris Bellamy reaches a milestone", so zoom on the second, the goal card, in the Analyst and the Casual
Fan columns. Record a second take with the Casual Fan persona and Language set to Spanish before kick-off; the same
seed replays the same match, so beat 2d and the highlights cut to it. Shape shift at 88': after going ahead at 77',
Kestrel Bay Athletic's back line drops from 30.9 m to 20.2 m; capture it before the full-time recap opens. VS Code
open with GitHub Copilot agent mode and the project's MCP server configured (`.vscode/mcp.json`, see README). No
real club names, crests, footage, or copyrighted music.

Story: Kestrel Bay Athletic fight back from 0-3 to 3-3, and at 69' the Tactical Scout notices they keep attacking
down the left. At 77' Idris Bellamy scores the winner from exactly there, and the AI explains the goal through that
earlier flag, in depth for the analyst and in one line, in Spanish, for the casual fan. Everything after the arc
is the same goal seen through another part of the system, ending with Kestrel Bay sitting deeper to protect it.

| Time | Screen | Action | Voice-over |
|---|---|---|---|
| 0:00-0:08 | Landing screen, then broadcast view | Hold "Every match, made for every fan." for 3 s, press Watch a demo match, cut to 62' as the GOAL banner reads "IDRIS BELLAMY 3-3" | "Fans see the score. They rarely see why it happened. Inside the Game explains every match, live, for every fan." |
| 0:08-0:21 | Broadcast view, broadcast cam (arc: pattern flagged) | At 69' the Tactical Scout card appears: "Channel overload", "Kestrel Bay Athletic sent 7 of 11 final-third entries down the left (64%) in 15 minutes", "7 entries, 64%"; the flagged zone, the left channel of the final third Kestrel Bay attack, lights up on the pitch, labelled "Channel overload" | "Kestrel Bay Athletic were three down and are level at 3-3. At 69 minutes the Tactical Scout agent spots a pattern: seven of their eleven final-third entries in fifteen minutes went down the left." |
| 0:21-0:31 | Broadcast view (arc: goal) | Auto replays off; start the cut at 75' so the shot is in frame. At 77' Idris Bellamy scores; the GOAL banner reads "IDRIS BELLAMY 4-3" with "Scout flagged 69': Kestrel Bay Athletic sent 7 of 11 final-third entries down the left (64%) in 15 minutes" | "Eight minutes later the winner comes from exactly there. Idris Bellamy makes it 4-3, and the goal banner links straight back to the Scout's flag." |
| 0:31-0:42 | All personas view (arc: the AI connects them) | All personas opened at 75', before the goal, in this and the Spanish take; zoom on the Analyst column's second 77' card, "Idris Bellamy puts their side in front, just as the Scout flagged at 69'", whose explanation ends with "The finish came from a chance worth 0.075 xG. The Tactical Scout flagged it at 69': Kestrel Bay Athletic sent 7 of 11 final-third entries down the left (64%) in 15 minutes."; the commentator says the card headline on air | "The AI connects the two. The Analyst agent's explanation names the 69th-minute flag as the reason, and the commentator says it on air." |
| 0:42-0:55 | All personas view, then the Spanish take (arc: analyst vs casual fan) | Pan from the Analyst card (xG 0.075, 4-3, the Scout's 7 of 11) to the Casual Fan column's second 77' card, "Idris Bellamy puts their side in front, just as the Scout flagged at 69'. It is 4-3."; cut to the Spanish take's Casual Fan column on the same 77' card | "Same goal, two fans. The analyst gets the evidence: a 0.075 xG chance and the Scout's numbers. The casual fan gets one line, and with one switch, in Spanish." |
| 0:55-1:04 | All personas view | Hover the AI and Fact-checked chips on the 77' Analyst card | "Behind that one goal, Agent Framework agents on Microsoft Foundry handed off in turn, and a Standards Editor fact-checked every number." |
| 1:04-1:12 | Broadcast view, Danger leaderboard | At the 77' goal the leaderboard reads Rafael Gunnarsson 0.292, Tomas Iversen 0.209, Hugo Drummond 0.191 xT added | "Expected threat shows who builds the danger: Hugo Drummond, who set up the winner, is third on the board." |
| 1:12-1:23 | Broadcast view, then studio | Shape shift at 88': the shape layer draws Kestrel Bay's back line "Before 30.9 m" and "Now 20.2 m" with "Low block"; cut to the studio back-line height timeline with the 88' mark | "Second act: ahead after the 77th-minute winner, Kestrel Bay sit deeper. Their back line drops from 31 to 20 metres, and their possession falls from 65 to 50 percent." |
| 1:23-1:32 | Producer console | Select the 77' Goal row: its agent trace (Intake, Match Analyst, Lead Commentator, Personalization Producer, Standards Editor, Broadcast Translator) and broadcast record show; toggle "Holding AI overlays for approval", then back to "AI overlays airing live" | "In the control room the producer sees every agent handoff behind the winner, and can hold AI overlays until a human releases them." |
| 1:32-1:40 | VS Code, Copilot agent mode | Ask "How has Kestrel Bay Athletic's shape changed since they went ahead?"; Copilot calls `get_team_shape` and answers with the 88' shift, back line 30.9 m to 20.2 m after going ahead at 77' | "It is also an MCP server, so GitHub Copilot can query the live match: how did Kestrel Bay change after scoring?" |
| 1:40-1:48 | Full-time highlights, Spanish take | In the full-time recap press "Watch highlights" (not "Back to the match"), then press Next to the last of six goal clips, the 77' winner, narrated in Spanish | "At full time the highlights cut themselves, ending on Bellamy's winner, narrated in each viewer's language." |
| 1:48-1:57 | Architecture diagram, then app | Show the diagram, end on the broadcast with an overlay | "All from a seeded synthetic match. Agent Framework, Foundry, Azure AI Speech, MCP, and Azure Container Apps: explainable, personalized match intelligence for live broadcast." |
