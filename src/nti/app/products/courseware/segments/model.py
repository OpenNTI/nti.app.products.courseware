#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import BTrees
import operator

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.container.contained import Contained

from zope.intid.interfaces import IIntIds

from nti.contenttypes.completion.interfaces import IProgress

from nti.app.products.courseware.segments.interfaces import ENROLLED_IN
    
from nti.app.products.courseware.segments.interfaces import ICourseProgressFilterSet
from nti.app.products.courseware.segments.interfaces import ICourseMembershipFilterSet

from nti.contenttypes.courses import get_enrollment_catalog

from nti.contenttypes.courses.index import IX_SCOPE
from nti.contenttypes.courses.index import IX_STUDENT

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_enrollments_query

from nti.coremetadata.interfaces import IX_USERNAME

from nti.coremetadata.interfaces import IUser

from nti.dataserver.users import get_entity_catalog

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.schema.fieldproperty import createDirectFieldProperties

from nti.schema.schema import SchemaConfigured

from nti.site.site import get_component_hierarchy_names


@interface.implementer(ICourseMembershipFilterSet)
class CourseMembershipFilterSet(SchemaConfigured,
                                Contained):

    createDirectFieldProperties(ICourseMembershipFilterSet)

    mimeType = mime_type = "application/vnd.nextthought.courseware.segments.coursemembershipfilterset"

    def __init__(self, **kwargs):
        SchemaConfigured.__init__(self, **kwargs)

    @property
    def enrollment_catalog(self):
        return get_enrollment_catalog()

    @property
    def entity_catalog(self):
        return get_entity_catalog()

    @property
    def enrolled_intids(self):
        result = self.enrollment_catalog.family.IF.Set()

        scopes = entry_ntiids = None
        if self.course_ntiid:
            course = find_object_with_ntiid(self.course_ntiid)
            course = ICourseInstance(course, None)
            catalog_entry = ICourseCatalogEntry(course, None)

            if catalog_entry is None:
                return result

            entry_ntiids = (catalog_entry.ntiid,)

            # In case it hasn't been initialized already
            course.SharingScopes.initScopes()
            scopes = course.SharingScopes.keys()

        # TODO: Do we want to be more restrictive than this?  E.g. only
        #  operate on the current site, or the site the "parent" segment is
        #  stored in (filter sets are not currently Contained objects).  Should
        #  this be a part of the definition?  To some
        #  degree this is currently already enforced at the view level.
        site_names = get_component_hierarchy_names()
        query = get_enrollments_query(catalog=self.enrollment_catalog,
                                      site_names=site_names,
                                      entry_ntiids=entry_ntiids)

        # If a course was provided and, hence, we have the scopes available in
        # that course, then we can restrict the query to only those scopes
        if scopes is not None:
            query[IX_SCOPE] = {'any_of': scopes}

        for intid in self.enrollment_catalog.apply(query):
            usernames = self.enrollment_catalog[IX_STUDENT].documents_to_values.get(intid)
            for username in usernames or ():
                user_intids = self.entity_catalog[IX_USERNAME].values_to_documents.get(username)
                for user_intid in user_intids or ():
                    result.add(user_intid)

        return result

    def apply(self, initial_set):
        intids = self.enrolled_intids
        if self.operator == ENROLLED_IN:
            return initial_set.intersection(intids)
        return initial_set.difference(intids)



@interface.implementer(ICourseProgressFilterSet)
class CourseProgressFilterSet(SchemaConfigured,
                              Contained):

    createDirectFieldProperties(ICourseProgressFilterSet)

    mimeType = mime_type = "application/vnd.nextthought.courseware.segments.courseprogressfilterset"

    def __init__(self, **kwargs):
        SchemaConfigured.__init__(self, **kwargs)

    @Lazy
    def course(self):
        course = find_object_with_ntiid(self.course_ntiid)
        course = ICourseInstance(course, None)
        return course
    
    @Lazy
    def op(self):
        return getattr(operator, self.operator)
    
    def _get_progress(self, user):
        progress = component.queryMultiAdapter((user, self.course),
                                               IProgress)
        return progress
    
    def _check(self, progress):
        return self.op(progress.PercentageProgress, self.percentage)
    
    def _iter_users(self):
        if self.course is None:
            return
        enrollments = ICourseEnrollments(self.course)
        for record in enrollments.iter_enrollments():
            user = IUser(record, None)
            if user is not None:
                progress = self._get_progress(user)
                if self._check(progress):
                    yield user
    
    def _get_intids(self, set_factory):
        intids = component.getUtility(IIntIds)
        result = set_factory()
        for user in self._iter_users():
            user_intid = intids.getId(user)
            result.add(user_intid)
        return result
    
    def apply(self, initial_set):
        set_factory = initial_set.family.IF.Set
        intids = self._get_intids(set_factory)
        return initial_set.intersection(intids)
