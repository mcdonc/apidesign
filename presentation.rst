.. include:: <s5defs.txt>

API Design for Libraries
========================

:Authors: Chris McDonough, Agendaless Consulting
:Date: 03/15/2013 (PyCon 2013)

..  footer:: Chris McDonough, Agendaless Consulting

Who Am I
--------

Came to Python via Zope in 1999.  Worked at Digital Creations (aka Zope
Corporation) until 2003.  Now a consultant with Agendaless Consulting.

Primary author of Pyramid web framework, Supervisor UNIX process control
system, Deform form system, Repoze collection of middleware, and other
unmentionables.  Contributor to Zope, WebOb, and other OSS projects.

I Care About Your Feelings
--------------------------

During this talk, I call out antipattern examples from actual projects,
including my own.

If I use code from one of your projects as an antipattern example, it
doesn't mean I don't like you.

This talk is impossible to give without showing negative examples.

.. class:: handout

  I'm lazy and the best negative examples are those that already exist.

Libs, Frameworks, Apps
----------------------

Application: Maintains lots of state, can use global state with abandon.

Framework: No or little state, but lots of callbacks.  

Library: Maintains none or little of its own state, no or few callbacks.

.. class:: handout

   A web framework instance is often fed to a global mainloop, but that doesn't
   mean it should use globals with abandon.  Even then if the framework doesn't
   use global state, with a little care, two framework instances can live in
   the same process.  Some frameworks mutate or require global state (IMO
   inappropriately).

Guidelines
----------

This talk covers four guidelines.

If you follow these guidelines, your library will be useful for strangers in
both the scenarios you expect and in ones you don't.

The importance of the guidelines increases with the number of users whom might
reuse your code and your social distance from those users.

Guidelines
----------

#1: Global State is Precious

#2: Don't Design Exclusively For Convenience

#3: Avoid Knobs on Knobs

#4: Composition Usually Beats Inheritance

#1: Global State is Precious
----------------------------

- Avoid unnecessary mutation of global (module-level) state when your library
  is imported.

- Avoid requiring that other people mutate global state to use your library.
  Ex: telling people to set an environment variable or call a function
  which mutates global state to use your library.

- If your library mutates global state when it's imported or you require
  people to mutate global state to use it, it's not really a library, it's
  kinda more like an application.

Registration During Import
--------------------------

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

Reg. During Import (2)
----------------------

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

Unexpected.  Registration of an ``atexit`` function is a mutation of global
state that results solely from an *import* of a module, whether or not you
actually use any APIs from the module.

Unnecessary.  Both ``multiprocessing`` and ``logging`` choose to manage global
state.  But neither really needs to register an ``atexit`` function until
there's any nondefault state to clean up.

.. class:: handout

   Your program will behave differently at shutdown if you cause
   ``multiprocessing`` or ``logging`` to be imported, or if you import a
   third-party module that happens to import one of them (you might not even
   know).

   It's convenient until your process shutdown starts spewing errors that you
   can't figure out at unit test exit time.  Then it's pretty inconvenient.
   Example: seemingly random error message at shutdown time if you attempt to
   use the ``logging.Handler`` class independent of the rest of the framework.

Ctor Globals Mutation
---------------------

Mutating a global registry as the result of an object constructor (again from
``logging``).

.. sourcecode:: python

   _handlers = {}  #repository of handlers
   _handlerList = [] # ordered list of handlers

   class Handler(Filterer):
       def __init__(self, level=NOTSET):
           # .. elided code ...
           _handlers[self] = 1
           _handlerList.insert(0, self)
           # .. elided code ..

Ctor Globals Mutation (2)
-------------------------

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

Calls for Side-Effects
----------------------

Users of the ``logging`` module are encouraged to do this:

.. sourcecode:: python

   import logging
   logging.basicConfig()
   logging.addLevelName(175, 'OHNOES')

Calls for Side-Effects (2)
---------------------------

``mimetypes`` module maintains a global registry:

.. sourcecode:: python

   import mimetypes
   mimetypes.init()
   mimetypes.add_type('text/foo', '.foo')

Calls for Side-Effects (3)
--------------------------

From the Python Braintree payment gateway API:

.. sourcecode:: python

   import braintree

   braintree.Configuration.configure(
       braintree.Environment.Sandbox,
       merchant_id="use_your_merchant_id",
       public_key="use_your_public_key",
       private_key="use_your_private_key"
       )

What's Wrong with This?
-----------------------

- The ``logging``, ``mimetypes`` and ``braintree`` APIs encourage users to
  mutate their module's global state by exposing APIs that have return values
  that nobody cares about.

- Introduces responsibility, chronology, and idempotency confusion.  Who is
  responsible for calling this?  When should they call it?  Can it be called
  more than once?  If it is called more than once, what happens when it's
  called the second time?

.. class:: handout

   ``logging`` maintains a global registry as a dictionary at module scope.
   Calling ``basicConfig()`` is effectively a structured monkeypatch of
   ``logging`` module state.  Same for ``addLevelName``.  Logging classes know
   about this global state and use it.  The ``mimetypes`` module API maintains
   a global registry too.  Same deal with Braintree.

Not-Really-Configuration
------------------------

From the ``logging`` package:

.. sourcecode:: python

   #
   # raiseExceptions is used to see if exceptions during 
   # handling should be propagated
   #
   raiseExceptions = 1

What's Wrong With This?
-----------------------

- Nothing, if it's only for the benefit/convenience of the library developer
  himself.

- But if it's presence is advertised to users, it's pseudo-configuration;
  there's no way to change it without monkeypatching the module.

- The setting is global.  No way to use separate settings per process.

Inversion of Config Control
---------------------------

Django ``settings.py``:

.. sourcecode:: python

   # Django settings for mysite project.

   DEBUG = True
   TEMPLATE_DEBUG = DEBUG

   ADMINS = (
       # ('Your Name', 'your_email@example.com'),
   )

What's Wrong With This?
-----------------------

- The library/framework wants to import values from this module.

- But since it's Python, the author of the settings code will be tempted to
  import stuff from the library/framework.  Extremely high likelihood of
  circular import problems (framework imports settings, settings imports
  framework).

- The settings are global.  No way to use separate settings per process.

OK at Module Scope
------------------

A non-circular import of another module or global.

Assignment of a variable name in the module to some constant value.

The addition of a function via a def statement.

The addition of a class via a class statement.

Control flow which handles conditionals for platform-specific failure handling
of the above.

.. class:: handout

   Anything else will usually end in tears.

Solutions
---------

Think of an application bootstrapping in two phases.

Before ``if __name__ == '__main__':``.  Do nothing.

As the result of ``if __name__ == '__main__'``.  Do everything.

Downsides
---------

Downside for ``multiprocessing`` to ditch its global state maintenance: its API
won't match that of ``threading``.

Downside for ``logging``: streams related to the same handler might interleave.

Downside for ``mimetypes``: might need to reparse system mimetype files.

But, But..
----------

You can always create library code such that it mutates no global state, but
then, as necessary, create a convenience application module which integrates
the library stuff and mutates some global state on behalf of its users.  This
makes the library code reusable, and if someone wants to use the application
code, they can.

Restraint Under Pressure
------------------------

Example of restraint under obvious pressure for convenience and magic from
the Python ``sched.scheduler`` library class:

.. sourcecode:: python

   """Each instance of this class manages its own queue.
   No multi-threading is implied; you are supposed to hack that
   yourself, or use a single instance per application."""


   scheduler = sched.scheduler()
   def do(arg): print arg
   scheduler.enter(30, 0, do, 1)
   scheduler.run()

Quote
-----

"This method of turning your code inside out is the secret to solving what
appear to be hopelessly state-oriented problems in a purely functional
style. Push the statefulness to a higher level and let the caller worry about
it. Keep doing that as much as you can, and you'll end up with the bulk of
the code being purely functional." -- http://prog21.dadgum.com/131.html

#2: Avoid Convenience
---------------------

Avoid convenience (magical) features such as thread local access until
you've finished creating the inconvenient (nonmagical) version.

Expose the inconvenient version as a set of APIs and make the convenience
features optional, through a separate set of APIs.

You can always add convenience to a library, you can never remove it.

Stacked Object Proxies
----------------------

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

- Two levels of magic: proxy that accesses a thread-local when asked for an
  attribute.

- Encourages inappropriate coupling of non-web-context code to a web context
  (e.g. "model" modules start to ``import request``).

- Makes unit testing harder than it needs to be, because proxy objects need
  to be initialized.

Instead
-------

- Design a framework so its users receive an argument (e.g. ``request``) and
  suggest to them that they pass derivations
  (e.g. ``request.GET['first_name']``) around.  It's less convenient for
  consumers.  It's usually also the right thing to do in library and
  framework code.

- You can always create an (optional) convenience API that allows your
  library's consumers to elide the passing of state, but you can never remove
  a "mandatory" convenience feature from a library.

.. class:: handout

  Remember that people will want to use your stuff to
  compose larger systems, and your assumptions about environment may not fit
  there.

Convenience != Cleanliness
--------------------------

- The assumption: "clean" == "is maximally convenient for the case I presume
  this code is going to be used in"

- The reality:  "clean" == "maximally understandable; without surprises or
  exceptions".

- The fewer limiting assumptions made by the library, the fewer surprises it
  will have and the more understandable it will be.

- Ex: thread-local state management doesn't work in async systems without
  magical intervention.

#3: Avoid Knobs on Knobs
------------------------

A "knob" is a replaceable component in a framework or library.

When a replaceable component itself offers a knob, this is the "knobs on
knobs" pattern.

Pyramid Authn Policy
--------------------

From ``pyramid``, the use of an authentication policy knob on knob:

.. sourcecode:: python

   # ... imports elided ...

   GROUPS = {'fred':['editors']}

   def groupfinder(userid, request):
       return GROUPS.get(userid)

   pol = AuthTktAuthenticationPolicy(callback=groupfinder)
   config = Configurator()
   config.set_authentication_policy(pol)

Why Is This Bad?
----------------

- We're actually dealing with two separate frameworks.

- Pyramid ``Configurator.set_authentication_policy`` accepts an authentication
  policy.

- ``AuthTktAuthenticationPolicy``, an authentication policy, is itself a
  miniframework, that accepts a callback.

- People don't understand when or why to replace "the big thing" when there's
  a "little thing" inside the big thing that's also replaceable.

.. class:: handout

   There's the Pyramid configurator ``set_authentication_policy`` method, which
   accepts something that adheres to the "authentication policy interface"
   (the interface requires a number of methods).  AuthTktAuthenticationPolicy
   implements this interface.

   But AuthTktAuthenticationPolicy is also its own mini-framework, accepting a
   ``callback`` constructor argument, which must be a callable that accepts a
   userid and a request, and which must return a sequence of groups.

   This was done with the intent of avoiding documentation that tells people to
   subclass AuthTktAuthenticationPolicy, preferring to tell them to compose
   something together by passing a callback function to the policy's
   constructor.

Solution
--------

Remove or hide a knob.

Would probably be less confusing and more straightforward in this case to tell
folks to subclass AuthTktAuthenticationPolicy and override e.g. a
``find_groups`` method in the subclass instead of passing in a callback.

#4: Composing>Inheriting
------------------------

Offering up superclasses "from on high" in a library or framework is often a
bad idea.

Composition *usually* beats inheritance (although not always).

The Yo-Yo Problem
------------------

- http://en.wikipedia.org/wiki/Yo-yo_problem

" ... occurs when  a programmer has to read and  understand a program whose
inheritance graph  is so long  and complicated  that the programmer  has to
keep flipping between  many different class definitions in  order to follow
the control flow of the program..."

Yo-Yo Problem (Cont'd)
----------------------

Almost every Zope object visible from the ZMI inherits from this base class:

.. sourcecode:: python

   class Item(Base,
              Resource,
              CopySource,
              Tabs,
              Traversable,
              Owned,
              UndoSupport,
              ):
       """A common base class for simple, non-container 
          objects."""

Codependency
------------

- The "specialization interface" of a superclass can be hard to document and
  it's very easy to get wrong.

- Encapsulation is rarely honored when inheritance is used, so changes to a
  parent class will almost always break some number of existing subclasses
  whose implementers weren't paying attention to the specialization interface
  when they originally inherited from your library's superclass.

.. class:: handout

   The superclass may start simple, initially created to handle one or two
   particular cases of reuse via inheritance, but over time, as more folks add
   to its specialization interface, it will need to do more delegation, and may
   be required to become very abstract.

   When the superclass reaches a high level of abstraction, it may not be
   obvious what the purpose of the class is or why it's implemented as it is.
   A potential maintainer of the superclass may need to gain a detailed
   understanding of the implementation of in-the-wild subclasses in order to
   change the superclass.  This can scare off potential contributors.

Codependency (Cont'd)
---------------------

- The superclass may assume a particular state outcome from a combination of
  method calls.  The expected outcome of such an operation is hard to explain
  and difficult for a subclass to enforce.  It may need to change over time,
  breaking existing subclasses in hard-to-predict ways.

- Subclasses may unknowingly coopt and change the meaning of superclass
  instance or class variables.

Smells
------

From "Inheritance Considered Harmful" on http://www.midmarsh.co.uk

- Subclasses which override methods used by other inherited methods.

- A subclass which extends inherited methods using ``super``.  Other
  inherited methods may rely on the extended method.

- Subclass which uses or changes the state of "private" instance variables or
  calls/overrides methods not part of the specialization interface.

.. class:: handout

   [1] Which are thus reliant on the behaviour and results of the overridden
   methods.

Alternatives to Inheritance
---------------------------

Composition

Event systems

Composition
------------

- Instead of telling folks to override a method of a library superclass via
  inheritance, you can tell them to pass in a component object to a library
  class constructor.

- The interaction between a component and your library code is "composition".

- When a library or framework uses a component, the only dependency between
  the library code and the component is the component's interface.

.. class:: handout

   A component represents the custom logic that would have otherwise gone in a
   method of a subclass.

   The library code will only have visibility into the component via its
   interface.  The component needn't have any visibility into the library code
   at all (but often does).

   It's less likely that a component author will rely on non-API implementation
   details of the library than it would be if he was required to subclass a
   library parent class.  The potential distraction of the ability to customize
   every aspect of the behavior of the system by overriding methods is removed.

   A clear contract makes it feasible to change the implementation of both the
   library and the component with reduced fear of breaking an integration of
   the two.

Inheritance Example
-------------------

Here's an example of providing a class built to be specialized via
inheritance:

.. sourcecode:: python

   class TVRemote(object):
       def __init__(self):
           self.channel = 0

       def increment_channel(self):
           self.channel += 1

       def click(self, button_name):
           raise NotImplementedError

Composition Ex. (Cont'd)
------------------------

Here's an example of using the TVRemote class:

.. sourcecode:: python

   from tv import TVRemote

   class MyRemote(TVRemote):
       def click(self, button_name):
           if button_name == 'blue':
               self.increment_channel()

   remote = MyRemote()
   remote.click('blue')

Composition Ex. (Cont'd)
------------------------

Here's an example of a library class built to be specialized via composition
instead of inheritance:

.. sourcecode:: python

   class TVRemote(object):
       def __init__(self, buttons):
           self.channel = 0
           self.buttons = buttons

       def increment_channel(self):
           self.channel += 1

       def click(self, button_name):
           self.buttons.click(self, button_name)

Composition Ex. (Cont'd)
------------------------

Here's an example of someone using the library class we built for
composition:

.. sourcecode:: python

   from tv import TVRemote

   class Buttons(object):
       def click(self, remote, button_name):
           if button_name == 'blue':
               remote.increment_channel()

   buttons = Buttons()
   remote = TVRemote(buttons)
   remote.click('blue')

Composition (Cont'd)
---------------------

Composition is "take it or leave it" customizability.  It's a good choice when
a problem and interaction is well-defined and well-understood (and, if you're
writing a library for other people to use, this should, by definition, be
true).  But it can be limiting in requirements-sparse environments where the
problem is not yet well-defined or well-understood.

.. class:: handout

   It can be easier to use inheritance in a system where you control the
   horizontal and vertical while you're working out exactly what the
   relationship between objects should be.  If you control the horizontal and
   vertical, you can always later switch from inheritance to composition once
   the problem is fully understood and people begin to want to reuse your code.

Event Systems
-------------

- Specialized kind of composition.

- For example, instead of adding a ``on_modification`` method of a class, and
  requiring that people subclass the class to override the method, have the
  would-be-superclass send an event to an event system.  The event system can
  be subscribed to by system extenders as necessary.

Event Systems (Cont'd)
-----------------------

- This is more flexible than subclassing too, because there's more than one
  entry point to extending behavior: an event can be subscribed to by any
  number of prospective listeners instead of just one.

- But systems reliant on event handling can be a bitch to understand and debug
  due to action-at-a-distance.

Event System Example
--------------------

.. sourcecode:: python

   class ButtonPress(object):
        def __init__(self, remote, bname)
            self.remote = remote
            self.bname = bname
   class TVRemote(object):
        def __init__(self, event_system):
            self.channel = 0
            self.event_system = event_system
        def click(self, bname):
            self.event_system.notify(ButtonPress(self, bname))
   event_system = EventSystem()
   def subscriber(event):
       if event.bname == 'blue': event.remote.increment_channel()
   event_system.subscribe(ButtonPress, subscriber)
   remote = TVRemote(event_system)
   remote.click('blue')

When To Offer Superclass
------------------------

When the behavior is absolutely fundamental to the spirit and intent of the
library or framework (e.g. ZODB's ``Persistent``).  Parent classes offered as
slight variations on a theme (e.g. Django class-based views shipped as
niceties) are not fundamental.

A superclass offered by your library should almost always be abstract.

Composition is harder for people to wrap their brains around.

.. class:: handout

   When a user inherits from a concrete parent class, he's usually inheriting
   from something that you haven't really designed for specialization, and it's
   likely that neither you nor he will be completely clear on what the
   specialization interface actually is.  High likelihood for future breakage.

   I wish I had used inheritance in the case of an AuthTktAuthenticationPolicy
   instead of composition because I would have had to answer fewer questions
   about it.  Python programmers will always understand the mechanics of
   inheritance better than whatever composition API you provide.

Guidelines
----------

#1: Global State is Precious

#2: Don't Design Exclusively For Convenience

#3: Avoid Knobs on Knobs

#4: Composition Usually Beats Inheritance

Contact Info
------------

Chris McDonough, Agendaless Consulting

@chrismcdonough on Twitter

"mcdonc" on Freenode IRC
