#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Implementation of course activity.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import time

from BTrees import family64
from BTrees.Length import Length

from persistent import Persistent

from zope import component
from zope import interface

from zope.annotation import factory as an_factory

from zope.cachedescriptors.property import Lazy
from zope.cachedescriptors.property import CachedProperty

from zope.intid.interfaces import IIntIds

from nti.app.products.courseware.interfaces import ICourseInstanceActivity

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import ACE_DENY_ALL

from nti.zodb.containers import bit64_int_to_time
from nti.zodb.containers import time_to_64bit_int

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance)
@interface.implementer(ICourseInstanceActivity)
class _DefaultCourseActivity(Persistent):
    """
    Default activity storage.

    Our strategy, to minimize overhead, is to store the activity
    sorted by timestamp and by reference to intid.
    """

    family = family64

    __name__ = None
    __parent__ = None

    createdTime = 0  # pretty useless, here for ILastModified

    def __init__(self):
        pass

    def __acl__(self):
        # We want to get everything from the role map
        return (ACE_DENY_ALL,)

    @Lazy
    def _storage(self):
        storage = self.family.II.BTree()
        self._p_changed = True  # pylint: disable=attribute-defined-outside-init
        return storage

    @Lazy
    def _DefaultCourseActivity__len(self):
        l = Length()
        ol = len(self._storage)
        if ol > 0:
            l.change(ol)
        self._p_changed = True  # pylint: disable=attribute-defined-outside-init
        return l

    @CachedProperty
    def _intids(self):
        return component.getUtility(IIntIds)

    def __len__(self):
        return self.__len()

    @property
    def lastModified(self):
        if len(self):
            # pylint: disable=no-member
            return bit64_int_to_time(-self._storage.minKey())
        return 0

    def append(self, activity):
        # pylint: disable=no-member
        value = self._intids.getId(activity)
        # Time is increasing, but we want
        # our default sort order to be descending, so we
        # negate the key
        key = -time_to_64bit_int(time.time())

        # We do a poor job of probing to find a free time so as not to
        # overwrite
        # pylint: disable=unsupported-membership-test
        while key in self._storage:
            key -= 1

        # pylint: disable=unsupported-assignment-operation
        l = self.__len  # must capture pre-state
        self._storage[key] = value
        l.change(1)

    def remove(self, activity):
        # pylint: disable=no-member
        value = self._intids.getId(activity)
        keys = []
        # This might be a use case for byValue?
        for k, v in list(self._storage.items()):
            if v == value:
                keys.append(k)
        if not keys:
            return

        l = self.__len
        for k in keys:
            del self._storage[k]  # pylint: disable=unsupported-delete-operation
        l.change(-len(keys))

    def items(self, min=None, max=None, excludemin=False, excludemax=False):
        # pylint: disable=no-member
        intids = self._intids
        min = time_to_64bit_int(min) if min is not None else None
        max = time_to_64bit_int(max) if max is not None else None
        for key, value in self._storage.items(min, max,
                                              excludemin=excludemin,
                                              excludemax=excludemax):
            key = -key
            when = bit64_int_to_time(key)
            activity = intids.queryObject(value)  # account for deletions

            # Even if the activity object has gone missing, still
            # yield None to be consistent with __len__
            yield when, activity

    def trim(self):
        # pylint: disable=no-member
        removed = 0
        intids = self._intids
        for key, value in list(self._storage.items()):
            activity = intids.queryObject(value)
            if activity is None:
                removed += 1
                del self._storage[key]  # pylint: disable=unsupported-delete-operation
        # reset length
        if removed:
            l = self.__len
            l.change(-removed)
        return removed


_DefaultCourseActivityFactory = an_factory(_DefaultCourseActivity,
                                           u'CourseActivity')
