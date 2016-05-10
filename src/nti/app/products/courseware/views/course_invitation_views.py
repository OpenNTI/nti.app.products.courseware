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
from urlparse import urljoin
from collections import Mapping

from zope import component

from zope.event import notify

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

from nti.app.invitations.views import AcceptInvitationByCodeView

from nti.app.products.courseware import MessageFactory as _

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.products.courseware.utils import get_course_invitation
from nti.app.products.courseware.utils import get_course_invitations

from nti.app.products.courseware.views import SEND_COURSE_INVITATIONS
from nti.app.products.courseware.views import VIEW_COURSE_INVITATIONS
from nti.app.products.courseware.views import ACCEPT_COURSE_INVITATION
from nti.app.products.courseware.views import ACCEPT_COURSE_INVITATIONS
from nti.app.products.courseware.views import CHECK_COURSE_INVITATIONS_CSV

from nti.appserver.pyramid_authorization import has_permission

from nti.common.maps import CaseInsensitiveDict

from nti.common.property import Lazy

from nti.common.string import TRUE_VALUES

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IJoinCourseInvitation

from nti.contenttypes.courses.interfaces import AlreadyEnrolledException
from nti.contenttypes.courses.interfaces import CourseInvitationException

from nti.contenttypes.courses.invitation import JoinCourseInvitation

from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IUser

from nti.dataserver.users import User
from nti.dataserver.users.interfaces import IUserProfile

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.invitations.interfaces import InvitationSentEvent
from nti.invitations.interfaces import IInvitationsContainer

from nti.links.links import Link

from nti.ntiids.ntiids import find_object_with_ntiid

CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS
MIMETYPE = StandardExternalFields.MIMETYPE

USER_COURSE_INVITATIONS_CLASS = u'UserCourseInvitations'
COURSE_INVITATIONS_MIMETYPE = u'application/vnd.nextthought.courseware.courseinvitations'
USER_COURSE_INVITATIONS_MIMETYPE = u'application/vnd.nextthought.courses.usercourseinvitations'
COURSE_INVITATIONS_SENT_MIMETYPE = u'application/vnd.nextthought.courses.courseinvitationssent'

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
		result[MIMETYPE] = COURSE_INVITATIONS_MIMETYPE
		items = result[ITEMS] = get_course_invitations(self._course)
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

@view_config(name=ACCEPT_COURSE_INVITATION)
@view_config(name=ACCEPT_COURSE_INVITATIONS)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   context=IUser,
			   permission=nauth.ACT_READ)
class AcceptCourseInvitationsView(AcceptInvitationByCodeView):

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

	def get_invite_code(self):
		if self.request.body:
			data = read_body_as_external_object(self.request)
		else:
			data = self.request.params
		if isinstance(data, Mapping):
			data = CaseInsensitiveDict(data)
			data = 		data.get('code') \
					or  data.get('invitation') \
					or	data.get('invitation_code') \
					or	data.get('invitation_codes') # legacy
		if not isinstance(data, six.string_types):
			raise hexc.HTTPBadRequest()
		return data

	def handle_generic_invitation(self, code):
		invitation = get_course_invitation(self.context, code)
		if invitation is not None and invitation.IsGeneric:
			invitation = JoinCourseInvitation()
			invitation.scope = invitation.Scope
			invitation.course = invitation.Course
			invitation.receiver = self.context.username
			self.invitations.add(invitation) # record a new invitation
			return invitation
		return None

	def _do_call(self):
		code = self.get_invite_code()
		accepted = self.handle_generic_invitation(code)
		if accepted is not None:
			self.accept_invitation(self.context, accepted)
		else:
			accepted = AcceptInvitationByCodeView._do_call(self)
		if IJoinCourseInvitation.providedBy(accepted):
			course = find_object_with_ntiid(accepted.course)
			course = ICourseInstance(course, None)
			enrollment = component.queryMultiAdapter((course, self.context),
											 		 ICourseInstanceEnrollment)
			return enrollment
		return accepted

	def _web_root(self):
		from nti.appserver.interfaces import IApplicationSettings
		settings = component.getUtility(IApplicationSettings)
		web_root = settings.get('web_app_root', '/app/')
		return web_root

	def _get_app_url(self, request, redemption_code):
		url = 'library/courses/available/invitations/accept/%s' % redemption_code
		app_url = request.application_url
		redemption_link = urljoin(app_url, self._web_root())
		redemption_link = urljoin(redemption_link, url)
		return redemption_link

	def __call__(self):
		if not self.request.is_xhr:
			# For non-xhr (email links), redirect to our app form.
			code = self.get_invite_code()
			app_url = self._get_app_url(self.request, code)
			raise hexc.HTTPFound(location=app_url)
		item = self._do_call()
		# Make sure we commit
		self.request.environ[b'nti.request_had_transaction_side_effects'] = b'True'
		# XXX single enrollment record. Externalize first
		# we have seen a LocationError if the enrollment object is returned
		result = to_external_object(item)
		return result

@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
			   renderer='rest',
			   request_method='POST',
			   name=CHECK_COURSE_INVITATIONS_CSV,
			   permission=nauth.ACT_READ)
class CheckCourseInvitationsCSVView(AbstractAuthenticatedView,
									ModeledContentUploadRequestUtilsMixin):

	@Lazy
	def _course(self):
		return ICourseInstance(self.context)

	def parse_csv_users(self, warnings=()):
		result = []
		source = get_source(self.request, 'csv', 'input', 'source')
		if source is not None:
			for idx, row in enumerate(csv.reader(source)):
				if not row or row[0].startswith("#"):
					continue
				email = row[0]
				realname = row[1] if len(row) > 1 else email
				if not email:
					msg = translate(_("Missing email in line ${line}.",
									mapping={'line': idx + 1}))
					warnings.append(msg)
					continue
				if not isValidMailAddress(email):
					msg = translate(_("Invalid email ${email} in line ${line}.",
									mapping={'email': email, 'line': idx + 1}))
					warnings.append(msg)
					continue
				if email.lower().endswith('@nextthought.com'):
					msg = translate(_("Cannot send invitation to email ${email}.",
									 mapping={'email': email}))
					warnings.append(msg)
					continue
				result.append({'email':email, 'name':realname})
		else:
			warnings.append(_("No CSV source found."))
		return result

	def __call__(self):
		if 		not is_course_instructor(self._course, self.remoteUser) \
			and not has_permission(nauth.ACT_NTI_ADMIN, self._course, self.request):
			raise hexc.HTTPForbidden()

		warnings = list()
		result = LocatedExternalDict()
		result[CLASS] = USER_COURSE_INVITATIONS_CLASS
		result[MIMETYPE] = USER_COURSE_INVITATIONS_MIMETYPE
		result[ITEMS] = self.parse_csv_users(warnings)
		result['Warnings'] = warnings if warnings else None
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

	def get_course_invitation(self, values):
		invitation = None
		code = values.get('code') or values.get('invitation')
		if not code:
			invitations = get_course_invitations(self.context)
			if invitations:
				invitation = invitations[0]  # pick first
			else:
				raise_json_error(
						self.request,
						hexc.HTTPUnprocessableEntity,
						{
							u'message': _('Must provide a inviation code.') ,
							u'code': 'MissingInvitationCodeError',
						},
						None)
		if invitation is None:
			invitation = get_course_invitation(self.context, code)
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

	def get_user_course_invitations(self, values, warnings=()):
		result = {}
		if 		values.get(MIMETYPE) == USER_COURSE_INVITATIONS_MIMETYPE \
			or	values.get(CLASS) == USER_COURSE_INVITATIONS_CLASS:
			items = values.get(ITEMS) or ()
			for idx, entry in enumerate(items):
				email = entry.get('email')
				realname = entry.get('name') or email
				if not email:
					msg = translate(_("Missing email at index ${idx}.",
									mapping={'idx': idx + 1}))
					warnings.append(msg)
					continue
				if not isValidMailAddress(email):
					msg = translate(_("Invalid email ${email} at index ${idx}.",
									mapping={'email': email, 'idx':idx + 1}))
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
		email = values.get('email')
		name = values.get('name') or email
		if name or email:
			if not email:
				msg = translate(_("Missing email."))
				warnings.append(msg)
			elif not isValidMailAddress(email):
				msg = translate(_("Invalid email ${email}.",
								mapping={'email': email}))
				warnings.append(msg)
			else:
				result[email] = (name, email)
		return result

	@Lazy
	def invitations(self):
		return component.getUtility(IInvitationsContainer)

	def register_invitation(self, course, username, email, name, scope, message=None):
		result = JoinCourseInvitation(name=name, email=email, message=message)
		result.scope = scope
		result.course = course
		result.receiver = username
		result.sender = self.remoteUser.username
		self.invitations.add(result)
		return result

	def send_invitations(self, users, course, scope=None, message=None):
		result = list()
		for email, data in users.items():
			name, username = data
			invitation = self.register_invitation(name=name,
												  email=email,
												  scope=scope,
												  course=course,
												  message=message,
												  username=username)
			notify(InvitationSentEvent(invitation, username))
			result.append(invitation)
		return result

	def __call__(self):
		if 		not is_course_instructor(self._course, self.remoteUser) \
			and not has_permission(nauth.ACT_NTI_ADMIN, self._course, self.request):
			raise hexc.HTTPForbidden()

		values = self.readInput()
		force = (values.get('force') or u'').lower() in TRUE_VALUES
		if not force:
			links = (
				Link(self.request.path, rel='confirm',
					 params={'force':True}, method='POST'),
			)
		else:
			links = None

		warnings = []
		invitation = self.get_course_invitation(values)
		user_invitations = self.get_user_course_invitations(values, warnings)
		if not force and warnings:
			raise_json_error(
					self.request,
					hexc.HTTPUnprocessableEntity,
					{
						u'warnings':  warnings,
						u'message': _('There are errors in the user invitation source.') ,
						u'code': 'SendCourseInvitationError',
						LINKS: to_external_object(links) if links else None,
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
						u'message': _('Could not process all direct user invitations.') ,
						u'code': 'SendCourseInvitationError',
						LINKS: to_external_object(links) if links else None,
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
						u'message': _('Could not process single user invitation.') ,
						u'code': 'SendCourseInvitationError',
						LINKS: to_external_object(links) if links else None,
					},
					None)

		all_users = direct_users
		all_users.update(direct_email)
		all_users.update(user_invitations)
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
		message = values.get('message')
		sent = self.send_invitations(all_users,
									 invitation.Course,
									 invitation.Scope,
									 message=message)
		result = LocatedExternalDict()
		result[CLASS] = 'CourseInvitationsSent'
		result[MIMETYPE] = COURSE_INVITATIONS_SENT_MIMETYPE
		result[ITEMS] = sent
		return result
