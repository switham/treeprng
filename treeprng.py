#!/usr/bin/env python
""" 
Repeatable virtual trees of pseudorandom numbers.  Alpha test version.
See warnings in RandomTree's docstring below.
"""

import hashlib, random
try:
    import cPickle as pickle
except:
    import pickle


class TreePRNG(object):
    """
    A TreePRNG object is a node in a repeatable virtual tree whose leaves
    are pseudorandom number generators (PRNGs).  
        lotr = TreePRNG("The Lord of the Rings")
    Each node can be indexed like a read-only dict of virtually-already-
    existing subnodes:
        orcs = lotr["orcs"]
        orc192 = orcs[192]
        hobbits = lotr["hobbits"]
        frodo = hobbits["frodo"]
        fmr = frodo["measurements"]
    Or it can be used as an instance of a random.Random PRNG...
        height = fmr.random() * 2.0 + 3.0
        hair_color = fmr.choice(["brown", "black", "blond", "red"])
    ...in which case it will generate a unique sequence of numbers that 
    will repeat if you revisit the same path in the tree.  Once a TreePRNG
    object has been used as a dict, it will refuse to act as PRNG, and 
    vice-versa.

    Although TreePRNG uses a cryptographic hash function to seed the 
    PRNGs, they are not cryptographic PRNGs.
    
    This is an alpha test version.
    1) Until the internal representations are settled, different versions of
       this module will produce different random numbers for the same
       tree paths.
    2) It's not especially fast.  subnode = node["key"] involves a hashlib 
       update(), and any node's first use as a PRNG involves a hashlib 
       digest() and a random.Random seeding.
    3) It may be too easy to find sequences repeated in different locations.
       (Using unbroken hashes (not the default sha1), I think it should take
       about 2**(nbits/2) probes to find a repeat, where nbits is the
       number of bits in the hash digest type used.)
    """
    def __init__(self, seed, hashname="sha1", state=None):
        """
        Produce the top node of a tree.  
         o  seed is a pickle-able Python object, see pickle_key().
            It's mandatory; the seed() method is disabled.
         o  hashname is one of the names in hashlib.algorithms.
         o  state is the output of the getstate() of a TreePRNG,
            and overrides seed and hashname if given.
        Consider seeding with a combination of
         o  A really-unique application identifier like
            "com.mydomain.myhost.myname.myapplication".
         o  Application version number.
         o  ID of the user unique across all users of the application.
         o  Unique run id that can be used to recreate/revisit/resume a run.
         o  With multiple threads or processors, unique logical IDs for 
            tasks,  so that saved runs can resume in different situations.
        Something like this:
            root = TreePRNG("com.mydomain.myhost.myname.myapplication")
            task = root[app_ver][user_id][run_id][task_id]
        
        Subnodes and leaves are TreePRNG instances also.
        """
        self.prng = None
        if state:
            self.hash, prng_state, self.is_dict = state
            if prng_state:
                self.__become_prng()
                self.prng.setstate(prng_state)
            if self.is_dict:
                self.__become_dict()
        else:
            self.hash = hashlib.new(hashname)
            self.hash.update(pickle_key(seed))
            self.prng = None
            self.is_dict = False

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
        method from the PRNG.
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
        """ Not implemented.  To set the state, create a new TreePRNG. """
        raise NotImplementedError()

    def seed(self, *args, **kargs):
        """ Not implemented.  To seed a PRNG, create a new TreePRNG. """
        raise NotImplementedError()

    def jumpahead(self, *args, **kargs):
        """ 
        Not implemented.  For multiple random sequences under one node, do:
        prng1 = node[id_1]
         prng2 = node[id_2]
        ...
        With a unique id for each sequence.
        """
        raise NotImplementedError()


def pickle_key(k):
    """
    Create an input string for a secure hash, using pickle.
    Basic types convert in a repeatable way with this method:
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
    "equal things are equal".
    So far this means: 
        An embedded float is converted to an equal long or int if possible.
        An embedded long is converted to an equal int if possible.
    Where "embedded" means in a (nested) list or tuple...or just k itself.
    Members of classes we aren't sure of (e.g. sets, dicts) are left alone.

    Note: pickle_key_prep, pickle_key, and TreePRNG aren't meant to be
    used with large objects as keys.  The cost is the temporary storage, 
    and time while a hash function digests the massaged, pickled object.
    """
    if type(k) == list:  # Not isinstance -- don't touch subclasses.
        for i, x in enumerate(k):
            y = pickle_key_massage(x)
            if y is not x:
                k = k[:i] + [y] + [pickle_key_massage(z) for z in k[i+1:]]
                break
    elif type(k) == tuple:  # Not isinstance -- don't touch subclasses.
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
