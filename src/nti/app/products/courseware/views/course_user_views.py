#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from . import MessageFactory as _

from zope.security.interfaces import IPrincipal

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.dataserver import authorization as nauth

from nti.dataserver.users import User

from nti.externalization.interfaces import LocatedExternalDict 
from nti.externalization.interfaces import StandardExternalFields 
from nti.externalization.externalization import to_external_object

from .. import VIEW_COURSE_CLASSMATES

from ..utils import get_enrollment_record

from ..interfaces import ICourseInstanceEnrollment

ITEMS = StandardExternalFields.ITEMS

@view_config(context=ICourseInstance)
@view_config(context=ICourseInstanceEnrollment)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   permission=nauth.ACT_READ,
			   name=VIEW_COURSE_CLASSMATES)
class ClassmatesView(AbstractAuthenticatedView):

	def __call__(self):
		record = get_enrollment_record(self.context, self.remoteUser)
		if record is None:
			raise hexc.HTTPForbidden(_("Must be enrolled in course."))
		
		implies = set([record.Scope])
		for term in ENROLLMENT_SCOPE_VOCABULARY:
			if record.Scope == term.value:
				implies.update(term.implies)
				break
		
		result = LocatedExternalDict()
		items = result[ITEMS] = []
		course = ICourseInstance(self.context)
		for record in ICourseEnrollments(course).iter_enrollments():
			if record.Scope in implies:
				username = IPrincipal(record.Principal).id
				user = User.get_user(username)
				if user is not None:
					ext = to_external_object(user, name="summary")
					items.append(ext)
		return result
