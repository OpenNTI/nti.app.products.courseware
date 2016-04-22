#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import csv
import six
from collections import Mapping

from zope import component

from zope.i18n import translate

from z3c.schema.email import isValidMailAddress

from pyramid import httpexceptions as hexc

from pyramid.view import view_config
from pyramid.view import view_defaults

from nti.app.base.abstract_views import get_source
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.error import raise_json_error

from nti.app.externalization.internalization import read_body_as_external_object

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.app.invitations.views import AcceptInvitationsView

from nti.app.products.courseware import MessageFactory as _

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.products.courseware.invitations import send_invitation_email

from nti.app.products.courseware.utils import get_course_invitation
from nti.app.products.courseware.utils import get_all_course_invitations
from nti.app.products.courseware.utils import get_invitations_for_course

from nti.app.products.courseware.views import SEND_COURSE_INVITATIONS
from nti.app.products.courseware.views import VIEW_COURSE_INVITATIONS
from nti.app.products.courseware.views import ACCEPT_COURSE_INVITATIONS

from nti.app.products.courseware.views import CourseAdminPathAdapter

from nti.appserver.dataserver_pyramid_views import GenericGetView

from nti.appserver.pyramid_authorization import has_permission

from nti.common.maps import CaseInsensitiveDict

from nti.common.property import Lazy

from nti.common.string import TRUE_VALUES

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IJoinCourseInvitation

from nti.contenttypes.courses.interfaces import AlreadyEnrolledException
from nti.contenttypes.courses.interfaces import CourseInvitationException

from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDataserverFolder

from nti.dataserver.users import User
from nti.dataserver.users.interfaces import IUserProfile

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.links.links import Link

from nti.ntiids.ntiids import find_object_with_ntiid

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS
MIMETYPE = StandardExternalFields.MIMETYPE

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
		if 		not is_course_instructor(self._course, self.remoteUser) \
			and not has_permission(nauth.ACT_NTI_ADMIN, self._course, self.request):
			raise hexc.HTTPForbidden()

		result = LocatedExternalDict()
		result[CLASS] = 'CourseInvitations'
		result[MIMETYPE] = u'application/vnd.nextthought.courses.joincourseinvitations'
		invitations = get_invitations_for_course(self._course)
		items = result[ITEMS] = dict(invitations)
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

@view_config(context=IUser)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   name=ACCEPT_COURSE_INVITATIONS,
			   permission=nauth.ACT_READ)
class AcceptCourseInvitationsView(AcceptInvitationsView):

	def get_invite_codes(self):
		if self.request.body:
			data = read_body_as_external_object(self.request)
		else:
			data = self.request.subpath[0] if self.request.subpath else ''
			data = self.request.params

		if isinstance(data, Mapping):
			data = data.get('invitation_codes') or data.get('codes') or data.get('code')
		if isinstance(data, six.string_types):
			data = data.split()
		if not data:
			raise hexc.HTTPBadRequest()
		return data

	def handle_possible_validation_error(self, request, e):
		if isinstance(e, AlreadyEnrolledException):
			raise_json_error(
					self.request,
					hexc.HTTPConflict,
					{
						u'message': str(e),
						u'code': 'AlreadyEnrolledException',
					},
					None)
		elif isinstance(e, CourseInvitationException):
			raise_json_error(
					self.request,
					hexc.HTTPUnprocessableEntity,
					{
						u'message': str(e),
						u'code': 'CourseValidationError',
					},
					None)
		else:
			super(AcceptCourseInvitationsView, self).handle_possible_validation_error(request, e)

	def _do_call(self):
		items = []
		accepted = AcceptInvitationsView._do_call(self) or {}
		for invitation in accepted.values():
			if not IJoinCourseInvitation.providedBy(invitation):
				continue
			course = find_object_with_ntiid(invitation.course)
			course = ICourseInstance(course, None)
			enrollment = component.queryMultiAdapter((course, self.context),
												 	 ICourseInstanceEnrollment)
			if enrollment is not None:
				items.append(enrollment)
		return items

	def __call__(self):
		items = self._do_call()
		# make sure we commit
		self.request.environ[b'nti.request_had_transaction_side_effects'] = b'True'
		if self.request.is_xhr:
			if len(items) == 1:
				# XXX single enrollment record. Externalize first
				# we have seen a LocationError if the enrollment object is returned
				result = to_external_object(items[0])
			else:
				result = LocatedExternalDict()
				result[CLASS] = 'CourseInstanceEnrollments'
				result[ITEMS] = items
		else:
			# XXX: redirect to host so enrollments can be loaded
			result = hexc.HTTPFound(location=self.request.host_url)
		return result

@view_config(context=ICourseInstance)
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

	def readInput(self, value=None):
		result = ModeledContentUploadRequestUtilsMixin.readInput(self, value=value)
		result = CaseInsensitiveDict(result)
		return result

	def get_invitation(self, values):
		code = values.get('code')
		if not code:
			invitations = get_invitations_for_course(self.context)
			if invitations: # not provided
				code = tuple(invitations.keys())[0] # pick first
		if not code:
			raise hexc.HTTPUnprocessableEntity(_("Must provide a inviation code."))
		invitation = get_course_invitation(code)
		if invitation is None:
			raise_json_error(
					self.request,
					hexc.HTTPUnprocessableEntity,
					{
						u'message': _('Invalid inviation code.') ,
						u'code': 'InvalidInvitationCodeError',
					},
					None)
		return invitation

	def get_direct_users(self, values, warnings=()):
		usernames = values.get('username') or values.get('usernames')
		if isinstance(usernames, six.string_types):
			usernames = usernames.split(",")
		usernames = set(x.lower() for x in usernames or ())

		result = {}
		for username in usernames:
			if username.endswith('@nextthought.com'):
				msg = translate(_("Cannot send invitation to NT user ${user}.",
								 mapping={'user': username}))
				warnings.append(msg)
				continue
			user = User.get_user(username)
			if not IUser.providedBy(user):
				msg = translate(_("Could not find user ${user}.",
								mapping={'user': username}))
				warnings.append(msg)
				continue
			profile = IUserProfile(user)
			realname = profile.realname or user.username
			email = getattr(profile, 'email', None)
			if not email:
				msg = translate(_("User ${user} does not have a valid email.",
								mapping={'user': username}))
				warnings.append(msg)
				continue
			result[email] = (realname, user.username)
		return result

	def get_csv_users(self, warnings=()):
		result = {}
		source = get_source(self.request, 'csv', 'input')
		if source is not None:
			for idx, row in enumerate(csv.reader(source)):
				if not row or row[0].startswith("#"):
					continue
				realname = row[0]
				email = row[1] if len(row) > 1 else None
				if not realname or not email:
					msg = translate(_("Missing name or email in line ${line}.",
									mapping={'line': idx+1}))
					warnings.append(msg)
					continue
				if not isValidMailAddress(email):
					msg = translate(_("Invalid email ${email}.",
									mapping={'email': email}))
					warnings.append(msg)
					continue
				if email.lower().endswith('@nextthought.com'):
					msg = translate(_("Cannot send invitation to email ${email}.",
									 mapping={'email': email}))
					warnings.append(msg)
					continue
				result[email] = (realname, email)
		return result

	def get_name_email(self, values, warnings=()):
		result = {}
		name = values.get('name')
		email = values.get('email')
		if name or email:
			if not name or not email:
				msg = translate(_("Missing name or email."))
				warnings.append(msg)
			elif not isValidMailAddress(email):
				msg = translate(_("Invalid email ${email}.",
								mapping={'email': email}))
				warnings.append(msg)
			else:
				result[email] = (name, email)
		return result

	def send_invitations(self, invitation, users):
		result = dict()
		for email, data in users.items():
			name, username = data
			if send_invitation_email(invitation,
									 self.remoteUser,
								 	 name,
								  	 email,
								  	 username,
								     self.request):
				result[email] = name
		return result

	def __call__(self):
		if 		not is_course_instructor(self._course, self.remoteUser) \
			and not has_permission(nauth.ACT_NTI_ADMIN, self._course, self.request):
			raise hexc.HTTPForbidden()

		values = self.readInput()
		force = (values.get('force') or u'').lower() in TRUE_VALUES

		warnings = []
		invitation = self.get_invitation(values)
		csv_users = self.get_csv_users(warnings)
		if not force and warnings:
			links = (
				Link(self.request.path, rel='confirm',
					 params={'force':True}, method='POST'),
			)
			raise_json_error(
					self.request,
					hexc.HTTPUnprocessableEntity,
					{
						u'warnings':  warnings,
						u'message': _('There are errors in invitation csv source.') ,
						u'code': 'SendCourseInvitationCSVError',
						LINKS: to_external_object(links),
					},
					None)

		warnings = []
		direct_users = self.get_direct_users(values, warnings)
		if not force and warnings:
			raise_json_error(
					self.request,
					hexc.HTTPUnprocessableEntity,
					{
						u'warnings':  warnings,
						u'message': _('Could not process all user invitations.') ,
						u'code': 'SendCourseInvitationUserError',
					},
					None)

		warnings = []
		direct_email = self.get_name_email(values, warnings)
		if not force and warnings:
			raise_json_error(
					self.request,
					hexc.HTTPUnprocessableEntity,
					{
						u'warnings':  warnings,
						u'message': _('Could not process all user invitations.') ,
						u'code': 'SendCourseInvitationUserError',
					},
					None)

		all_users = direct_users
		all_users.update(csv_users)
		all_users.update(direct_email)
		if not all_users:
			raise_json_error(
					self.request,
					hexc.HTTPUnprocessableEntity,
					{
						u'message': _('There are no invitation to process.') ,
						u'code': 'SendCourseInvitationError',
					},
					None)

		# send invites
		sent = self.send_invitations(invitation, direct_users)
		result = LocatedExternalDict()
		result[ITEMS] = sent
		return result

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
		items = result[ITEMS] = list(get_all_course_invitations())
		result['Total'] = result['ItemCount'] = len(items)
		result.__parent__ = self.context
		result.__name__ = self.request.view_name
		return result
