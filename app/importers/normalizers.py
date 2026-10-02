import re
from decimal import Decimal, InvalidOperation


class ImportValidationError(ValueError):
    pass


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_supplier_part(value: object) -> str:
    return normalize_text(value).replace(" ", "").upper()


def parse_non_negative_int(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise ImportValidationError(f"{field_name} 必须是非负整数")
    if isinstance(value, int):
        result = value
    elif isinstance(value, float) and value.is_integer():
        result = int(value)
    else:
        match = re.search(r"-?\d+", normalize_text(value))
        if not match:
            raise ImportValidationError(f"{field_name} 必须是非负整数")
        result = int(match.group())
    if result < 0:
        raise ImportValidationError(f"{field_name} 必须是非负整数")
    return result


def parse_money(value: object) -> Decimal | None:
    text = normalize_text(value)
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text.replace(",", ""))
    if not match:
        return None
    try:
        return Decimal(match.group())
    except InvalidOperation:
        return None


def split_designators(value: object) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    return [item.strip() for item in re.split(r"[,，;；\s]+", text) if item.strip()]
