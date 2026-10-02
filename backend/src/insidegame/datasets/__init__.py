"""Dataset layer turning simulated, analysed matches into analytics- and ML-ready tables.

The rows module is pure; the generate module is a thin command-line adapter that writes files.
Outputs are JSON Lines with a dataset card, ready for Microsoft Fabric, notebooks, or model training.
"""
