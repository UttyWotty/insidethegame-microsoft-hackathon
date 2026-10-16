<!--
Shot-by-shot script for the demo video, which must run under two minutes.
Each beat lists the screen, the action, and the voice-over, with cumulative timing.
Record at 30x replay speed so a key moment appears within the first beats.
-->

# Demo Video Script (1:56)

Setup before recording: deployed app (or local with a Foundry model), seed 201, Kestrel Bay vs Ironvale (4-3, goals at 15', 19', 35', 36', 52', 62', and 77'), 30x speed,
broadcast camera on, Voice on (the commentator speaks from kick-off and lifts for goals and close calls). Every
chip must show **AI**, not **Template**, before recording. VS Code open with GitHub
Copilot agent mode and the project's MCP server configured (`.vscode/mcp.json`, see README).
No real club names, crests, footage, or copyrighted music.

| Time | Screen | Action | Voice-over |
|---|---|---|---|
| 0:00-0:08 | Landing screen | Hold on the value proposition | "Football stories don't end with the scoreline. Inside the Game turns raw match events into explainable intelligence, made for every fan." |
| 0:08-0:18 | Broadcast view, 3D camera | Press Watch a demo match, switch to 3D; players run, the camera follows the ball, a sprint tag shows a speed, the commentator calls the play | "A seeded simulator streams football-realistic events and tracking for all 22 players. Our analytics engine turns them into xG, pass difficulty, momentum, and control versus chaos, live." |
| 0:18-0:32 | Analyst overlay over the 3D view | Hover the AI and Fact-checked chips | "At every key moment, eight Microsoft Agent Framework agents on Microsoft Foundry go to work. The Analyst explains why it matters, every number is checked against the match data, and a Standards Editor agent fact-checks the card before it airs." |
| 0:32-0:46 | Broadcast view, 2D pitch | At 31' the Tactical Scout card appears bottom-right and Kestrel Bay's left flank lights up ("Ironvale United beat Felix Tavish down Kestrel Bay Athletic's left flank"); at 35' Rasmus scores and the goal banner reads "Scout flagged 31'" | "The Tactical Scout doesn't just react. It mines the event stream for patterns, here a flank Ironvale keep exploiting, and four minutes later the goal comes from exactly there. Later the Scout flags Kestrel Bay overloading the left at 69', and the 77' winner of a 4-3 comeback comes down that side." |
| 0:46-0:56 | All personas view | Slow pan across the five columns at the same moment | "The same moment, five experiences: metrics for the Analyst, one clear line for the Casual Fan, celebration for the Superfan, one player for the Tracker, and a lesson for the Newcomer." |
| 0:56-1:06 | Studio view | Follow the Analyst switches the visual; show the pressing map or pass network beside the explanation | "In the studio, the Analyst's own reasoning picks the evidence: a pressure shift shows the pressing map, chaos shows who controls the space." |
| 1:06-1:18 | Producer console, agent trace | A Scout flag's trace fills in live (Intake to Tactical Scout to Commentator and Producer); toggle "Holding AI overlays for approval", then "Release to air" | "The control room shows the agents handing work to each other, with every output's source and fact-check verdict, and a human who can hold AI overlays before they air." |
| 1:18-1:28 | VS Code, Copilot agent mode | Ask "Who is on top in the live match, and why?" | "The same intelligence is an MCP server, so GitHub Copilot or a Foundry hosted agent can query the live match as a tool." |
| 1:28-1:44 | Half-time highlights in 3D | Watch highlights from the recap; the goal replays with spoken commentary, in Spanish for a Spanish viewer | "At half-time and full-time the highlights package is cut automatically, narrated in each viewer's language." |
| 1:44-1:56 | Architecture diagram, then app | Show the diagram, end on the 3D broadcast with an overlay | "Agent Framework, Foundry, Azure AI Speech, MCP, and Azure Container Apps: explainable, personalized match intelligence, ready for live broadcast." |
