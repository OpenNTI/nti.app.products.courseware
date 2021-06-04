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

from zope.intid.interfaces import IIntIds

from nti.app.products.courseware.interfaces import IAvailableCoursesProvider

from nti.appserver.workspaces.interfaces import IFeaturedCatalogCollectionProvider
from nti.appserver.workspaces.interfaces import IPurchasedCatalogCollectionProvider

from nti.contenttypes.courses.index import get_courses_catalog

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import IDeletedCourse
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseCatalogEntryFilterUtility

from nti.contenttypes.courses.utils import get_enrollments
from nti.contenttypes.courses.utils import get_all_site_entry_intids

from nti.dataserver.authorization import ACT_READ

from nti.dataserver.authorization import is_admin_or_site_admin

from nti.dataserver.authorization_acl import has_permission

from nti.dataserver.interfaces import IUser


@interface.implementer(IAvailableCoursesProvider)
class AvailableCoursesProvider(object):
    """
    A utility to fetch available courses for a principal.
    """

    def __init__(self, principal):
        self.principal = principal

    @property
    def catalog(self):
        return component.getUtility(ICourseCatalog)

    @Lazy
    def enrolled_entry_ntiid_to_course(self):
        enrolled_courses = (x.CourseInstance for x in get_enrollments(self.principal))
        result = {ICourseCatalogEntry(x).ntiid: x for x in enrolled_courses}
        return result

    @Lazy
    def _courses_to_exclude(self):
        """
        Filter out sibling courses when we are already enrolled in one; this
        is probably inefficient.
        """
        courses_to_remove = set()
        for course in self.enrolled_entry_ntiid_to_course.values():
            if ICourseSubInstance.providedBy(course):
                # Look for parents and siblings to remove
                # XXX: Too much knowledge
                courses_to_remove.update(course.__parent__.values())
                courses_to_remove.add(course.__parent__.__parent__)
            else:
                # Look for children to remove
                courses_to_remove.update(course.SubInstances.values())
        return courses_to_remove

    def get_available_entries(self):
        """
        Return a sequence of :class:`ICourseCatalogEntry` objects the principal is
        not enrolled in and that are available to be enrolled in. We also include
        the entries of the courses the principal is enrolled in.
        """
        # To support ACLs limiting the available parts of the catalog, we
        # filter out here. we could do this with a proxy, but it's easier right
        # now just to copy. This is highly dependent on implementation.
        courses_to_remove = self._courses_to_exclude
        result = []
        for x in self.catalog.iterCatalogEntries():
            if x.ntiid in self.enrolled_entry_ntiid_to_course:
                result.append(x)
            elif ICourseInstance(x, None) in courses_to_remove:
                pass
            elif IDeletedCourse.providedBy(ICourseInstance(x, None)):
                # XXX: Make this an ACL toggle also? Would have to affect
                # zope security too.
                pass
            elif has_permission(ACT_READ, x, self.principal):
                result.append(x)
        return result

    def entry_intids(self):
        exclude_non_public = not is_admin_or_site_admin(self.principal)
        entry_intids = get_all_site_entry_intids(exclude_non_public=exclude_non_public,
                                                 exclude_deleted=True)
        entries_to_exclude = [ICourseCatalogEntry(x) for x in self._courses_to_exclude]
        intids = component.getUtility(IIntIds)
        excluded_intids = intids.family.IF.LFSet(intids.getId(x) for x in entries_to_exclude)
        catalog = get_courses_catalog()
        return catalog.family.IF.difference(entry_intids, excluded_intids)


class UnauthenticatedAvailableCoursesProvider(AvailableCoursesProvider):
    """
    For unauthenticated principals, ensure they get the available courses only
    if the catalog folder is setup for anonymous access.
    """

    def entry_intids(self):
        folder = component.getUtility(ICourseCatalog)
        if not folder.anonymously_accessible:
            return ()
        return super(UnauthenticatedAvailableCoursesProvider, self).entry_intids()


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
    Returns 'purchased' objects, defined as the :class:`ICourseCatalogEntry`
    of each enrollment for this user.
    """

    def __init__(self, user):
        self.user = user

    def _sort_key(self, record):
        return record.createdTime

    @property
    def enrollments(self):
        return get_enrollments(self.user)

    def get_collection_iter(self, filter_string=None):
        """
        Returns an iterable over this collection provider, optionally
        filtering on the given string.
        """
        # Most recent first
        result = sorted(self.enrollments, key=self._sort_key, reverse=True)
        result = [ICourseCatalogEntry(x.CourseInstance) for x in result]
        if filter_string:
            filter_utility = component.getUtility(ICourseCatalogEntryFilterUtility)
            result = filter_utility.filter_entries(result, (filter_string,))
        return result


import zope.deferredimport
zope.deferredimport.initialize()

zope.deferredimport.deprecatedFrom(
    "moved to nti.contenttypes.courses",
    "nti.contenttypes.courses.catalog",
    "CourseCatalog",
    "CourseCatalogInstructorInfo",
    "CourseCatalogEntry")
