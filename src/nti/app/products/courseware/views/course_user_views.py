#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from . import MessageFactory as _

from zope import component

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import authorization as nauth

from nti.dataserver.users import User
from nti.dataserver.interfaces import IUser

from nti.externalization.interfaces import LocatedExternalDict 
from nti.externalization.interfaces import StandardExternalFields 
from nti.externalization.externalization import to_external_object

from .. import VIEW_CLASSMATES
from .. import VIEW_COURSE_CLASSMATES

from ..utils import get_enrollment_record

from ..interfaces import ICourseInstanceEnrollment
from ..interfaces import IClassmatesSuggestedContactsProvider

ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS

class BaseClassmatesView(AbstractAuthenticatedView):

	def export_suggestions(self, suggestions):
		for contact in suggestions:
			user = User.get_user(contact.username)
			if user is not None and self.remoteUser != user:
				ext = to_external_object(user, name="summary")
				ext.pop(LINKS, None)
				yield ext
	
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
		items = result[ITEMS] = []
		provider = component.queryUtility(IClassmatesSuggestedContactsProvider)
		if provider is not None:
			suggestions = provider.suggestions_by_course(self.remoteUser, self.context)
			for ext in self.export_suggestions(suggestions):
				items.append(ext)
		return result

@view_config(context=IUser)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_READ,
			   name=VIEW_CLASSMATES)
class ClassmatesView(BaseClassmatesView):

	def __call__(self):
		result = LocatedExternalDict()
		items = result[ITEMS] = []
		provider = component.queryUtility(IClassmatesSuggestedContactsProvider)
		if provider is not None:
			suggestions = provider.suggestions(self.remoteUser)
			for ext in self.export_suggestions(suggestions):
				items.append(ext)
		return result
