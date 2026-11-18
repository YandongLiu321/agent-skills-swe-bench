"""Helper for bounding command output before it is serialized into a trajectory."""

DEFAULT_RAW_OUTPUT_MAX_CHARS = 1_000_000
"""Default bound for `raw_output`, in characters (1 MiB).

Chosen so that ordinary large outputs (a full test suite log) are kept intact,
while a pathologically chatty command (a recursive grep over a package tree) is
capped. The worst case observed in practice was 618 million characters.
"""


def truncate_middle(text: str, max_chars: int) -> str:
    """Bound `text` to about `max_chars` by eliding its middle.

    The head and the tail are kept rather than a prefix, because observation
    templates render only the first and last few thousand characters of an
    over-long output. Eliding the middle therefore leaves what the model sees
    unchanged, while bounding what gets written into the trajectory file. For
    that to hold, `max_chars` has to be larger than twice the template's largest
    window (see `LitellmModelConfig.raw_output_max_chars`).

    The elision is marked with the number of characters removed, so a trajectory
    reader can always tell a bounded output apart from a genuinely short one.
    """
    if max_chars <= 0 or len(text) <= max_chars:
        return text
    half = max_chars // 2
    elided = len(text) - 2 * half
    marker = f"\n[... {elided} characters elided by raw_output_max_chars ...]\n"
    return text[:half] + marker + text[-half:]
