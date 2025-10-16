import re
from typing import Any, Dict, Iterable, List, Optional, Pattern, Tuple, Union


def _flags_from_string(flags: Optional[str]) -> int:
    if not flags:
        return 0
    mapping = {
        "i": re.IGNORECASE,
        "m": re.MULTILINE,
        "s": re.DOTALL,
    }
    value = 0
    for ch in flags:
        value |= mapping.get(ch.lower(), 0)
    return value


def _compile_rule(pattern: str, flags: Optional[str]) -> Pattern[str]:
    return re.compile(pattern, _flags_from_string(flags))


def extract_fields(
    text: str,
    rules: Union[Dict[str, str], List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Extract fields from text using regex-based rules.

    Rules can be one of:
    - Dict[str, str]: { field_name: regex }, assumes first capture group is the value.
    - List of dicts with keys:
        - name: field name (required)
        - pattern: regex pattern (required)
        - group: capture group index or name (default 1 or 'value' if named exists)
        - flags: combination of 'i', 'm', 's'
        - multiple: if true, returns list of all matches
        - default: default value when not found
    """
    results: Dict[str, Any] = {}

    if isinstance(rules, dict):
        for field_name, pattern in rules.items():
            regex = re.compile(pattern, re.IGNORECASE)
            match = regex.search(text)
            if match:
                value = match.group(1) if match.groups() else match.group(0)
                results[field_name] = value
        return results

    for rule in rules:
        name = rule.get("name")
        pattern = rule.get("pattern")
        group = rule.get("group")
        flags = rule.get("flags")
        multiple = bool(rule.get("multiple", False))
        default = rule.get("default")

        if not name or not pattern:
            continue

        regex = _compile_rule(pattern, flags)

        if multiple:
            values: List[Any] = []
            for match in regex.finditer(text):
                if group is None:
                    if "value" in regex.groupindex:
                        values.append(match.group("value"))
                    elif match.groups():
                        values.append(match.group(1))
                    else:
                        values.append(match.group(0))
                else:
                    values.append(match.group(group))
            if values:
                results[name] = values
            elif default is not None:
                results[name] = default
        else:
            match = regex.search(text)
            if match:
                if group is None:
                    if "value" in regex.groupindex:
                        results[name] = match.group("value")
                    elif match.groups():
                        results[name] = match.group(1)
                    else:
                        results[name] = match.group(0)
                else:
                    results[name] = match.group(group)
            elif default is not None:
                results[name] = default

    return results
