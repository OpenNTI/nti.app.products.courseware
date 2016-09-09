#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.intid.interfaces import IIntIds

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.assessment.common import get_evaluation_courses

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware import MessageFactory as _

from nti.app.products.courseware.views import raise_error
from nti.app.products.courseware.views import VIEW_LESSONS_CONTAINERS

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQuestionSet

from nti.assessment.randomized.interfaces import IQuestionBank

from nti.contentlibrary.indexed_data import get_library_catalog

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.presentation.interfaces import INTIAssignmentRef
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef
from nti.contenttypes.presentation.interfaces import INTILessonOverview

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.site.site import get_component_hierarchy_names

from nti.traversal.traversal import find_interface

TOTAL = StandardExternalFields.TOTAL
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

class AbstractContainersView(AbstractAuthenticatedView):
	"""
	Fetch all lessons holding our given context. A `course` param
	can be given that narrows the scope of the result, otherwise,
	results from all courses will be returned.
	"""

	# : Subclasses define for searching
	provided = None

	def _search_for_lessons(self, container_ntiids, catalog, intids, sites):
		results = []
		for item in catalog.search_objects(intids=intids,
										   provided=self.provided,
										   container_ntiids=container_ntiids,
										   container_all_of=False,
										   sites=sites):
			if item.target == self.context.ntiid:
				lesson = find_interface(item, INTILessonOverview, strict=False)
				if lesson is not None:
					results.append(lesson)
		return results

	def get_lessons(self, courses):
		catalog = get_library_catalog()
		intids = component.getUtility(IIntIds)
		sites = get_component_hierarchy_names()
		container_ntiids = \
				set(getattr(ICourseCatalogEntry(x, None), 'ntiid', None) for x in courses)
		container_ntiids.discard(None)
		result = self._search_for_lessons(container_ntiids, catalog, intids, sites)
		return result

	def __call__(self):
		result = LocatedExternalDict()
		result['Lessons'] = lessons = list()
		course = ICourseInstance(self.request, None)
		courses = (course,)
		if course is None:
			courses = get_evaluation_courses(self.context)
		if not courses:
			raise_error({
				u'message': _("No courses found for assessment."),
				u'code': 'NoCoursesForAssessment',
				})
		lessons.extend(self.get_lessons(courses))
		result[ITEM_COUNT] = result[TOTAL] = len(lessons)
		return result

@view_config(context=IQuestionSet)
@view_config(context=IQuestionBank)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   name=VIEW_LESSONS_CONTAINERS,
			   permission=nauth.ACT_CONTENT_EDIT)
class QuestionSetContainersView(AbstractContainersView):

	provided = INTIQuestionSetRef

@view_config(context=IQAssignment)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   name=VIEW_LESSONS_CONTAINERS,
			   permission=nauth.ACT_CONTENT_EDIT)
class AssignmentLessonsContainersView(AbstractContainersView):

	provided = INTIAssignmentRef
