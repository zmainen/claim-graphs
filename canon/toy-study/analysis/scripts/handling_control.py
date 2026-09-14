"""Toy control script (fixture): handled-but-unpolished widgets show no shine rise."""
def rise(handled_only=[0.1, -0.2, 0.0]):
    return sum(handled_only) / len(handled_only)  # ~0: the validating null
