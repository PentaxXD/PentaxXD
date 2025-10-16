import re
from typing import Iterable, List, Optional, Pattern, Set


def _compile_patterns(patterns: Optional[Iterable[str]], ignore_case: bool) -> List[Pattern[str]]:
    if not patterns:
        return []
    flags = re.IGNORECASE if ignore_case else 0
    return [re.compile(p, flags) for p in patterns]


def filter_lines(
    text: str,
    include_patterns: Optional[Iterable[str]] = None,
    exclude_patterns: Optional[Iterable[str]] = None,
    context_lines: int = 0,
    ignore_case: bool = True,
) -> str:
    """Filter text by include/exclude regex patterns at the line level.

    If include_patterns is provided, only matching lines are retained, with optional
    context lines before and after each match. Exclude patterns are applied last
    and remove lines even if they were included by context.
    """
    lines = text.splitlines()

    include_regexes = _compile_patterns(include_patterns, ignore_case)
    exclude_regexes = _compile_patterns(exclude_patterns, ignore_case)

    if not include_regexes:
        kept_indices: Set[int] = set(range(len(lines)))
    else:
        kept_indices = set()
        for idx, line in enumerate(lines):
            if any(r.search(line) for r in include_regexes):
                start = max(0, idx - context_lines)
                end = min(len(lines) - 1, idx + context_lines)
                kept_indices.update(range(start, end + 1))

    # Apply excludes last
    if exclude_regexes:
        to_remove = set()
        for idx in kept_indices:
            line = lines[idx]
            if any(r.search(line) for r in exclude_regexes):
                to_remove.add(idx)
        kept_indices.difference_update(to_remove)

    filtered_lines = [lines[i] for i in sorted(kept_indices)]
    return "\n".join(filtered_lines)
