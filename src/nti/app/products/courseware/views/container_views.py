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

from nti.app.products.courseware.views import raise_error
from nti.app.products.courseware.views import VIEW_LESSONS_CONTAINERS

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQuestionSet

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.presentation.interfaces import INTIAssessmentRef
from nti.contenttypes.presentation.interfaces import INTIQuestionSetRef

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

TOTAL = StandardExternalFields.TOTAL
ITEMS = StandardExternalFields.ITEMS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

class AbstractContainersView(AbstractAuthenticatedView):
	"""
	Fetch all lessons holding our given context. A `course` param
	can be given that narrows the scope of the result, otherwise,
	results from all courses will be returned.
	"""

	#: Subclasses define this for searching
	provided = None

	def __call__(self):
		result = LocatedExternalDict()
		course = ICourseInstance(self.request, None)
		courses = (course,)
		if course is None:
			courses = get_evaluation_courses(self.context)
		if not courses:
			raise_error({
				u'message': _("No courses found for assessment."),
				u'code': 'NoCoursesForAssessment',
				})
		lessons = get_evaluation_lessons( self.context,
										  self.provided,
										  courses=courses,
										  request=self.request )
		lessons = set( lessons or () )
		result[ITEMS] = lessons
		result[ITEM_COUNT] = result[TOTAL] = len(lessons)
		return result

@view_config(context=IQuestionSet)
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

	# Some assignments are in question set refs...
	provided = INTIAssessmentRef
