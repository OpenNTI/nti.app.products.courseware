#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from datetime import datetime

from zope import interface
from zope import component

from zope.cachedescriptors.property import Lazy

from nti.app.products.courseware.interfaces import IAvailableCoursesProvider

from nti.appserver.workspaces.interfaces import IFeaturedCatalogCollectionProvider
from nti.appserver.workspaces.interfaces import IPurchasedCatalogCollectionProvider

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_enrollments

from nti.dataserver.authorization import ACT_READ

from nti.dataserver.authorization_acl import has_permission

from nti.dataserver.interfaces import IUser


@component.adapter(IUser)
@interface.implementer(IAvailableCoursesProvider)
class AvailableCoursesProvider(object):
    """
    A utility to fetch available courses for a user.
    """

    def __init__(self, user):
        self.user = user

    @property
    def catalog(self):
        return component.getUtility(ICourseCatalog)

    def get_available_entries(self):
        """
        Return a sequence of :class:`ICourseCatalogEntry` objects the user is
        not enrolled in and that are available to be enrolled in.
        """
        # To support ACLs limiting the available parts of the catalog, we
        # filter out here. we could do this with a proxy, but it's easier right
        # now just to copy. This is highly dependent on implementation. We also
        # filter out sibling courses when we are already enrolled in one; this
        # is probably inefficient.
        result = dict()
        my_enrollments = {}
        for x in self.catalog.iterCatalogEntries():
            if has_permission(ACT_READ, x, self.user):
                # Note that we have to expose these by NTIID, not their
                # __name__. Because the catalog can be reading from
                # multiple different sources, the __names__ might overlap
                course = ICourseInstance(x, None)
                if course is not None:
                    enrollments = ICourseEnrollments(course)
                    if enrollments.get_enrollment_for_principal(self.user) is not None:
                        my_enrollments[x.ntiid] = course
                result[x.ntiid] = x
        courses_to_remove = []
        for course in my_enrollments.values():
            if ICourseSubInstance.providedBy(course):
                # Look for parents and siblings to remove
                # XXX: Too much knowledge
                courses_to_remove.extend(course.__parent__.values())
                courses_to_remove.append(course.__parent__.__parent__)
            else:
                # Look for children to remove
                courses_to_remove.extend(course.SubInstances.values())

        for course in courses_to_remove:
            ntiid = ICourseCatalogEntry(course).ntiid
            if ntiid not in my_enrollments:
                result.pop(ntiid, None)
        return result.values()


@component.adapter(IUser)
@interface.implementer(IFeaturedCatalogCollectionProvider)
class FeaturedCatalogCoursesProvider(object):
    """
    Returns 'featured' :class:`ICourseCatalogEntry' objects, defined as
    current and upcoming courses.
    """

    def __init__(self, user):
        self.user = user

    @Lazy
    def now(self):
        return datetime.utcnow()

    def _sort_key(self, entry):
        start_date = entry.StartDate
        return (start_date is not None, start_date)

    @property
    def available_entries(self):
        # XXX: Encapsulate this date filtering logic in the provider for reuse
        course_provider = IAvailableCoursesProvider(self.user)
        return course_provider.get_available_entries()

    # XXX: copied from some catalog views
    def _is_entry_current(self, entry):
        now = self.now
        return  (entry.StartDate is None or now > entry.StartDate) \
            and (entry.EndDate is None or now < entry.EndDate)

    def _is_entry_upcoming(self, entry):
        return entry.StartDate is not None and self.now < entry.StartDate

    def include_filter(self, entry):
        return self._is_entry_current(entry) \
            or self._is_entry_upcoming(entry)

    def get_collection_iter(self, unused_filter_string=None):
        """
        Returns an iterable over this collection provider, optionally
        filtering on the given string.

        TODO: filtering
        TODO: caller sorting
        """
        entries = (
            x for x in self.available_entries if self.include_filter(x)
        )
        # Most recent first
        result = sorted(entries, key=self._sort_key)
        return result


@component.adapter(IUser)
@interface.implementer(IPurchasedCatalogCollectionProvider)
class PurchasedCatalogCoursesProvider(object):
    """
    Returns 'purchased' objects, defined as any enrollment for this user.
    """

    def __init__(self, user):
        self.user = user

    def _sort_key(self, record):
        return record.createdTime

    @property
    def enrollments(self):
        return get_enrollments(self.user)

    def get_collection_iter(self, unused_filter_string=None):
        """
        Returns an iterable over this collection provider, optionally
        filtering on the given string.

        TODO: filtering
        """
        # Most recent first
        result = sorted(self.enrollments, key=self._sort_key, reverse=True)
        return result


import zope.deferredimport
zope.deferredimport.initialize()

zope.deferredimport.deprecatedFrom(
    "moved to nti.contenttypes.courses",
    "nti.contenttypes.courses.catalog",
    "CourseCatalog",
    "CourseCatalogInstructorInfo",
    "CourseCatalogEntry")
