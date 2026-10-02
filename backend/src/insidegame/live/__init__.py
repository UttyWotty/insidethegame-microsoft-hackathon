"""Live layer that replays a simulated match in real time and fans results out to subscribers.

It paces events by match clock, runs agent work in background tasks so the event feed never waits,
and routes overlay cues to the viewer segment they were personalized for.
"""
