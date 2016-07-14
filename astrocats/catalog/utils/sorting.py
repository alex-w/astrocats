'''Key sorting functions
'''

from .digits import is_integer

__all__ = ['alias_priority', 'bib_priority']


def alias_priority(name, attr):
    if name == attr:
        return 0
    return 1


def bib_priority(attr):
    if 'bibcode' in attr:
        if is_integer(attr['bibcode'][:4]):
            return -int(attr['bibcode'][:4])
        return 0
    return 0
