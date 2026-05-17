def parse_weight(value: str) -> float:
    weight = float(value.replace(",", ".").strip())
    if not 20 <= weight <= 300:
        raise ValueError
    return round(weight, 1)


def parse_height(value: str) -> float:
    height = float(value.replace(",", ".").strip())
    if not 80 <= height <= 250:
        raise ValueError
    return round(height, 1)


def parse_calories(value: str) -> int:
    calories = int(value.strip())
    if not 500 <= calories <= 10000:
        raise ValueError
    return calories


def parse_protein(value: str) -> int:
    protein = int(value.strip())
    if not 10 <= protein <= 400:
        raise ValueError
    return protein
