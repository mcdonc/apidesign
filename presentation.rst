.. include:: <s5defs.txt>

API Design for Libraries
========================

:Authors: Chris McDonough, Agendaless Consulting
:Date: X/X/2013 (PyCon 2013)

..  footer:: Chris McDonough, Agendaless Consulting

Who Am I
--------

- Bad Perl hacker until Python.  Came to Python via Zope in 1999.  Worked at
  Digital Creations (aka Zope Corporation) until 2003.

- Primary author of: Pyramid web framework, Supervisor UNIX process control
  system, Deform form system, Repoze collection of middleware, and other
  unmentionables.  Contributor to Zope, WebOb, and other OSS projects.

Guidelines
----------

- If you follow these guidelines, your library will be useful for other
  people in both the scenarios you expect and in ones you don't.

- The importance of these guidelines increases along with the number of users
  whom will depend upon your library.  The more people whom use your library,
  the more likely it is that some of them will try to use your library in
  unexpected ways.  Ex: someone will want to create two separate applications
  that use your library in the same process.

Why People Make Bad Libraries
-----------------------------

- Library authors sometimes do the wrong things for the right reasons.

- A skewed sense of how people will need to use the library they're
  developing.

- Skewed perception of what's acceptable for the sake of convenience.

- Skewed perception of "cleanliness".

Differences: Libs, Frameworks, Apps
-----------------------------------

- Library: maintains none or little of its own state, no or few callbacks.

- Framework: no or little state, but lots of callbacks.  Some frameworks
  mutate or require global state (IMO inappropriately).  A web framework
  instance is often fed to a global mainloop, but that doesn't mean it should
  use globals with abandon.  Even then if the framework doesn't use global
  state, with a little care, two framework instances can live in the same
  process (e.g. a multiplexer for a "composite" application where each app
  serves from a prefix).

- Application: maintains lots of state, can use global state with abandon.

- It's not discrete, it's a gradient.

Convenience != "Cleanliness"
----------------------------

- The assumption: "clean" == "is maximally convenient for the case i presume
  this code is going to be used in"

- The reality:  "clean" == "maximally understandable; without surprises or
  exceptions".

- The fewer limiting assumptions made by the library, the fewer surprises it
  will have and the more understandable it will be.

- Ex: thread-local state management doesn't work in async systems without
  magical intervention.

I Care About Your Feelings
--------------------------

- During this talk, I call out antipattern examples from actual projects
  (including my own).

- If I use code from one of your projects as an antipattern example, it
  doesn't mean I don't like you.  It doesn't even mean I don't respect and
  use your code.

- This talk is impossible to give without showing negative examples.  I'm
  lazy and the best negative examples are those that already exist.

#1: Global State is Precious
----------------------------

- Avoid the mutation of global (module-level) state when your library is
  imported.  

- Avoid requiring that other people mutate global state to use your library.
  Ex: telling people to set an environment variable or call a function
  which mutates global state to use your library

- If your library mutates global state when it's imported or you tell people
  to mutate global state to use it, it's not really a library, it's kinda
  more like an application.

OK at Module Scope
------------------

- An import of another module or global.

- Assignment of a variable name in the module to some constant value.

- The addition of a function via a def statement.

- The addition of a class via a class statement.

- Control flow which may handles conditionals for platform-specific handling
  or failure handling of the above.

- Anything else will usually end in tears.

Antipatterns
------------

- Antipatterns from the Python standard library: ``logging``,
  ``multiprocessing``, ``mimetypes``.

``atexit`` Func Registered During Import
-----------------------------------------

Importing ``multiprocessing`` from the standard library causes an atexit
function to be registered at module scope:

.. sourcecode:: python

   def _exit_function():

       # ... elided ...

       for p in active_children():
           if p._daemonic:
               info('calling terminate() for daemon %s', p.name)
               p._popen.terminate()

       # .. elided ...

   atexit.register(_exit_function)

``atexit`` Func Registered During Import (2)
--------------------------------------------

From ``logging`` module:

.. sourcecode:: python

   _handlerList = [] # mutated by logging.getLogger, etc

   import atexit

    def shutdown(handlerList=_handlerList):
        for h in handlerList[:]:
           # ...

   atexit.register(shutdown)

Why is This Bad?
----------------

- It's unexpected.  Registration of an ``atexit`` function is a mutation of
  global state that results solely from an *import* of a module, whether or
  not you actually use any APIs from the module.  Your program will behave
  differently at shutdown if you cause ``multiprocessing`` or ``logging`` to
  be imported, or if you import a third-party module that happens to import
  one of them (you might not even know).

- It's unnecessary.  both ``multiprocessing`` and ``logging`` need to manage
  global state.  But neither really needs to register an `atexit`` function
  until there's any nondefault state to clean up.

- It's convenient until your process shutdown starts spewing errors that you
  can't figure out at unit test exit time.  Then it's pretty damn
  inconvenient.  Example: seemingly random error message at shutdown time if
  you attempt to use the ``logging.Handler`` class independent of the rest of
  the framework (see next slide).

Globals Mutation From Constructor
---------------------------------

Mutating a global registry as the result of an object constructor (again from
``logging``).

.. sourcecode:: python

   _handlers = {}  #repository of handlers

   class Handler(Filterer):
       def __init__(self, level=NOTSET):
           # .. elided code ...
           _acquireLock()
           try:
               _handlers[self] = 1
               _handlerList.insert(0, self)
           finally:
               _releaseLock()
           # .. elided code ..

Globals Mutation From Constructor (2)
-------------------------------------

From ``asyncore`` (at least it lets you choose the ``map``):

.. sourcecode:: python

    socket_map = {}

    class dispatcher:
        def __init__(self, sock=None, map=None):
            if map is None:
                self._map = socket_map
            else:
                self._map = map
            if sock:
                # .. set_socket mutates the map ...
                self.set_socket(sock, map)

What's Wrong With This?
-----------------------

- Side effect of globals mutation makes out-of-context reuse of the class
  more difficult than necessary.

- You can't make an instance without mutating global state.

- If you really must do this, create an alternative "application" API for
  instance construction which constructs an instance and *then* mutates a
  global, but let the library be just a library.

- Makes unit testing hard (need to clean up module global state).

Module-Scope Functions Called for Side-Effects
----------------------------------------------

Users of the ``logging`` module are encouraged to do this:

.. sourcecode:: python

   import logging
   logging.basicConfig()
   logging.addLevelName(175, 'OHNOES')

Calls for Side-Effects (2)
---------------------------

``mimetypes`` module maintains a global registry:

   import mimetypes
   mimetypes.init()
   mimetypes.add_type('text/foo', '.foo')

What's Wrong with This?
-----------------------

- The ``logging`` and ``mimetypes`` APIs encourage users to mutate external
  global state by calling APIs that have return values that nobody cares
  about (the APIs are called only for side effects).

- Introduces responsibility, chronology, and idempotency confusion.  Who is
  responsible for calling this?  When should they call it?  Can it be called
  more than once?  If it is called more than once, what happens when it's
  called the second time?

- ``logging`` maintains a global registry as a dictionary at module scope.
  Calling ``basicConfig()`` is effectively a structured monkeypatch of
  ``logging`` module state.  Same for ``addLevelName``.  Logging classes know
  about this global state and use it.  The ``mimetypes`` module API maintains
  a global registry too.  Same deal.

Alternatives to Mutable Globals
-------------------------------

- All of these packages could choose not manage any global (module-scope)
  state at all, and encapsulate all state in an instance.  This has
  downsides.

- Downside for ``multiprocessing``: its API won't match that of
  ``threading``.

- Downside for ``logging``: streams related to the same handler might
  interleave.

- Downside for ``mimetypes``: might need to reparse system mimetype files.

- In general, however, no globals in *library* code is the best solution.
  You can always create the library code such that it mutates no global
  state, but then, as necessary, create a convenience application module/API
  which integrates the library stuff and manages global state on behalf of
  its users.  This makes the library code reusable, and if someone wants to
  build an alternate set of convenience APIs, they can.

#2: Configuration at Module Scope
---------------------------------

- Settings at module scope, requiring monkeypatching to change.

- Or configuration systems which tell the user to make a Python module
  available for the *library* to import.

Antipatterns
------------

``logging`` and Django.

Not-Really-Configuration
------------------------

From the ``logging`` package:

.. sourcecode:: python

   #
   #raiseExceptions is used to see if exceptions during handling should be
   #propagated
   #
   raiseExceptions = 1

What's Wrong With This?
-----------------------

- Nothing, if it's only for the benefit/convenience of the library developer
  himself.

- But if it's presence is advertised to users, it's pseudo-configuration;
  there's no way to change it without monkeypatching the module.

- The setting is global.  No way to use separate settings per process.

Inversion of Configuration Control
----------------------------------

Django ``settings.py``:

.. sourcecode:: python

   # Django settings for mysite project.

   DEBUG = True
   TEMPLATE_DEBUG = DEBUG

   ADMINS = (
       # ('Your Name', 'your_email@example.com'),
   )

   # .. and so on ..

What's Wrong With This?
-----------------------

- The library/framework itself wants to import settings from this module.

- But the author of the settings code also usually wants to import stuff from
  the library/framework.

- Extremely high likelihood of circular import problems (framework imports
  settings, settings imports framework).

- The settings are global.  No way to use separate settings per process.

- Better: suggest non-Python configuration so likeihood of circular import
  problems is reduced.  Configuration parsing can be done at startup time, in
  a nonglobal place, allowing multiple usages of the library per process.

#3: Avoid Convenience Features
------------------------------

- Avoid convenience (magical) features such as thread local access until
  you've finished creating the inconvenient (nonmagical) version.

- Expose the inconvenient version as a set of APIs.

- Make the convenience features optional, through a separate set of APIs.

- You can always add convenience to a library, you can never remove it.

Antipatterns
------------

- Pylons and Flask.

- Stacked object proxies / context locals.

Pylons' Stacked Object Proxies
------------------------------

Pylons offers importable ``request`` and ``response`` objects ("stacked
object proxies"):

.. sourcecode:: python

   from pylons import request, response
   from pylons.controllers import BaseController

   class Controller(BaseController):
       def ok(self):
           if request.params.get('ok'):
               response.body = 'ok'
           else:
               response.body = 'not ok'
           return response

Flask's Context Locals
----------------------

Flask has the same concept for its ``request``:

.. sourcecode:: python

   from flask import request
   @app.route('/login', methods=['POST', 'GET'])
   def login():
       error = None
       if request.method == 'POST':
           if valid_login(request.form['username'],
                          request.form['password']):
               return log_the_user_in(request.form['username'])
           else:
               error = 'Invalid username/password'

What's Wrong With This?
-----------------------

- Things that are not logically global (``request`` and/or ``response``) are
  obtained via an import.

- Stacked object proxies / context locals are magical proxy objects that
  access a thread-local (action-at-a-distance) when interrogated.  Nonmagical
  version is hidden away from you (``request = self._py_object.request``) in
  Pylons.

- Encourages inappropriate coupling of non-web-context code to a web context
  (e.g. "model" modules start to ``import request``).

- Makes unit testing harder than it needs to be.

- Function and class constructor arguments exist for a reason.  Just pass
  things around.  Yes, it's less convenient.  It's usually also the right
  thing to do *in library code*.  Remember that people will want to use your
  stuff to compose larger systems, and your assumptions about environment may
  not fit there.

- You can always create an optional convenience API that allows you to elide
  the passing of state, but you can never remove a "mandatory" convenience
  feature.

#4: Avoid Knobs on Knobs
------------------------

- A "knob" is often a replaceable component in a framework or library.

- When that replaceable component itself offers a knob, this is the "knobs on
  knobs" pattern.

Pyramid Authentication Policy Knob
----------------------------------

From ``pyramid``, the use of an authentication policy knob:

.. sourcecode:: python

   from pyramid.authentication import AuthTktAuthenticationPolicy
   from pyramid.config import Configurator

   GROUPS = {'fred':['editors']}

   def groupfinder(userid, request):
       return GROUPS.get(userid)

   pol = AuthTktAuthenticationPolicy(callback=groupfinder)
   config = Configurator()
   config.set_authentication_policy(pol)

Why Is This Bad?
----------------

- We're actually dealing with two separate frameworks.

- There's the Pyramid configurator ``set_authentication_policy`` method,
  which accepts something that adheres to the "authentication policy
  interface" (the interface requires a number of methods).
  AuthTktAuthenticationPolicy implements this interface.

- But AuthTktAuthenticationPolicy is also its own mini-framework, accepting a
  ``callback`` constructor argument, which must be a callable that accepts a
  userid and a request, and which must return a sequence of groups.

- People don't understand when or why to replace "the big thing" when there's
  a "little thing" inside the big thing that's also replaceable.  The choice
  introduces indecision and confusion.

- This was done with the intent of avoiding documentation that tells people
  to subclass AuthTktAuthenticationPolicy, preferring to tell them to compose
  something together using a callback arg to the policy's constructor.  But
  telling folks to subclassing AuthTktAuthenticationPolicy and to override a
  ``find_groups`` method in the subclass would probably be less confusing, as
  this pattern is more widely understood (for better or worse).

#5: First, Do No Harm
----------------------

- Offering decorators that mutate the call signature of a function or method.

#6: Composition Beats Inheritance
---------------------------------

- Offering up superclasses is usually a bad idea (although not always).

- Composition beats inheritance almost always.

#7: Avoid Requiring Imports for Side-Effects
---------------------------------------------

- Importing a module solely for its side effects (sqla declarative mode).

Example
-------

- How convenience makes unit testing hard.

- system testing vs unit testing, YAGNI/explicilt dependencies/quicker tests,
  test_spam only needs the 'spambayes_score' config value, not your entire
  django settings module (which you have to setup/clear after every test),
  can't run those tests in parallel

