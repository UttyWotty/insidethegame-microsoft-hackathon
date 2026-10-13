"""Speech layer turning match commentary into spoken audio for broadcast.

The ssml module is pure: it chooses a neural voice per language and builds escaped SSML within a size limit.
Synthesis itself lives in the adapters layer, so this package has no I/O and depends only on core.
"""
