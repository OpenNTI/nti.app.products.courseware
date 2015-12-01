#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views related to course emails.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from pyramid.view import view_config
from pyramid import httpexceptions as hexc

from nti.app.mail.views import AbstractMemberEmailView

from nti.common.maps import CaseInsensitiveDict

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver import authorization as nauth

from nti.dataserver.users import User
from nti.dataserver.interfaces import IEnumerableEntityContainer

from ..interfaces import ICourseInstanceEnrollment

from . import VIEW_COURSE_MAIL

@view_config(route_name='objects.generic.traversal',
			 context=ICourseInstance,
			 permission=nauth.ACT_READ,
			 renderer='rest',
			 request_method='POST',
			 name=VIEW_COURSE_MAIL)
class CourseMailView(AbstractMemberEmailView):
	"""
	Support emailing one or many students from the roster.

	TODO: Do we gather students from subinstances automatically?
	TODO: Permissioning, any instructor have permission or only
	those on each subinstance?

	Params:

	scope
		We support scope filters of: `all`, `ForCredit`, `Public`
		and `Open`, case insensitive. By default, all users are
		emailed.

	"""
	@property
	def _context_display_name(self):
		cat_entry = ICourseCatalogEntry(self.course)
		return getattr(cat_entry, 'title', '')

	def _default_subject(self):
		display_name = self._context_display_name
		return 'Email for "%s" users' % display_name

	@property
	def course(self):
		return self.context

	def _get_scope_usernames(self, scope):
		result = {x.lower() for x in IEnumerableEntityContainer( scope ).iter_usernames()}
		return result

	@property
	def _public_usernames(self):
		public_scope = self.course.SharingScopes.get(ES_PUBLIC)
		result = self._get_scope_usernames( public_scope )
		return result

	@property
	def _for_credit_scope(self):
		return self.course.SharingScopes.get(ES_CREDIT)

	@property
	def _for_credit_usernames(self):
		result = self._get_scope_usernames( self._for_credit_scope )
		return result

	def _get_member_names(self):
		values = CaseInsensitiveDict(self.request.params)
		scope_name = values.get('scope')

		if not scope_name or scope_name.lower() == 'all':
			result = self._public_usernames
		elif scope_name.lower() == 'forcredit':
			result = self._for_credit_usernames
		elif scope_name.lower() in ('public', 'open'):
			result = self._public_usernames - self._for_credit_usernames
		else:
			raise hexc.HTTPUnprocessableEntity(detail='Invalid scope %s' % scope_name)

		instructor_usernames = {x.username for x in self.course.instructors}
		result = result - instructor_usernames
		return result

	def reply_addr_for_recipient(self, recipient):
		"""
		If the recipient is Public/Open, we never want a reply address.
		"""
		if recipient not in self._for_credit_scope:
			result = self._no_reply_addr
		else:
			result = self._sender_reply_addr
		return result

	def iter_members(self):
		for username in self._get_member_names():
			user = User.get_user(username)
			if user is not None:
				yield user

	def predicate(self):
		return is_course_instructor(self.course, self.remoteUser)

@view_config(route_name='objects.generic.traversal',
			 context=ICourseInstanceEnrollment,
			 permission=nauth.ACT_READ,
			 renderer='rest',
			 request_method='POST',
			 name=VIEW_COURSE_MAIL)
class EnrollmentRecordMailView(CourseMailView):
	"""
	Email an individual student.
	"""

	@property
	def course(self):
		return ICourseInstance(self.context, None)

	def iter_members(self):
		user = User.get_user(self.context.Username)
		return (user,)

	def predicate(self):
		return 	self.course is not None \
			and is_course_instructor(self.course, self.remoteUser)

	def reply_addr_for_recipient(self, recipient):
		return self._sender_reply_addr
