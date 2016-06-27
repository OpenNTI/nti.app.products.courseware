#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import BatchingUtilsMixin

from nti.app.products.courseware import MessageFactory as _

from nti.app.products.courseware import VIEW_CLASSMATES
from nti.app.products.courseware import VIEW_COURSE_CLASSMATES

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment
from nti.app.products.courseware.interfaces import IClassmatesSuggestedContactsProvider

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.contenttypes.courses.utils import get_enrollment_record

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

class BaseClassmatesView(AbstractAuthenticatedView, BatchingUtilsMixin):
	"""
	batchSize
		The size of the batch.  Defaults to 50.

	batchStart
		The starting batch index.  Defaults to 0.
	"""

	_DEFAULT_BATCH_SIZE = 50
	_DEFAULT_BATCH_START = 0

	def selector(self, contact):
		user = User.get_user(contact.username)
		if user is not None and self.remoteUser != user:
			ext = to_external_object(user, name="summary")
			ext.pop(LINKS, None)
			return ext
		return contact

	def export_suggestions(self, result_dict, suggestions):
		result_dict['TotalItemCount'] = len(suggestions)
		self._batch_items_iterable(result_dict, suggestions, selector=self.selector)
		result_dict[ITEM_COUNT] = len(result_dict.get(ITEMS) or ())

@view_config(context=ICourseInstance)
@view_config(context=ICourseInstanceEnrollment)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_READ,
			   name=VIEW_COURSE_CLASSMATES)
class CourseClassmatesView(BaseClassmatesView):

	def __call__(self):
		record = get_enrollment_record(self.context, self.remoteUser)
		if record is None:
			raise hexc.HTTPForbidden(_("Must be enrolled in course."))
		result = LocatedExternalDict()
		provider = component.getUtility(IClassmatesSuggestedContactsProvider)
		suggestions = provider.suggestions_by_course(self.remoteUser, self.context)
		self.export_suggestions(result, suggestions)
		return result

@view_config(context=IUser)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_READ,
			   name=VIEW_CLASSMATES)
class ClassmatesView(BaseClassmatesView):

	def __call__(self):
		if self.remoteUser != self.request.context:
			raise hexc.HTTPForbidden()
		result = LocatedExternalDict()
		provider = component.getUtility(IClassmatesSuggestedContactsProvider)
		suggestions = provider.suggestions(self.remoteUser)
		self.export_suggestions(result, suggestions)
		return result
