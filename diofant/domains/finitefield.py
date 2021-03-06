"""Implementation of :class:`FiniteField` class."""

import numbers
import random

from ..core import Dummy, integer_digits
from ..ntheory import factorint
from ..polys.galoistools import dup_gf_irreducible
from ..polys.polyerrors import CoercionFailed
from .field import Field
from .groundtypes import DiofantInteger
from .integerring import GMPYIntegerRing, PythonIntegerRing, ZZ_python
from .quotientring import QuotientRingElement
from .simpledomain import SimpleDomain


__all__ = 'FiniteField', 'GMPYFiniteField', 'PythonFiniteField'


_modular_integer_cache = {}


class FiniteField(Field, SimpleDomain):
    """General class for finite fields."""

    is_FiniteField = True
    is_Numerical = True

    def __new__(cls, order, dom, modulus=None):
        try:
            pp = factorint(order)
            if not order or len(pp) != 1:
                raise ValueError
            mod, deg = pp.popitem()
        except ValueError:
            raise ValueError(f'order must be a prime power, got {order}')

        if deg == 1:
            if modulus:
                deg = len(modulus) - 1
            else:
                modulus = [1, 0]

        order = mod**deg

        if modulus is None:
            random.seed(0)
            modulus = dup_gf_irreducible(deg, ZZ_python.finite_field(mod))
        elif deg != len(modulus) - 1:
            raise ValueError('degree of a defining polynomial for the field'
                             ' does not match extension degree')

        modulus = tuple(map(dom.dtype, modulus))

        mod = dom.convert(mod)

        key = order, dom, mod, modulus

        obj = super().__new__(cls)

        obj.domain = dom
        obj.mod = mod
        obj.order = order

        if order > mod:
            obj.rep = f'GF({obj.mod}, {list(map(ZZ_python, modulus))})'
        else:
            obj.rep = f'GF({obj.mod})'

        try:
            obj.dtype = _modular_integer_cache[key]
        except KeyError:
            if deg == 1:
                obj.dtype = type('ModularInteger', (ModularInteger,),
                                 {'mod': mod, 'domain': dom, '_parent': obj})
            else:
                ff = dom.finite_field(mod).inject(Dummy('x'))
                mod = ff.from_dense(modulus)
                if not mod.is_irreducible:
                    raise ValueError('defining polynomial must be irreducible')
                obj.dtype = type('GaloisFieldElement', (GaloisFieldElement,),
                                 {'mod': mod, 'domain': ff, '_parent': obj})
            _modular_integer_cache[key] = obj.dtype

        obj.zero = obj.dtype(0)
        obj.one = obj.dtype(1)

        return obj

    def __hash__(self):
        return hash((self.__class__.__name__, self.dtype, self.order, self.domain))

    def __eq__(self, other):
        return isinstance(other, FiniteField) and \
            self.order == other.order and self.domain == other.domain

    def __getnewargs_ex__(self):
        return (self.order,), {}

    @property
    def characteristic(self):
        return self.mod

    def to_expr(self, element):
        return DiofantInteger(int(element))

    def from_expr(self, expr):
        if expr.is_Integer:
            return self.dtype(self.domain.dtype(int(expr)))
        elif expr.is_Float and int(expr) == expr:
            return self.dtype(self.domain.dtype(int(expr)))
        else:
            raise CoercionFailed(f'expected an integer, got {expr}')

    def _from_PythonFiniteField(self, a, K0=None):
        return self.dtype(self.domain.convert(a.rep, K0.domain))

    def _from_PythonIntegerRing(self, a, K0=None):
        return self.dtype(self.domain.convert(a, K0) % self.characteristic)
    _from_GMPYIntegerRing = _from_PythonIntegerRing

    def _from_PythonRationalField(self, a, K0=None):
        if a.denominator == 1:
            return self.convert(a.numerator)

    def _from_GMPYFiniteField(self, a, K0=None):
        return self.dtype(self.domain.convert(a.rep, K0.domain))

    def _from_GMPYRationalField(self, a, K0=None):
        if a.denominator == 1:
            return self.convert(a.numerator)

    def _from_RealField(self, a, K0):
        p, q = K0.to_rational(a)

        if q == 1:
            return self.dtype(self.domain.dtype(p))

    def is_normal(self, a):
        return True


class PythonFiniteField(FiniteField):
    """Finite field based on Python's integers."""

    def __new__(cls, order, modulus=None):
        return super().__new__(cls, order, PythonIntegerRing(), modulus)


class GMPYFiniteField(FiniteField):
    """Finite field based on GMPY's integers."""

    def __new__(cls, order, modulus=None):
        return super().__new__(cls, order, GMPYIntegerRing(), modulus)


class ModularInteger(QuotientRingElement):
    """A class representing a modular integer."""

    @property
    def numerator(self):
        return self

    @property
    def denominator(self):
        return self.parent.one


class GaloisFieldElement(ModularInteger):
    def __init__(self, rep):
        if isinstance(rep, numbers.Integral):
            rep = integer_digits(rep % self.parent.order, self.parent.mod)

        if isinstance(rep, (list, tuple)):
            rep = self.domain.from_dense(rep)

        super().__init__(rep)

    def __int__(self):
        rep = self.rep.set_domain(self.parent.domain)
        return int(rep.eval(0, self.parent.mod))
