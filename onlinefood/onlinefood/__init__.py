import django.template.context as context
from copy import copy as _copy


def _patched_base_copy(self):
    from django.template.context import BaseContext
    duplicate = BaseContext()
    duplicate.__class__ = self.__class__
    duplicate.__dict__ = _copy(self.__dict__)
    duplicate.dicts = self.dicts[:]
    return duplicate


context.BaseContext.__copy__ = _patched_base_copy
context.RenderContext.__copy__ = _patched_base_copy
