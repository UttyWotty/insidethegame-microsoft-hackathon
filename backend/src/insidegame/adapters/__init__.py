"""Adapter layer holding thin I/O boundaries such as environment configuration and model clients.

Business logic never reads the environment directly; it receives clients and settings from here.
Adapters may import any lower layer but are never imported by core, domain, analytics, or agents.
"""
