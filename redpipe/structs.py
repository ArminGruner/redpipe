# -*- coding: utf-8 -*-
"""
The Struct is a convenient way to access data in a hash.
Makes it possible to load data from redis as an object and access the fields.
Then store changes back into redis.
"""
from six import add_metaclass
from json.encoder import JSONEncoder
from functools import wraps
from .pipelines import autoexec
from .keyspaces import Hash
from .fields import TextField
from .exceptions import InvalidOperation
from .futures import Future, IS

__all__ = ['Struct']


class StructMeta(type):
    """
    Data binding of a redpipe.Hash to the core of the Struct object.
    Creates it dynamically on class construction.
    uses the keyspace and connection fields
    Meta Classes are strange beasts.
    """

    def __new__(mcs, name, bases, d):
        if name in ['Struct']:
            return type.__new__(mcs, name, bases, d)

        class StructHash(Hash):
            keyspace = d.get('keyspace', name)
            connection = d.get('connection', None)
            fields = d.get('fields', {})
            keyparse = d.get('keyparse', TextField)
            valueparse = d.get('valueparse', TextField)
            memberparse = d.get('memberparse', TextField)

        d['core'] = StructHash

        return type.__new__(mcs, name, bases, d)


@add_metaclass(StructMeta)
class Struct(object):
    """
    load and store structured data in redis using OOP patterns.

    If you pass in a dictionary-like object, redpipe will write all the
    values you pass in to redis to the key you specify.

    By default, the primary key name is `_key`.
    But you should override this in your Struct with the `key_name`
    property.

    .. code-block:: python

        class Beer(redpipe.Struct):
            fields = {'name': redpipe.StringField}
            key_name = 'beer_id'

        beer = Beer({'beer_id': '1', 'name': 'Schlitz'})

    This will store the data you pass into redis.
    It will also load any additional fields to hydrate the object.
    **RedPipe** does this in the same pipelined call.

    If you need a stub record that neither loads or saves data, do:

    .. code-block:: python

        beer = Beer({'beer_id': '1'}, no_op=True)

    You can later load the fields you want using, load.

    If you pass in a string we assume it is the key of the record.
    redpipe loads the data from redis:

    .. code-block:: python

        beer = Beer('1')
        assert(beer['beer_id'] == '1')
        assert(beer['name'] == 'Schlitz')

    If you need to load a record but only specific fields, you can say so.

    .. code-block:: python

        beer = Beer('1', fields=['name'])

    This will exclude all other fields.

    **RedPipe** cares about pipelining and efficiency, so if you need to
    bundle a bunch of reads or writes together, by all means do so!

    .. code-block:: python

        beer_ids = ['1', '2', '3']
        with redpipe.pipeline() as pipe:
            beers = [Beer(i, pipe=pipe) for i in beer_ids]
        print(beers)

    This will pipeline all 3 together and load them in a single pass
    from redis.

    The following methods all accept a pipe:

    * __init__
    * update
    * incr
    * decr
    * pop
    * remove
    * clear
    * delete

    You can pass a pipeline into them to make sure that the network i/o is
    combined with another pipeline operation.
    The other methods on the object are about accessing the data
    already loaded.
    So you shouldn't need to pipeline them.

    """
    __slots__ = ['key', '_data']
    keyspace = None
    connection = None
    key_name = '_key'
    fields = {}
    default_fields = 'all'  # set as 'defined', 'all', or ['a', b', 'c']

    def __init__(self, _key_or_data=None, pipe=None, fields=None, no_op=False):
        """
        class constructor

        :param _key_or_data:
        :param pipe:
        :param fields:
        """
        keyname = self.key_name
        self._data = {}
        with self._pipe(pipe=pipe) as pipe:
            try:
                coerced = dict(_key_or_data)
                self.key = coerced[keyname]
                del coerced[keyname]
                if no_op:
                    self._data = coerced
                    return

                self.update(coerced, pipe=pipe)
            except KeyError:
                raise InvalidOperation(
                    'must specify primary key when cloning a struct')
            except (ValueError, TypeError):
                self.key = _key_or_data

            if not no_op:
                self.load(fields=fields, pipe=pipe)

    def load(self, fields=None, pipe=None):
        """
        Load data from redis.
        restrict to just the fields specified.

        :param fields: 'all', 'defined', or array of field names
        :param pipe: Pipeline(), NestedPipeline() or None
        :return: None
        """
        if fields is None:
            fields = self.default_fields

        if fields == 'all':
            return self._load_all(pipe=pipe)

        if fields == 'defined':
            fields = [k for k in self.fields.keys()]

        if not fields:
            return

        with self._pipe(pipe) as pipe:
            ref = self.core(pipe=pipe).hmget(self.key, fields)

            def cb():
                for i, v in enumerate(ref.result):
                    k = fields[i]
                    if k != self.key_name:
                        self._data[k] = v

            pipe.on_execute(cb)

    def _load_all(self, pipe=None):
        with self._pipe(pipe) as pipe:
            ref = self.core(pipe=pipe).hgetall(self.key)

            def cb():
                if not ref.result:
                    return

                for k, v in ref.result.items():
                    if k != self.key_name:
                        self._data[k] = v

            pipe.on_execute(cb)

    def incr(self, field, amount=1, pipe=None):
        """
        Increment a field by a given amount.
        Return the future

        Also update the field.

        :param field:
        :param amount:
        :param pipe:
        :return:
        """
        with self._pipe(pipe) as pipe:
            core = self.core(pipe=pipe)
            new_amount = core.hincrby(self.key, field, amount)
            ref = core.hget(self.key, field)

            def cb():
                self._data[field] = ref.result

            pipe.on_execute(cb)
            return new_amount

    def decr(self, field, amount=1, pipe=None):
        """
        Inverse of incr function.

        :param field:
        :param amount:
        :param pipe:
        :return: Pipeline, NestedPipeline, or None
        """
        return self.incr(field, amount * -1, pipe=pipe)

    def update(self, changes, pipe=None):
        """
        update the data in the Struct.

        This will update the values in the underlying redis hash.
        After the pipeline executes, the changes will be reflected here
        in the local struct.

        If any values in the changes dict are None, those fields will be
        removed from redis and the instance.

        The changes should be a dictionary representing the fields to change
        and the values to change them to.

        :param changes: dict
        :param pipe: Pipeline, NestedPipeline, or None
        :return: None
        """
        if not changes:
            return

        if self.key_name in changes:
            raise InvalidOperation('cannot update the redis key')

        deletes = {k for k, v in changes.items() if IS(v, None)}
        updates = {k: v for k, v in changes.items() if k not in deletes}

        with self._pipe(pipe) as pipe:

            core = self.core(pipe=pipe)

            def build(k, v):
                core.hset(self.key, k, v)

                def cb():
                    self._data[k] = v

                pipe.on_execute(cb)

            for k, v in updates.items():
                build(k, v)

            self.remove(deletes, pipe=pipe)

    def remove(self, fields, pipe=None):
        """
        remove some fields from the struct.
        This will remove data from the underlying redis hash object.
        After the pipe executes successfully, it will also remove it from
        the current instance of Struct.

        :param fields: list or iterable, names of the fields to remove.
        :param pipe: Pipeline, NestedPipeline, or None
        :return: None
        """
        if not fields:
            return

        if self.key_name in fields:
            raise InvalidOperation('cannot remove the redis key')

        with self._pipe(pipe) as pipe:
            core = self.core(pipe=pipe)
            core.hdel(self.key, *fields)

            def cb():
                for k in fields:
                    try:
                        del self._data[k]
                    except KeyError:
                        pass

            pipe.on_execute(cb)

    def copy(self):
        """
        like the dictionary copy method.

        :return:
        """
        return self.__class__(dict(self))

    @property
    def persisted(self):
        """
        Not certain I want to keep this around.
        Is it useful?

        :return:
        """
        return True if self._data else False

    def clear(self, pipe=None):
        """
        delete the current redis key.

        :param pipe:
        :return:
        """
        with self._pipe(pipe) as pipe:
            self.core(pipe=pipe).delete(self.key)

            def cb():
                self._data = {}

            pipe.on_execute(cb)

    def get(self, item, default=None):
        """
        works like the dict get method.

        :param item:
        :param default:
        :return:
        """
        return self._data.get(item, default)

    def pop(self, name, default=None, pipe=None):
        """
        works like the dictionary pop method.

        IMPORTANT!

        This method removes the key from redis.
        If this is not the behavior you want, first convert your
        Struct data to a dict.

        :param name:
        :param default:
        :param pipe:
        :return:
        """
        f = Future()
        with self._pipe(pipe) as pipe:
            c = self.core(pipe)
            ref = c.hget(self.key, name)
            c.hdel(self.key, name)

            def cb():
                f.set(default if ref.result is None else ref.result)
                self._data.pop(name)

            pipe.on_execute(cb)

        return f

    @classmethod
    def delete(cls, keys, pipe=None):
        """
        Delete one or more keys from the Struct namespace.

        This is a class method and unlike the `clear` method,
        can be invoked without instantiating a Struct.

        :param keys: the names of the keys to remove from the keyspace
        :param pipe: Pipeline, NestedPipeline, or None
        :return: None
        """
        with cls._pipe(pipe) as pipe:
            core = cls.core(pipe)
            core.delete(*keys)

    @classmethod
    def _pipe(cls, pipe=None):
        return autoexec(pipe, name=cls.connection)

    def __getitem__(self, item):
        if item == self.key_name:
            return self.key

        return self._data[item]

    def __delitem__(self, key):
        tpl = 'cannot delete %s from %s indirectly. Use the delete method.'
        raise InvalidOperation(tpl % (key, self))

    def __setitem__(self, key, value):
        tpl = 'cannot set %s key on %s indirectly. Use the set method.'
        raise InvalidOperation(tpl % (key, self))

    def __iter__(self):
        for k in self.keys():
            yield k

    def __len__(self):
        return len(dict(self))

    def __contains__(self, item):
        if item == self.key_name:
            return True
        return item in self._data

    def iteritems(self):
        yield self.key_name, self.key
        for k, v in self._data.items():
            yield k, v

    def items(self):
        return [row for row in self.iteritems()]

    def __eq__(self, other):
        if self is other:
            return True
        try:
            if dict(self) == dict(other):
                return True
        except (TypeError, ValueError):
            pass

        return False

    def keys(self):
        return [row[0] for row in self.items()]

    def __str__(self):
        return "<%s:%s>" % (self.__class__.__name__, self.key)

    def __repr__(self):
        return repr(dict(self))

    def __getstate__(self):
        return self.key, self._data,

    def __setstate__(self, state):
        self.key = state[0]
        self._data = state[1]

    @property
    def _redpipe_struct_as_dict(self):
        return dict(self)


def _json_default_encoder(func):
    """
    Monkey-Patch the core json encoder library.
    This isn't as bad as it sounds.
    We override the default method so that if an object
    falls through and can't be encoded normally, we see if it is
    a Future object and return the result to be encoded.

    I set a special attribute on the Struct object so I can tell
    that's what it is.

    If that doesn't work, I fall back to the earlier behavior.
    The nice thing about patching the library this way is that it
    won't inerfere with existing code and it can itself be wrapped
    by other methods.

    So it's very extensible.

    :param func: the JSONEncoder.default method.
    :return: an object that can be json serialized.
    """

    @wraps(func)
    def inner(self, o):
        try:
            return o._redpipe_struct_as_dict  # noqa
        except AttributeError:
            pass
        return func(self, o)

    return inner


JSONEncoder.default = _json_default_encoder(JSONEncoder.default)
