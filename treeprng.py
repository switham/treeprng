#!/usr/bin/env python
""" 
Repeatable virtual trees of pseudorandom numbers.  Alpha test version.

https://github.com/switham/treeprng/wiki/Documentation
https://github.com/switham/treeprng/wiki/Critique
"""

# Copyright (c) 2013-2014 Steve Witham.  All rights reserved.  
# treeprng is available under a BSD license, whose full text is at
#   https://github.com/switham/treeprng/blob/master/LICENSE

import hashlib, random
try:
    import cPickle as pickle
except:
    import pickle


class TreePRNG(object):
    """
    A TreePRNG object is a virtual tree of nested Python dicts,
    with pseudorandom numbers at the bottom.  See the user guide:
        https://github.com/switham/treeprng/wiki/Documentation
    """
    def __init__(self, hashname="sha1"):
        """
        Produce the root of a tree in a "dict" state.
         o  hashname is one of the names in hashlib.algorithms.

        Subnodes are TreePRNG instances also.
        """
        self.prng = None
        self.hash = hashlib.new(hashname)
        self.prng = None
        self.is_dict = True # The root is always a dict.

    def __getitem__(self, i):
        """
        Given a TreePRNG t,
            s = t[i]
        Gives a daughter node of t.  This commits t to be a dict rather 
        than a PRNG, but otherwise doesn't change t.
        i can be any picklable object, but if you want repeatability 
        across runs of a program, see help(pickle_key).
        """
        assert not self.prng, "Can't be a dict--already used as a PRNG."
        if not self.is_dict:
            self.__become_dict()
        new_hash = self.hash.copy()
        new_hash.update(pickle_key(i))
        return TreePRNG(None, state=(new_hash, None, False))

    def __become_prng(self):
        assert not self.is_dict, "Can't be a PRNG--already used as a dict."
        self.prng = random.Random(long(self.hash.hexdigest(), 16))
        self.hash = None

    def __become_dict(self):
        assert not self.prng, "Can't be a dict--already used as a PRNG."
        self.is_dict = True

    def __getattr__(self, attr):
        """
        This handles calls to any random.Random methods by returning the
        method of the PRNG.
        """
        if not self.prng:
            self.__become_prng()
        return getattr(self.prng, attr)

    def getstate(self):
        """
        Return a tuple that can be used to initialize a new TreePRNG.
        (Not sure whether this survives across runs of Python.)
        """
        if self.prng:
            return (None, self.prng.getstate(), False)
        else:
            return (self.hash, None, self.is_dict)

    def setstate(self, *args, **kargs):
        """ Disabled.  To set the state, create a new TreePRNG. """
        raise NotImplementedError()

    def seed(self, *args, **kargs):
        """ Disabled.  To seed a PRNG, create a new TreePRNG. """
        raise NotImplementedError()

    def jumpahead(self, *args, **kargs):
        """ 
        Disabled.  For multiple random sequences under one node, do:
        prng1 = node[id_1]
        prng2 = node[id_2]
        ...
        With a unique id for each sequence.
        """
        raise NotImplementedError()


def pickle_key(k):
    """
    Create an input string for a secure hash, using pickle.
    These basic types convert in a repeatable way with this method:
        None, False, True
        string, unicode string
        float, long, int
        tuple -- empty, or tuple of items that convert repeatably
        list -- empty, or list of items that convert repeatably
    pickle_key_massage() (see) is used to make sure equal-comparing numbers
    become actually equal before pickling.
    """
    return pickle.dumps(pickle_key_massage(k), 2)


def pickle_key_massage(k):
    """
    Return (a possibly massaged copy of) input for pickle_key to make sure
    "equal things are equal".  So far this means: 
        An embedded float is converted to an equal long or int if possible.
        An embedded long is converted to an equal int if possible.
    Where "embedded" means in a (nested) list or tuple...or just k itself.
    Members of classes we aren't sure of (e.g. sets, dicts) are left alone.

    Note: pickle_key_massage, pickle_key, and TreePRNG aren't meant to be
    used with large objects as keys.  The hash can only absorb a certain
    amount of, um, pseudo-entropy.  But the cost is only storage (of both 
    the massaged and picked versions) which is recovered immediately, and 
    time (while the hash digests the pickle).
    """
    if type(k) == list:  # ==, not isinstance -- don't massage subclasses.
        for i, x in enumerate(k):
            y = pickle_key_massage(x)
            if y is not x:
                k = k[:i] + [y] + [pickle_key_massage(z) for z in k[i+1:]]
                break
    elif type(k) == tuple:  # ==, not isinstance -- don't massage subclasses.
        for i, x in enumerate(k):
            y = pickle_key_massage(x)
            if y is not x:
                k = k[:i] + (y,) + \
                   tuple(pickle_key_massage(z) for z in k[i+1:])
                break
    elif isinstance(k, float):
        if k == int(k):  k = int(k)
    elif isinstance(k, long):
        k = int(k)
    return k
