#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Functions and architecture for general activity streams.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from BTrees.LFBTree import LFSet as Set

from zope.cachedescriptors.property import CachedProperty

from nti.app.notabledata.interfaces import IUserNotableProvider
from nti.app.notabledata.interfaces import IUserNotableSharedWithIDProvider

from nti.contenttypes.courses.utils import get_course_enrollments
from nti.contenttypes.courses.utils import get_instructed_courses
from nti.contenttypes.courses.utils import get_non_preview_enrollments

from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_MAP

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScope
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.dataserver.contenttypes.forums.interfaces import IPersonalBlogComment

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import INotableFilter

from nti.dataserver.metadata.index import get_metadata_catalog
from nti.dataserver.metadata.index import isTopLevelContentObjectFilter

from nti.traversal.traversal import find_interface

_FEEDBACK_MIME_TYPE = "application/vnd.nextthought.assessment.userscourseassignmenthistoryitemfeedback"

logger = __import__('logging').getLogger(__name__)


def _get_implied_course_scopes(course, scope):
    """
    For the given enrollment scope and course, return all implied scopes.
    """
    results = []
    scope_term = ENROLLMENT_SCOPE_MAP[scope]
    course_scope = course.SharingScopes.get(scope)
    results.append(course_scope)
    for scope in scope_term.implies:
        course_scope = course.SharingScopes.get(scope)
        if course_scope is not None:
            results.append(course_scope)
    return results


@interface.implementer(INotableFilter)
class TopLevelPriorityNotableFilter(object):
    """
    Determines whether the object is a notable created by important
    creators (e.g. instructors of my courses).  These objects must also
    be top-level objects.
    """

    def __init__(self, context):
        self.context = context

    def is_notable(self, obj, user):
        obj_creator = getattr(obj, 'creator', None)
        obj_creator = getattr(obj_creator, 'username', obj_creator)
        # Filter out blog comments that might cause confusion.
        if     obj_creator is None \
            or IPersonalBlogComment.providedBy(obj) \
            or obj_creator == user.username:
            return False

        # Note: pulled from metadata_index; first two params not used.
        if not isTopLevelContentObjectFilter(None, None, obj):
            return False

        # See if our creator is an instructor in a current course.
        # Only if shared with my course community.
        shared_with = getattr(obj, 'sharedWith', {})
        if shared_with:
            enrollments = get_non_preview_enrollments(user.username)
            for enrollment in enrollments or ():
                if not ICourseInstanceEnrollmentRecord.providedBy(enrollment):
                    continue
                course = ICourseInstance(enrollment, None)
                catalog_entry = ICourseCatalogEntry(course, None)
                if     course is None \
                    or catalog_entry is None \
                    or not catalog_entry.isCourseCurrentlyActive():  # pragma: no cover
                    continue

                if obj_creator in (x.id for x in course.instructors or ()):
                    scopes = _get_implied_course_scopes(course,
                                                        enrollment.Scope)
                    for scope in scopes:
                        if obj.isSharedDirectlyWith(scope):
                            return True
        return False


@component.adapter(IUser, interface.Interface)
@interface.implementer(IUserNotableProvider)
class _UserPriorityCreatorNotableProvider(object):
    """
    We want all items created by instructors shared with
    course communities the user is enrolled in.  If items
    are shared with global communities or other, perhaps
    older, courses, we should exclude those.

    We also return all feedback created by such instructors.
    We rely on permissioning to filter out non-relevant entries.
    """

    def __init__(self, user, unused_request):
        self.context = user

    @CachedProperty
    def _catalog(self):
        return get_metadata_catalog()

    def _get_feedback_intids(self, instructor_intids):
        catalog = self._catalog
        query = {'any_of': (_FEEDBACK_MIME_TYPE,)}
        feedback_intids = catalog['mimeType'].apply(query)
        results = catalog.family.IF.intersection(instructor_intids,
                                                 feedback_intids)
        return results

    def get_notable_intids(self):
        results = Set()
        catalog = self._catalog
        enrollments = get_non_preview_enrollments(self.context.username)
        for enrollment in enrollments or ():
            if not ICourseInstanceEnrollmentRecord.providedBy(enrollment):
                continue
            course = ICourseInstance(enrollment, None)
            catalog_entry = ICourseCatalogEntry(course, None)
            if     course is None \
                or catalog_entry is None  \
                or not catalog_entry.isCourseCurrentlyActive():  # pragma: no cover
                continue

            course_instructors = {x.id for x in course.instructors}
            query = {'any_of': course_instructors}
            instructor_intids = catalog['creator'].apply(query)

            # Gather the implied course scopes.
            scopes = _get_implied_course_scopes(course, enrollment.Scope)
            scope_ntiids = [scope.NTIID for scope in scopes]

            query = {'any_of': scope_ntiids}
            course_shared_with_intids = catalog['sharedWith'].apply(query)
            course_results = catalog.family.IF.intersection(instructor_intids,
                                                            course_shared_with_intids)
            results.update(course_results)
            feedback_intids = self._get_feedback_intids(instructor_intids)
            results.update(feedback_intids)
        return results


@component.adapter(IUser, interface.Interface)
@interface.implementer(IUserNotableProvider)
class _UserInstructorFeedbackNotableProvider(_UserPriorityCreatorNotableProvider):
    """
    Provides a set of intids so that instructors can get
    notables for feedback that students leave on assignments.

    This means we return all items in courses where we are an
    instructor, where are feedback items created by students. We
    rely on permissioning to filter out items from other courses.
    """

    def get_notable_intids(self):
        results = Set()
        instructed_courses = get_instructed_courses(self.context)
        for course in instructed_courses:
            course_enrollments = get_course_enrollments(course)
            student_ids = [x.Principal.id for x in course_enrollments]
            index = self._catalog['creator']
            student_intids = index.apply({'any_of': student_ids})
            results.update(self._get_feedback_intids(student_intids))
        return results


@component.adapter(IUser, interface.Interface)
@interface.implementer(IUserNotableSharedWithIDProvider)
class _UserCourseSharingScopeNotableSharedWithIDProvider(object):
    """
    Return the non-preview course sharing scope ntiids to act as a source
    of notable data.
    """

    def __init__(self, user, unused_request):
        self.context = user

    def get_shared_with_ids(self):
        result = set()
        for membership in self.context.dynamic_memberships:
            if ICourseInstanceSharingScope.providedBy(membership):
                course = find_interface(membership, ICourseInstance)
                entry = ICourseCatalogEntry(course, None)
                if entry is not None and not entry.Preview:
                    result.add(membership.NTIID)
        return result
