"""
Limits
======

Implemented according to the PhD thesis
http://www.cybertester.com/data/gruntz.pdf, which contains very thorough
descriptions of the algorithm including many examples.  We summarize here the
gist of it.


All functions are sorted according to how rapidly varying they are at infinity
using the following rules. Any two functions f and g can be compared:

L=lim  ln|f(x)| / ln|g(x)|           (for x -> infty)

f > g .... L=+-infty 
    * f is greater than any power of g
    * f is more rapidly varying than g
    * f goes to infinity/zero faster than g


f < g .... L=0 
    * f is lower than any power of g

f ~ g .... L!=0,+-infty 
    * both f and g are bounded from above and below by suitable integral powers
    of the other


Examples: 

    1 < x < exp(x) < exp(x^2) < exp(exp(x))
    1 ~ 3 ~ -5
    x ~ x^2 ~ x^3 ~ 1/x ~ x^m ~ -x
    exp(x) ~ exp(-x) ~ exp(2x) ~ exp(x)^2 ~ exp(x+exp(-x))
    f ~ 1/f

So we can divide all the functions into comparability classes (x and x^2 is the
same class, as is exp(x) and exp(-x)). In principle, we could compare any two
functions, but in our algorithm, we don't compare anything below f=1 (for
example ln(x) is below 1), so we set f=1 as the lowest comparability class. 

Given the function f, we find the list of most rapidly varying (mrv set)
subexpressions of it. This list belongs to the same comparability class. Let's
say it is {exp(x), exp(2x)}. Using the rule f ~ 1/f we find an element "w"
(either from the list or a new one) from the same comparability class which
goes to zero at infinity. In our example we set w=exp(-x) (but we could also
set w=exp(-2x) or w=exp(3x) ...). We rewrite the mrv set using w, in our case
{1/w,1/w^2}, and substitute it into f. Then we expand f into a series in w:

    f=c0*w^e0 + c1*w^e1 + ... + O(w^en),        where e0<e1<...<en, c0!=0

but for x->infty, lim f = lim c0*w^e0, because all the other terms go to zero.
So, 
    for e0>0, lim f = 0
    for e0<0, lim f = +-infty   (the sign depends on the sign of c0)
    for e0=0, lim f = lim c0

We need to recursively compute limits at several places of the algorithm, but
as is shown in the PhD thesis, it always finishes.

Important functions from the implementation:

compare(a,b,x) compares "a" and "b" by computing the limit L.
mrv(e,x) returns the list of most rapidly varying (mrv) subexpressions of "e"
rewrite(e,Omega,x,wsym) rewrites "e" in terms of w
leadterm(f,x) returns the lowest power term in the series of f
mrvleadterm(e,x) returns the lead term (c0,e0) for e
limitinf(e,x) computes lim e  (for x->infty)
limit(e,z,z0) computes any limit by converting it to the case x->infty

all the functions are really simple and straightforward except rewrite(),
which is the most difficult part of the algorithm.

"""

import sym as s

def intersect(a,b):
    for x in a:
        if member(x,b): return True
    return False

def member(x,a):
    for y in a:
        if x == y: return True
    return False

def union(a,b):
    z=a[:]
    for x in b:
        if not member(x,a):
            z.append(x)
    return z

def leadterm(f,x):
    """Returns the leading term c0*x^e0 of the power series of f in x with the
    lowest power or x in a form (c0,e0)
    """
    series=f.series(x,1).eval()
    assert series!=0
    def domul(x):
        if len(x)>1:
            return s.mul(x)
        return x[0]
    def extract(t,x):
        if not has(t,x):
            return t,s.rational(0)
        if isinstance(t,s.pow):
            return  s.rational(1),  t.b
        elif isinstance(t,s.symbol):
            return  s.rational(1),  s.rational(1)
        assert isinstance(t,s.mul)
        for i,a in enumerate(t.args):
            if has(a,x):
                if isinstance(a,s.pow):
                    return  domul(t.args[:i]+t.args[i+1:]),  a.b
                elif isinstance(a,s.symbol):
                    return  domul(t.args[:i]+t.args[i+1:]),  s.rational(1)
                assert False
        return t,s.rational(0)
    if not isinstance(series,s.add):
        return extract(series,x)
    lowest=(0,(s.rational(10)**10).eval())
    for t in series.args:
        t2=extract(t,x)
        if t2[1]<lowest[1]:
            lowest=t2
    return lowest

def limit(e,z,z0):
    """Currently only limit z->z0+"""
    x=s.symbol("x")
    e0=e.subs(z,z0+1/x)
    return limitinf(e0,x)

def limitinf(e,x):
    """Limit e(x) for x-> infty"""
    #print "limitinf:",e
    if not has(e,x): return e #e is a constant
    c0,e0=mrvleadterm(e,x) 
    sig=sign(e0,x)
    if sig==1: return s.rational(0) # e0>0: lim f = 0
    elif sig==-1: return s.infty #e0<0: lim f = +-infty   (the sign depends on the sign of c0)
    elif sig==0: return limitinf(c0,x) #e0=0: lim f = lim c0

def has(e,x):
    return not e.diff(x).isequal(s.rational(0))

def sign(e,x):
    """Returns a sign of an expression at x->infty.
    
        e>0 ... 1
        e==0 .. 0
        e<0 ... -1
    """
    if isinstance(e,s.number):
        return e.sign()
    elif e == x: 
        return 1
    elif isinstance(e,s.mul): 
        a,b=e.getab()
        return sign(a,x)*sign(b,x)
    elif isinstance(e,s.exp): 
        return 1 
    elif isinstance(e,s.pow):
        if sign(e.a,x) == 1: 
            return 1
    raise "cannot determine the sign of %s"%e

def rewrite(e,Omega,x,wsym):
    """e(x) ... the function
    Omega ... the mrv set
    wsym ... the symbol which is going to be used for w

    returns the rewritten e in terms of w.
    """
    for t in Omega: assert isinstance(t,s.exp)
    assert len(Omega)!=0
    def cmpfunc(a,b):
        return -cmp(len(mrv(a,x)), len(mrv(b,x)))
    #if len(Omega)>1:
    #    print
    #    print "-"*60
    #    print "Omega       :",Omega
    Omega.sort(cmp=cmpfunc)
    g=Omega[-1] #g is going to be the "w" - the simplest one in the mrv set
    if sign(g.arg,x)==1: wsym=1/wsym #if g goes to infty, substitute 1/w
    O2=[]
    for f in Omega: #rewrite Omega using "w"
        c=mrvleadterm(f.arg/g.arg,x)
        assert c[1]==0
        O2.append((s.exp(f.arg-c[0]*g.arg)*wsym**c[0]).eval())
    f=e #rewrite "e" using "w"
    for a,b in zip(Omega,O2):
        f=f.subs(a,b)

    #if len(Omega)>1:
    #    print "Omega sorted:",Omega
    #    print "w=%s, wsym=%s"%(g,wsym)
    #    print "O2    sorted:",O2
    #    print "initial :",e
    #    print "final   :",f

    return f

def moveup(l,x):
    return [e.subs(x,s.exp(x)).eval() for e in l]

def movedown(l,x):
    return [e.subs(x,s.ln(x)).eval() for e in l]

def mrvleadterm(e,x,Omega=None):
    """Returns (c0, e0) for e."""
    e=e.eval()
    if not has(e,x): return (e,s.rational(0))
    if Omega==None:
        Omega=mrv(e,x)
    #else: take into account only terms from Omega, which are in e.
    if member(x,Omega):
        return movedown(mrvleadterm(moveup([e],x)[0],x,moveup(Omega,x)),x)
    wsym=s.symbol("w")
    f=rewrite(e,Omega,x,wsym)
    return leadterm(f,wsym)

def mrv(e,x):
    "Returns the list of most rapidly varying (mrv) subexpressions of 'e'"
    if not has(e,x): return []
    elif e==x: return [x]
    elif isinstance(e,s.mul): 
        a,b=e.getab()
        return max(mrv(a,x),mrv(b,x),x)
    elif isinstance(e,s.add): 
        a,b=e.getab()
        return max(mrv(a,x),mrv(b,x),x)
    elif isinstance(e,s.pow) and isinstance(e.b,s.number):
        return mrv(e.a,x)
    elif isinstance(e,s.ln): 
        return mrv(e.arg,x)
    elif isinstance(e,s.exp): 
        if limitinf(e.arg,x)==s.infty:
            return max([e],mrv(e.arg,x),x)
        else:
            return mrv(e.arg,x)
    raise "unimplemented in mrv: %s"%e

def max(f,g,x):
    """Computes the maximum of two sets of expressions f and g, which 
    are in the same comparability class, i.e. max() compares (two elements of)
    f and g and returns the set, which is in the higher comparability class
    of the union of both, if they have the same order of variation.
    """
    if f==[]: return g
    elif g==[]: return f
    elif intersect(f,g): return union(f,g)
    elif member(x,f): return g
    elif member(x,g): return f
    else:
        c=compare(f[0],g[0],x)
        if c==">": return f
        elif c=="<": return g
        else: return union(f,g)
    raise "max error",f,g

def compare(a,b,x):
    """Returns "<" if a<b, "=" for a==b, ">" for a>b"""
    c=limitinf(s.ln(a)/s.ln(b),x)
    if c==s.rational(0): return "<"
    elif c==s.infty: return ">"
    else: return "="