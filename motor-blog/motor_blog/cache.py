"""Manage in-memory cache of some data from Mongo, tail an 'events'
   capped collection to know when to invalidate
"""

import copy
import functools
import logging
import sys
import datetime

from tornado import gen

import pymongo.errors
from tornado.concurrent import Future
from tornado.ioloop import IOLoop


_cache = {}
_callbacks = {}
_db = None


@gen.coroutine
def create_events_collection(db):
    """Create capped collection.

    Pass in a MotorDatabase.
    """
    try:
        # Size is in bytes; event documents are rare and very small
        yield db.create_collection('events', size=100 * 1024, capped=True)
        logging.info(
            'Created capped collection "events" in database "%s"' % db.name)
    except pymongo.errors.CollectionInvalid:
        # Collection already exists
        collection_options = yield db.events.options()
        if 'capped' not in collection_options:
            logging.error(
                '%s.events exists and is not a capped collection,\n'
                'please drop the collection and start this app again.' %
                db.name)

            sys.exit(1)


def on(event_name, callback):
    """Register for event notification.

    If `event_name` is None, callback is run for all events.
    """
    _callbacks.setdefault(event_name, set()).add(callback)


def remove_callback(event_name, callback):
    """Unregister. Raises ValueError if not already registered"""
    _callbacks.get(event_name, set()).discard(callback)


@gen.coroutine
def event(name):
    """Insert event into events collection.

    Returns a Future. Yield it to wait until listeners have responded to the
    event.
    """
    assert _db, "Call cache.startup() once before calling event()."
    # event() is expected to be very rare -- e.g., called from
    # wp_newCategory. If it becomes more common, this will need work.
    future = Future()

    # Ensure future isn't resolved until after other listeners.
    def event_listener(_):
        # Unregister this function.
        remove_callback(name, event_listener)
        IOLoop.instance().add_callback(
            functools.partial(future.set_result, None))

    on(name, event_listener)

    yield _db.events.insert(
        {'ts': datetime.datetime.utcnow(), 'name': name},
        manipulate=False)  # No need to add _id


def cached(key, invalidate_event):
    """
    Caching decorator, invalidated when an event is inserted into `events`
    collection with a certain name.

    :Parameters:
        - `key`: Cache key. For now, caching does not depend on arguments to
           the function.
        - `invalidate_event`: Clear the cache when this event occurs.
    """
    def invalidate(event):
        _cache.pop(key, None)

    on(invalidate_event, invalidate)

    def _cached(fn):
        @gen.coroutine
        def maybecall(*args, **kwargs):
            if key in _cache:
                raise gen.Return(_cache[key])
            else:
                result = yield fn(*args, **kwargs)
                _cache[key] = result
                raise gen.Return(result)

        return maybecall
    return _cached


@gen.coroutine
def startup(db):
    global _db
    if _db:
        # Already started.
        return

    _db = db
    yield create_events_collection(db)

    # Typically the global loop, but it's a different loop in tests.
    loop = db.get_io_loop()

    @gen.coroutine
    def tail():
        collection = db.events
        now = datetime.datetime.utcnow()
        last_event_ts = None

        def make_cursor():
            return collection.find(
                {'ts': {'$gte': last_event_ts or now}},
                tailable=True, await_data=True)

        cursor = make_cursor()

        while True:
            if not cursor.alive:
                # While collection is empty, tailable cursor dies immediately.
                yield gen.Task(loop.add_timeout, datetime.timedelta(seconds=1))
                logging.debug('new cursor, last_event_ts = %s, now = %s',
                              last_event_ts, now)
                cursor = make_cursor()

            try:
                while (yield cursor.fetch_next):
                    event = cursor.next_object()
                    logging.info(
                        "Event: %r, %s", event.get('name'), event.get('ts'))

                    _on_event(event)
                    last_event_ts = event.get('ts')
            except pymongo.errors.OperationFailure:
                # Collection dropped?
                logging.exception('Tailing "events" collection.')
                yield gen.Task(loop.add_timeout, datetime.timedelta(seconds=1))
                logging.error(
                    'Resuming tailing "events" collection.'
                    ' Last_event_ts = %s, now = %s',
                    last_event_ts, now)

                cursor = make_cursor()

            except Exception:
                logging.exception('Tailing "events" collection.')
                return  # Give up

    # Start infinite loop
    tail()


def shutdown():
    global _db
    _db = None


def _on_event(event):
    # Get callbacks for this event, and those registered with event_name None.
    # Copy, since callbacks themselves may add / remove callbacks.
    callbacks = copy.copy(_callbacks.get(event['name'], set()))
    callbacks.update(_callbacks.get(None, set()))

    for callback in callbacks:
        try:
            callback(event)
        except Exception:
            logging.exception('Processing event %s' % event)
