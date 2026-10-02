"""Orchestration layer coordinating the agents into a multi-agent workflow per key moment.

It selects moments for broadcast, runs analyst, narrator, personalizer, and translator agents with shared state,
and assembles timed, machine-readable overlay cues (pipeline stage four: render).
"""
