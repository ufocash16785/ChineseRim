from .elements import element_multiplier


def damage(base, attacker_elem, defender, cfg=None):
    cfg = cfg or {}
    return base * element_multiplier(attacker_elem, defender.primary_element,
                                     cfg.get("elemAdvMult", 1.5), cfg.get("elemDisMult", 0.75))
