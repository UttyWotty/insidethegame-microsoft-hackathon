"""Microsoft Fabric lakehouse layer: table schemas, row validation, and semantic model checks.

The schema, validate, and tmdl modules are pure and hold the single source of truth for the Delta tables.
The check module is a thin command-line adapter that reads the dataset, notebook, and TMDL files and reports drift.
"""
