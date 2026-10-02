"""Agent layer implementing pipeline stages three to five: explain, narrate, and personalize.

It defines personas, structured output schemas, prompts, grounding checks, fallbacks, and agent factories.
Modules here are pure except factory.py, which only wires injected chat clients into Agent Framework agents.
"""
