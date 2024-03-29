#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import interface

from zope.component.hooks import getSite

from zope.security.interfaces import IPrincipal

from nti.app.products.courseware.interfaces import ISuggestedContactsProvider

from nti.app.products.courseware.utils import ZERO_DATETIME

from nti.app.site.interfaces import ISiteAdminSeatUserProvider

from nti.app.users.utils import get_user_creation_site

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_PURCHASED
from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE
from nti.contenttypes.courses.interfaces import ES_CREDIT_NONDEGREE
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_enrollments
from nti.contenttypes.courses.utils import get_enrollment_record
from nti.contenttypes.courses.utils import get_instructors_and_editors

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.suggested_contacts import SuggestedContact
from nti.dataserver.users.suggested_contacts import SuggestedContactsProvider
from nti.dataserver.users.suggested_contacts import SuggestedContactRankingPolicy

from nti.property.property import alias

ES_ORDER = {ES_CREDIT_DEGREE: 15,
            ES_CREDIT_NONDEGREE: 15,
            ES_CREDIT: 10,
            ES_PURCHASED: 10,
            ES_PUBLIC: 0}

logger = __import__('logging').getLogger(__name__)


class ClassmatesSuggestedContactRankingPolicy(SuggestedContactRankingPolicy):

    provider = alias('__parent__')

    def _r_order(self, x):
        scope = getattr(x, 'Scope', None) or ES_PUBLIC
        result = ES_ORDER.get(scope, 0)
        return result

    def _e_provider(self, x):
        entry = getattr(x, 'entry', None)
        result = getattr(entry, 'ProviderUniqueID', None) or ''
        return result

    def _e_startDate(self, x):
        entry = getattr(x, 'entry', None)
        startDate = getattr(entry, 'StartDate', None) or ZERO_DATETIME
        return startDate

    def _s_cmp(self, x, y):
        # reverse /recent first
        result = cmp(self._e_startDate(y), self._e_startDate(x))
        if result == 0:
            result = cmp(self._e_provider(x), self._e_provider(y))
        if result == 0:
            result = cmp(self._r_order(y), self._r_order(x))  # reverse
        # result = cmp(x.username, y.username) if result == 0 else result
        return result

    def sort(self, data):
        result = []
        seen = set()
        data = sorted(data, cmp=self._s_cmp)
        for contact in data:
            if contact.username not in seen:
                result.append(contact)
                seen.add(contact.username)
                try:
                    del contact.entry
                except AttributeError:
                    pass
        return result


@interface.implementer(ISuggestedContactsProvider)
class ClassmatesSuggestedContactsProvider(SuggestedContactsProvider):

    MAX_RESULT_COUNT = 10

    def __init__(self, *args, **kwargs):
        super(ClassmatesSuggestedContactsProvider, self).__init__(*args, **kwargs)
        self.ranking = ClassmatesSuggestedContactRankingPolicy()
        self.ranking.provider = self

    def _get_courses(self, user):
        for record in get_enrollments(user):
            course = ICourseInstance(record, None)
            entry = ICourseCatalogEntry(course, None)
            # Only return active courses as they are the most relevant.
            if entry is not None and entry.isCourseCurrentlyActive():
                yield course

    def iter_courses(self, user, source_user=None):
        results = self._get_courses(user)
        if source_user is not None and user != source_user:
            user_courses = set(results)
            source_courses = set(self._get_courses(source_user))
            results = user_courses.intersection(source_courses)
        return results

    def _iter_suggestions_by_course(self, user, context):
        record = get_enrollment_record(context, user)
        if record is None:
            return

        implies = set([record.Scope])
        for term in ENROLLMENT_SCOPE_VOCABULARY:
            if record.Scope == term.value:
                implies.update(term.implies)
                break

        course = ICourseInstance(context)
        entry = ICourseCatalogEntry(context, None)  # seen in alpha

        for record in ICourseEnrollments(course).iter_enrollments():
            if record.Scope in implies:
                principal = IPrincipal(record.Principal, None)
                if principal is not None and IUser(principal) != user:
                    suggestion = SuggestedContact(username=principal.id,
                                                  rank=1)
                    suggestion.entry = entry
                    suggestion.provider = self
                    suggestion.Scope = record.Scope
                    yield suggestion

    def suggestions_by_course(self, user, context):
        # XXX: Should we limit this?
        return tuple(self._iter_suggestions_by_course(user, context))

    def _get_suggestions(self, user, source_user=None):
        result = []
        for course in self.iter_courses(user, source_user):
            for suggestion in self._iter_suggestions_by_course(user, course):
                result.append(suggestion)
                if len(result) >= self.MAX_RESULT_COUNT:
                    return result
        return result

    def suggestions(self, user, source_user=None):
        result = self._get_suggestions(user, source_user)
        result = self.ranking.sort(result)
        return result


@interface.implementer(ISiteAdminSeatUserProvider)
class _CourseAdminSeatUserProvider(object):
    """
    Return a unique set of course instructors and editors,
    limited to courses and users in the current site.
    """

    def iter_users(self):
        site = getSite()
        course_admins = get_instructors_and_editors(getSite())
        for course_admin in course_admins:
            if site == get_user_creation_site(course_admin):
                yield course_admin
