from copy import deepcopy


MISSING = object()


def merge_with_defaults(data, defaults):
    if isinstance(defaults, dict):
        result = deepcopy(defaults)
        if not isinstance(data, dict):
            return result

        for key, value in data.items():
            if key in defaults:
                result[key] = merge_with_defaults(value, defaults[key])
            else:
                result[key] = deepcopy(value)
        return result

    return deepcopy(data)


def coerce_to_int(value, default: int = 0) -> int:
    if value in (None, ""):
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default


def coerce_to_float(value, default: float = 0.0) -> float:
    if value in (None, ""):
        return default

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def coerce_like_reference(value, reference):
    if value is None:
        return None

    if isinstance(reference, bool):
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "si", "sì"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return bool(value)

    if isinstance(reference, int) and not isinstance(reference, bool):
        if isinstance(value, str) and value.strip() == "":
            return value
        return coerce_to_int(value, reference)

    if isinstance(reference, float):
        if isinstance(value, str) and value.strip() == "":
            return value
        return coerce_to_float(value, reference)

    return value


def coerce_like_existing_or_default(value, existing=MISSING, default=MISSING):
    if existing is not MISSING:
        return coerce_like_reference(value, existing)

    if default is not MISSING:
        return coerce_like_reference(value, default)

    return value
