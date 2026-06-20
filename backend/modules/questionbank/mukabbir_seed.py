"""Deprecated — use punjab_seed.py"""
from .punjab_seed import ensure_punjab_data as ensure_mukabbir_data

if __name__ == "__main__":
    from .punjab_seed import ensure_punjab_data

    print("Punjab setup OK:", ensure_punjab_data())
