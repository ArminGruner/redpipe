Release Notes
=============

Releases prior to **1.0.0** are considered beta.
The api is not officially supported.
We make no guarantees about backward compatibility.

Once the api reaches **1.0.0**, all major and minor release notes will be well documented.
Upgrade notes and any breaking changes will be described here and how to handle them.

0.5.0 (May 5, 2017)
-------------------
More breaking changes to Struct.
Solidifying the api.
Making important simplifications.
This will make it easier to explain and document.

* Struct and Keyspace: simplifying some variable names
* Struct: support a no_op flag to prevent read/write from redis
* Struct: no kwargs as properties of struct. a dict models it better
* Struct: specify fields to load when instantiating
* Struct: reuse remove logic in the update function for elements set to None
* Simplifying task wait and promise to use the TaskManager directly
* Future: better isinstance and is comparison checks
* make it easier to build docs
* adding Docker support for testing many versions of python


0.4.0 (May 4, 2017)
-------------------
* by default, don't use transactions
* autocommit flag renamed to autoexec. *Breaking change*.
* support pickling Struct
* make repr(Struct) more standard
* cleaner connection and pipeline interfaces
* verify redis cluster support with a single-node redis cluster via redislite

0.3.2 (May 3, 2017)
-------------------
After experimenting with some things, simplifying Struct back down.
Some of the methods in Struct will break.
Easier to explain with fewer methods and can still do everything I need to.

* cleaner support for items and iteritems in struct
* support for delete in struct
* fixed a bug with deleting multiple keys in Keyspace objects.
* simplification on json serialization detection
* test flake8 on travis
* test with hiredis

This release also improves the documentation on Struct.
I hadn't bothered much up until this point.
The interface was still solidifying.
Starting to get to a stable place there.

0.3.1 (May 2, 2017)
-------------------
Breaking changes in this release as well.
Can only access data from a struct object like you would a dictionary.
This is an important step because it disambiguates commands from data.
And it enforces one consistent way to access data.
All the methods on the `Struct` give it a dictionary interface.
Easier to explain the mental model this way.

* Improvements to `redpipe.Struct`.
* Documentation improvements.


0.3.0 (April 30, 2017)
----------------------
BIG REFACTOR.
key no longer part of the constructor of Keyspace objects.
Instead, you pass the key name to the method.
This keeps the api identical in arguments in redis-py.
It also allows me to support multi-key operations.
This is a breaking change.

* no need for a compat layer, using six
* standardize key, value, member encoding & decoding by reusing Field interface
* key no longer part of the constructor of Keyspace objects


0.2.5 (April 30, 2017)
----------------------
* support for binary field
* improving encoding and decoding in Keyspaces
* alias iteritems to items on struct
* make fields use duck-typing to validate instead of using isinstance


0.2.4 (April 28, 2017)
----------------------
* better interface for async enable/disable.
* add ability to talk to multiple redis servers in parallel via threads


0.2.3 (April 27, 2017)
----------------------
* renaming datatypes to keyspaces. easier to explain.
* moving documentation from readme into docs/ for readthedocs.
* support for ascii field


0.2.2 (April 26, 2017)
----------------------
* better support and testing of redis cluster
* support for hyperloglog data type
* adding support for more complex field types
* support sortedset lex commands
* support for scanning


0.2.1 (April 24, 2017)
----------------------
* bug fix: make sure accessing result before ready results in a consistent exception type.
* bug fix: issue when exiting with statement from python cli


0.2.0 (April 24, 2017)
----------------------
* make the deferred object imitate the underlying result


0.1.1 (April 23, 2017)
----------------------
* make it possible to typecast fields in the Hash data type
* better support for utf-8
* make result object traceback cleaner

0.1.0 (April 21, 2017)
----------------------

* better pipelining and task management
* better support for multi pipeline use case


Earlier Releases
----------------
Releases less than **0.1.0** in this project are considered early alpha and don't deserve special mention.
