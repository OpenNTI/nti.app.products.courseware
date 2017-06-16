#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.assessment.common import get_evaluation_courses

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware import MessageFactory as _

from nti.app.products.courseware.utils import get_evaluation_lessons
from nti.app.products.courseware.utils import get_content_related_work_refs

from nti.app.products.courseware.views import raise_error
from nti.app.products.courseware.views import VIEW_LESSONS_CONTAINERS

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQuestionSet

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contentlibrary.interfaces import IContentUnit

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import get_courses_for_packages

from nti.contenttypes.presentation.interfaces import INTIAssessmentRef
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

TOTAL = StandardExternalFields.TOTAL
ITEMS = StandardExternalFields.ITEMS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT


class AbstractContainersView(AbstractAuthenticatedView):
    """
    Fetch all lessons holding our given context. A `course` param
    can be given that narrows the scope of the result, otherwise,
    results from all courses will be returned.
    """

    def __call__(self):
        result = LocatedExternalDict()
        course = ICourseInstance(self.request, None)
        courses = (course,)
        if course is None:
            courses = self._get_courses()
        if not courses:
            self._raise_error()
        lessons = self._get_lessons(courses)
        lessons = set(lessons or ())
        result[ITEMS] = lessons
        result[ITEM_COUNT] = result[TOTAL] = len(lessons)
        return result


@view_config(context=IContentUnit)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name=VIEW_LESSONS_CONTAINERS,
               permission=nauth.ACT_CONTENT_EDIT)
class ContentContainersView(AbstractContainersView):
    """
    Fetches all lessons that contain this `:class:IContentUnit`.
    """

    def _raise_error(self):
        raise_error({
            u'message': _("No courses found for reading."),
            u'code': 'NoCoursesForReading',
            })

    def _get_courses(self):
        return get_courses_for_packages(packages=self.context.ntiid)

    def _get_ref_lessons(self, catalog, ref):
        result = []
        containers = catalog.get_containers(ref)
        for ntiid in containers or ():
            obj = find_object_with_ntiid(ntiid)
            if INTILessonOverview.providedBy(obj):
                result.append(obj)
        return result

    def _get_lessons(self, courses):
        refs = get_content_related_work_refs(self.context)
        lessons = []
        catalog = get_library_catalog()
        for ref in refs or ():
            ref_lessons = self._get_ref_lessons(catalog, ref)
            if ref_lessons:
                lessons.extend(ref_lessons)
        return lessons


class AbstractAssessmentContainersView(AbstractContainersView):

    #: Subclasses define this for searching
    provided = None

    def _raise_error(self):
        raise_error({
            u'message': _("No courses found for assessment."),
            u'code': 'NoCoursesForAssessment',
            })

    def _get_courses(self):
        return get_evaluation_courses(self.context)

    def _get_lessons(self, courses):
        lessons = get_evaluation_lessons(self.context,
                                         self.provided,
                                         courses=courses,
                                         request=self.request)
        return lessons


@view_config(context=IQuestionSet)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name=VIEW_LESSONS_CONTAINERS,
               permission=nauth.ACT_CONTENT_EDIT)
class QuestionSetContainersView(AbstractAssessmentContainersView):
    provided = INTIQuestionSetRef


@view_config(context=IQAssignment)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               name=VIEW_LESSONS_CONTAINERS,
               permission=nauth.ACT_CONTENT_EDIT)
class AssignmentLessonsContainersView(AbstractAssessmentContainersView):
    # Some assignments are in question set refs...
    provided = INTIAssessmentRef
