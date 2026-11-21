from decimal import Decimal

def record(value):
    if isinstance(value, dict):
        return {k: record(v) for k, v in value.items() if k not in ('PK', 'SK') and not k.startswith('GSI')}
    if isinstance(value, list): return [record(v) for v in value]
    if isinstance(value, Decimal): return int(value) if value == value.to_integral() else str(value)
    return value
