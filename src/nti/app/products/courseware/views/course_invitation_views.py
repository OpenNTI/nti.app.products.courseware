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

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.products.courseware.views import SEND_COURSE_INVITATIONS
from nti.app.products.courseware.views import VIEW_COURSE_INVITATIONS

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.common.property import Lazy

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IJoinCourseInvitation

from nti.contenttypes.courses.utils import is_course_instructor
	
from nti.dataserver import authorization as nauth
from nti.dataserver.interfaces import IDataserverFolder

from nti.externalization.externalization import to_external_ntiid_oid

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

ITEMS = StandardExternalFields.ITEMS

@view_config(context=ICourseInstance)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   name=VIEW_COURSE_INVITATIONS,
			   permission=nauth.ACT_READ)
class CourseInvitationsView(AbstractAuthenticatedView):

	@Lazy
	def _course(self):
		return ICourseInstance(self.context)

	def __call__(self):
		if not is_course_instructor(self._course, self.remoteUser):
			raise hexc.HTTPForbidden()
		entry = ICourseCatalogEntry(self._course)
		ntiid = to_external_ntiid_oid(self._course)
		result = LocatedExternalDict()
		items = result[ITEMS] = []
		for name, invitation in list(component.getUtilitiesFor(IJoinCourseInvitation)):
			if invitation.course in (ntiid, entry.ntiid):
				items.append(name)
		result['Total'] = result['ItemCount'] = len(items)
		result.__parent__ = self.context
		result.__name__ = self.request.view_name
		return result

@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   name=VIEW_COURSE_INVITATIONS,
			   permission=nauth.ACT_READ)
class CatalogEntryInvitationsView(CourseInvitationsView):
	pass

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   name=SEND_COURSE_INVITATIONS,
			   permission=nauth.ACT_READ)
class SendCourseInvitationsView(AbstractAuthenticatedView,
								ModeledContentUploadRequestUtilsMixin):

	@Lazy
	def _course(self):
		return ICourseInstance(self.context)

	def __call__(self):
		pass
	
@view_config(context=IDataserverFolder)
@view_config(context=CourseAdminPathAdapter)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   name=VIEW_COURSE_INVITATIONS,
			   permission=nauth.ACT_NTI_ADMIN)
class AllCourseInvitationsView(GenericGetView):

	def __call__(self):
		result = LocatedExternalDict()
		items = result[ITEMS] = {}
		for name, invitation in list(component.getUtilitiesFor(IJoinCourseInvitation)):
			key = invitation.course
			items.setdefault(key, [])
			items[key].append(name)
		result['Total'] = result['ItemCount'] = len(items)
		result.__parent__ = self.context
		result.__name__ = self.request.view_name
		return result
