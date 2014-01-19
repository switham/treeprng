#!/usr/bin/env python
""" 
Repeatable virtual trees of pseudorandom numbers.  Alpha test version.
    1) Until the internal representations are settled, different versions of
       this module will produce different random numbers for the same
       tree paths.
    2) It's not especially fast.  subnode = node["key"] involves a hashlib 
       update(), and generating a random number generally involves a hashlib 
       digest().
    3) It may be too easy to find sequences repeated in different locations.
       (Using unbroken hashes (not the default sha1), I think it should take
       about 2**(nbits/2) probes to find a repeat, where nbits is the
       number of bits in the hash digest type used.)

Copyright (c) 2013-2014 Steve Witham.  All rights reserved.  
treeprng is available under a BSD license, whose full text is at
    https://github.com/switham/treeprng/blob/master/LICENSE
"""

import hashlib, random
try:
    import cPickle as pickle
except:
    import pickle


def lifecycle():
    """    
    TreePRNG instances have a LIFE CYCLE with THREE STATES:
    "uncommitted," "dict," and "spent."
    
    A TreePRNG is created in an uncommitted state.  If you use it like a 
    Python dict, it returns a new TreePRNG.  The child is uncommitted, 
    but the parent becomes committed to being a dict of TreePRNGs.
    
    If you use an uncommitted TreePRNG by calling one of the methods of
    the Python random.Random class (e.g. .random(), .choice(), 
    .shuffle()...), it does what you would expect that method to do, and 
    then goes into the spent state, where it won't do anything else.

    If you call the .sequence() method, it returns a seeded instance of
    (a subclass of) the random.Random class, which you can use as long
    as you like.  But the TreePRNG object goes into the spent state.

    WHY THE DICT AND SPENT STATES?

    To try to catch code that tries to use the same set of random numbers 
    for two different purposes, by mistake.  Or would get different results
    by asking for the same numbers, but in different order.  Here is how to
    use TreePRNG correctly:

    The simple way is to give a different address (path of dict keys) to
    every single random number (actually, to every Random method call).
    Hopefully this use-pattern will seem natural.  So after setting up...
        frodo = TreePRNG("Lord of the Rings")["hobbits"]["Frodo"]
    ...this works:
        frodo_hair = frodo["hair"].choice(["brown", "black", "blond", "red"])
        frodo_height = frodo["height"].random() * 2.0 + 3.0
    ...and gives the same results as:
        frodo_height = frodo["height"].random() * 2.0 + 3.0
        frodo_hair = frodo["hair"].choice(["brown", "black", "blond", "red"])
    ...but this DOES NOT WORK and raises an exception:
        frodo_hair = frodo.choice(["brown", "black", "blond", "red"])
        frodo_height = frodo.random() * 2.0 + 3.0

    Lists of (e.g.) numbers can be generated this way:
        f_ns_dict = frodo["nums"]
        frodo_nums = [f_ns_dict[i].random() for i in range(13)]

    Giving everything an address minimizes the chance of accidental reuse 
    and helps keep things stable in the face of code changes.  But there 
    may be times when you Know What You're Doing and you really want an 
    old-fashioned stateful random number generator.  In that case,
        f_ns_prng = frodo["nums"].sequence()
        frodo_nums = [f_ns_prng.random() for i in range(13)]
    """
    

class TreePRNG(object):
    """
    A TreePRNG object can be thought of as, virtually,
     o  an infinite subset of an infinite random universe.
     o  an unlimited-width and -depth subtree within the infinitely wide 
        and deep directory tree of an infinite hard disk of random data.
     o  a nested Python dictionary within a nested dictionary of randomness.
     o  a partial or complete, unlimited "size" seed for a pseudorandom 
        number generator (which nevertheless uses only a fixed amount of
        memory).
    
    By virtual, we mean that the source of numbers is actually of finite
    (though astronomical) size, and pseudorandom, not truly random. 

    This source of random numbers is read-only.  It is always the same for
    everyone, and static in every location of the tree.  You access 
    different data by addressing different locations within it.  The access 
    paths are truly not limited, and the intent is that programs that take 
    reasonable care can range as far and wide as they like within the 
    space, and never find evidence that the numbers aren't independently 
    random everywhere.
    
    IMPORTANT: TreePRNG instances have a LIFE CYCLE with THREE STATES.
    See help(treeprng.lifecycle) or help(TreePRNG.lifecycle).

    QUICK START
        lotr = TreePRNG("The Lord of the Rings")
        hobbits = lotr["hobbits"]
        frodo = hobbits["frodo"]
        frodo_height = frodo["height"].random() * 2.0 + 3.0
        frodo_hair = frodo["hair"].choice(["brown", "black", "blond", "red"])

    Although TreePRNG uses a cryptographic hash function to seed the 
    PRNGs, they are not cryptographic PRNGs.
    """
    def __init__(self, seed, hashname="sha1", state=None):
        """
        Produce the top node of a tree in an uncommitted state.
         o  seed is a pickle-able Python object, see pickle_key().
            It's mandatory; the seed() method is disabled.
         o  hashname is one of the names in hashlib.algorithms.
         o  state is the output of the getstate() of a TreePRNG,
            and overrides seed and hashname if given.
        Consider seeding with a combination of things like
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

        Subnodes are TreePRNG instances also.
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

    def lifecycle(self):
        """ (lifecycle help gets inserted here.) """
        pass

    lifecycle.__doc__ = globals()["lifecycle"].__doc__

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
