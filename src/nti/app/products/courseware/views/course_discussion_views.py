#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from zope.security.interfaces import IPrincipal

from pyramid.view import view_config
from pyramid.view import view_defaults
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.internalization import read_body_as_external_object

from nti.common.property import Lazy
from nti.common.maps import CaseInsensitiveDict

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstancePublicScopedForum
from nti.contenttypes.courses.interfaces import ICourseInstanceForCreditScopedForum

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.dataserver import authorization as nauth

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.ntiids.ntiids import find_object_with_ntiid

from ..discussions import get_topic_key

from . import CourseAdminPathAdapter

ITEMS = StandardExternalFields.ITEMS

def _parse_courses(values):
	# get validate course entry
	ntiids = values.get('ntiid') or values.get('ntiids') or \
			 values.get('entry') or values.get('entries') or \
			 values.get('course') or values.get('courses')
	if not ntiids:
		raise hexc.HTTPUnprocessableEntity(detail='No course entry identifier')

	if isinstance(ntiids, six.string_types):
		ntiids = ntiids.split()

	result = []
	for ntiid in ntiids:
		context = find_object_with_ntiid(ntiid)
		context = ICourseCatalogEntry(context, None)
		if context is not None:
			result.append(context)
	return result

def _parse_course(values):
	result = _parse_courses(values)
	if not result:
		raise hexc.HTTPUnprocessableEntity(detail='Course not found')
	return result[0]

# discussions

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='GET',
			   name='discussions',
			   permission=nauth.ACT_READ)
class CourseDiscussionsView(AbstractAuthenticatedView):

	@Lazy
	def _course(self):
		return ICourseInstance(self.context)

	@Lazy
	def _can_see_discussions(self):
		principal = IPrincipal(self.remoteUser)
		return principal in self._course.instructors

	def __call__(self):
		if not self._can_see_discussions:
			raise hexc.HTTPForbidden()
		else:
			result = LocatedExternalDict()
			items = result[ITEMS] = {}
			discussions = ICourseDiscussions(self._course, None) or {}
			for name, discussion in discussions.items():
				name = discussion.id or name
				items[name] = discussion
			return result

@view_config(name='DropCourseDiscussions')
@view_config(name='drop_course_discussions')
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=CourseAdminPathAdapter,
			   permission=nauth.ACT_NTI_ADMIN)
class DropCourseDiscussionsView(AbstractAuthenticatedView):

	def readInput(self):
		if self.request.body:
			values = read_body_as_external_object(self.request)
		else:
			values = self.request.params
		result = CaseInsensitiveDict(values)
		return result

	def __call__(self):
		values = self.readInput()
		courses = _parse_courses(values)
		if not courses:
			raise hexc.HTTPUnprocessableEntity(detail='Please specify a valid course')

		result = LocatedExternalDict()
		items = result[ITEMS] = {}
		for course in courses:
			course = ICourseInstance(course, None)
			entry = ICourseCatalogEntry(course, None)
			if course is None or entry is None:
				continue

			data = items[entry.ntiid] = {}
			course_discs = ICourseDiscussions(course, None) or {}
			course_discs = {get_topic_key(d) for d in course_discs.values()}
			if not course_discs:
				continue

			discussions = course.Discussions
			for forum in discussions.values():
				if 		not ICourseInstancePublicScopedForum.providedBy(forum) \
					and not ICourseInstanceForCreditScopedForum.providedBy(forum):
					continue

				for key in course_discs:
					if key in forum:
						del forum[key]
						data.setdefault(forum.__name__, [])
						data[forum.__name__].append(key)
		return result
