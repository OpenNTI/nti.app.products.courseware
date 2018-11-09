#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import csv
import six
from collections import Mapping
from six.moves.urllib_parse import urljoin

from requests.structures import CaseInsensitiveDict

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from zope.event import notify

from zope.i18n import translate

from zope.intid.interfaces import IIntIds

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

from nti.app.products.courseware.invitations.interfaces import ICourseInvitation

from nti.app.products.courseware.invitations.utils import create_course_invitation

from nti.app.products.courseware.utils import get_course_invitation
from nti.app.products.courseware.utils import get_course_invitations

from nti.app.products.courseware.views import VIEW_ENABLE_INVITATION
from nti.app.products.courseware.views import SEND_COURSE_INVITATIONS
from nti.app.products.courseware.views import ACCEPT_COURSE_INVITATION
from nti.app.products.courseware.views import ACCEPT_COURSE_INVITATIONS
from nti.app.products.courseware.views import VIEW_COURSE_ACCESS_TOKENS
from nti.app.products.courseware.views import CHECK_COURSE_INVITATIONS_CSV
from nti.app.products.courseware.views import VIEW_CREATE_COURSE_INVITATION

from nti.appserver.interfaces import IApplicationSettings

from nti.appserver.pyramid_authorization import has_permission

from nti.common.string import TRUE_VALUES

from nti.contenttypes.courses.index import IX_KEYWORDS

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_NAMES

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IJoinCourseInvitation

from nti.contenttypes.courses.interfaces import AlreadyEnrolledException
from nti.contenttypes.courses.interfaces import CourseInvitationException
from nti.contenttypes.courses.interfaces import InstructorEnrolledException
from nti.contenttypes.courses.interfaces import OpenEnrollmentNotAllowedException

from nti.contenttypes.courses.invitation import JoinCourseInvitation

from nti.contenttypes.courses.utils import get_courses_catalog
from nti.contenttypes.courses.utils import is_course_instructor
from nti.contenttypes.courses.utils import is_course_instructor_or_editor

from nti.dataserver import authorization as nauth

from nti.dataserver.authorization import ACT_CONTENT_EDIT

from nti.dataserver.authorization import is_admin_or_content_admin_or_site_admin

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IUserProfile

from nti.dataserver.users.users import User

from nti.externalization.externalization import to_external_object

from nti.externalization.interfaces import LocatedExternalDict
from nti.externalization.interfaces import StandardExternalFields

from nti.invitations.interfaces import InvitationSentEvent
from nti.invitations.interfaces import IDisabledInvitation
from nti.invitations.interfaces import IInvitationsContainer
from nti.invitations.interfaces import IActionableInvitation

from nti.links.links import Link

from nti.ntiids.ntiids import find_object_with_ntiid


CLASS = StandardExternalFields.CLASS
ITEMS = StandardExternalFields.ITEMS
LINKS = StandardExternalFields.LINKS
TOTAL = StandardExternalFields.TOTAL
MIMETYPE = StandardExternalFields.MIMETYPE
ITEM_COUNT = StandardExternalFields.ITEM_COUNT

USER_COURSE_INVITATIONS_CLASS = 'UserCourseInvitations'
COURSE_INVITATIONS_MIMETYPE = 'application/vnd.nextthought.courseware.courseinvitations'
USER_COURSE_INVITATIONS_MIMETYPE = 'application/vnd.nextthought.courses.usercourseinvitations'
COURSE_INVITATIONS_SENT_MIMETYPE = 'application/vnd.nextthought.courses.courseinvitationssent'

logger = __import__('logging').getLogger(__name__)


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='GET',
               name=VIEW_COURSE_ACCESS_TOKENS,
               permission=nauth.ACT_READ)
class CourseInvitationsView(AbstractAuthenticatedView):

    @Lazy
    def _course(self):
        return ICourseInstance(self.context)

    def __call__(self):
        if      not is_course_instructor_or_editor(self._course, self.remoteUser) \
            and not is_admin_or_content_admin_or_site_admin(self.remoteUser):
            raise hexc.HTTPForbidden()

        result = LocatedExternalDict()
        result.__parent__ = self.context
        result.__name__ = self.request.view_name
        result[CLASS] = 'CourseInvitations'
        result[MIMETYPE] = COURSE_INVITATIONS_MIMETYPE
        items = result[ITEMS] = get_course_invitations(self._course)
        result[TOTAL] = result[ITEM_COUNT] = len(items)
        return result


@view_config(name=ACCEPT_COURSE_INVITATION)
@view_config(name=ACCEPT_COURSE_INVITATIONS)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=IUser,
               permission=nauth.ACT_READ)
class UserAcceptCourseInvitationView(AcceptInvitationByCodeView):

    def handle_possible_validation_error(self, request, e):
        if isinstance(e, AlreadyEnrolledException):
            raise_json_error(
                self.request,
                hexc.HTTPForbidden,
                {
                    'message': str(e) or e.i18n_message,
                    'code': 'AlreadyEnrolledException',
                },
                None)
        elif isinstance(e, CourseInvitationException):
            raise_json_error(
                self.request,
                hexc.HTTPUnprocessableEntity,
                {
                    'message': str(e) or e.i18n_message,
                    'code': 'CourseValidationError',
                },
                None)
        elif isinstance(e, InstructorEnrolledException):
            raise_json_error(
                self.request,
                hexc.HTTPUnprocessableEntity,
                {
                    'message': str(e) or e.i18n_message,
                    'code': 'InstructorEnrolledError',
                },
                None)
        elif isinstance(e, OpenEnrollmentNotAllowedException):
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': str(e) or e.i81n_message,
                                 'code': 'OpenEnrollmentNotAllowedError'
                             },
                             None)
        else:
            AcceptInvitationByCodeView.handle_possible_validation_error(self, request, e)

    def get_invite_code(self):
        if self.request.body:
            data = read_body_as_external_object(self.request)
        else:
            data = self.request.params
        if isinstance(data, Mapping):
            data = CaseInsensitiveDict(data)
            data = data.get('code') \
                or data.get('invitation') \
                or data.get('invitation_code') \
                or data.get('invitation_codes')  # legacy
        if not isinstance(data, six.string_types):
            raise hexc.HTTPBadRequest()
        return data

    def _transform(self, accepted):
        if IJoinCourseInvitation.providedBy(accepted):
            course = find_object_with_ntiid(accepted.course)
            course = ICourseInstance(course, None)
            enrollment = component.queryMultiAdapter((course, self.context),
                                                     ICourseInstanceEnrollment)
            return enrollment
        return accepted

    def _get_courses_by_code(self, code):
        catalog = get_courses_catalog()
        query = {
            IX_KEYWORDS: {'any_of': (code,)}
        }
        intids = component.getUtility(IIntIds)
        for doc_id in catalog.apply(query) or ():
            course = intids.queryObject(doc_id)
            if ICourseInstance.providedBy(course):
                yield course

    def _do_validation(self, code):
        result = None
        invitation = self.invitations.get_invitation_by_code(code)
        if invitation is None:
            # Not targeted, so look through catalog for generic code.
            for course in self._get_courses_by_code(code):
                invitation = get_course_invitation(course, code)
                if invitation is not None:
                    break
        if IDisabledInvitation.providedBy(invitation):
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': _(u"Invitation code no longer valid."),
                                 'code': 'InvalidInvitationCode',
                             },
                             None)

        if ICourseInvitation.providedBy(invitation):
            # If a generic ICourseInvitation, we need to convert into a user
            # specific invitation, if possible. If we do this, we do not
            # need to validate invitation specifics.
            result = IActionableInvitation(invitation, None)
        # If nothing, the super class must handle validation.
        if result is None:
            result = super(UserAcceptCourseInvitationView, self)._do_validation(code)
        return result

    def _do_call(self):
        accepted = AcceptInvitationByCodeView._do_call(self)
        return self._transform(accepted)

    def _web_root(self):
        settings = component.getUtility(IApplicationSettings)
        web_root = settings.get('web_app_root', '/app/')
        return web_root

    def _get_app_url(self, request, redemption_code):
        url = 'catalog/redeem/%s' % redemption_code
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
        self.request.environ['nti.request_had_transaction_side_effects'] = 'True'
        # XXX single enrollment record. Externalize first
        # we have seen a LocationError if the enrollment object is returned
        result = to_external_object(item)
        return result


# These may be non-public courses that the incoming user
# is not (yet) enrolled in. Thus, no permissions required.


@view_config(name=ACCEPT_COURSE_INVITATION)
@view_config(name=ACCEPT_COURSE_INVITATIONS)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=ICourseInstance)
class CourseInvitationAcceptView(UserAcceptCourseInvitationView):

    def _do_call(self):
        code = self.get_invite_code()
        accepted = self.handle_generic_invitation(self.context, code)
        if accepted is not None:
            self.accept_invitation(self.remoteUser, accepted)
        else:
            accepted = super(CourseInvitationAcceptView, self)._do_call()
        return self._transform(accepted)


@view_config(name=ACCEPT_COURSE_INVITATION)
@view_config(name=ACCEPT_COURSE_INVITATIONS)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               context=ICourseCatalogEntry)
class CatalogEntryInvitationAcceptView(CourseInvitationAcceptView):
    pass


@view_config(context=ICourseInstance)
@view_config(context=ICourseCatalogEntry)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               permission=nauth.ACT_READ,
               name=CHECK_COURSE_INVITATIONS_CSV)
class CheckCourseInvitationsCSVView(AbstractAuthenticatedView,
                                    ModeledContentUploadRequestUtilsMixin):

    @Lazy
    def _course(self):
        return ICourseInstance(self.context)

    def parse_csv_users(self, warnings=(), invalid_emails=()):
        result = []
        source = get_source(self.request, 'csv', 'input', 'source')
        if source is not None:
            # Read in and split (to handle universal newlines).
            # XXX: Generalize this?
            source = source.read()
            for idx, row in enumerate(csv.reader(source.splitlines())):
                if not row or row[0].startswith("#"):
                    continue
                email = row[0]
                email = email.strip() if email else email
                realname = row[1] if len(row) > 1 else email
                if not email:
                    msg = translate(_(u"Missing email in line ${line}.",
                                    mapping={'line': idx + 1}))
                    warnings.append(msg)
                    continue
                if not isValidMailAddress(email):
                    invalid_emails.append(email)
                    continue
                result.append({'email': email, 'name': realname})
        else:
            warnings.append(_(u"No CSV source found."))
        return result

    def __call__(self):
        if      not is_course_instructor(self._course, self.remoteUser) \
            and not has_permission(nauth.ACT_NTI_ADMIN, self._course, self.request):
            raise hexc.HTTPForbidden()

        warnings = list()
        invalid_emails = list()
        result = LocatedExternalDict()
        result[CLASS] = USER_COURSE_INVITATIONS_CLASS
        result[MIMETYPE] = USER_COURSE_INVITATIONS_MIMETYPE
        try:
            result[ITEMS] = self.parse_csv_users(warnings, invalid_emails)
        except:
            logger.exception('Failed to parse csv file')
            raise_json_error(
                self.request,
                hexc.HTTPUnprocessableEntity,
                {
                    'message': _(u'Could not parse csv file.'),
                    'code': 'InvalidCSVFileCodeError',
                },
                None)
        result['Warnings'] = warnings if warnings else None
        if invalid_emails:
            invalid = dict()
            invalid['message'] = _(u"Invalid emails.")
            invalid[ITEMS] = invalid_emails
            result['InvalidEmails'] = invalid
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
        result = super(SendCourseInvitationsView, self).readInput(value)
        result = CaseInsensitiveDict(result)
        return result

    def get_course_and_scope(self, values):
        """
        Get the course and scope for the given params. We attempt to use
        any course invitations as a basis for this. Otherwise, we fall
        back to defaulting to our current course and ES_PUBLIC scope.
        """
        invitation = None
        code = values.get('code') or values.get('invitation')
        if not code:
            # Default to course invitation, if it exists.
            invitations = get_course_invitations(self.context)
            if invitations:
                invitation = invitations[0]  # pick first
        else:
            # Raise if they give us a code and we cannot find it.
            invitation = get_course_invitation(self.context, code)
            if invitation is None:
                raise_json_error(
                    self.request,
                    hexc.HTTPUnprocessableEntity,
                    {
                        'message': _(u'Invalid invitation code.'),
                        'code': 'InvalidInvitationCodeError',
                    },
                    None)
        course = getattr(invitation, 'Course', self.context)
        scope = values.get('scope')
        if scope is None:
            scope = getattr(invitation, 'Scope', ES_PUBLIC)
        return course, scope

    def get_direct_users(self, values, warnings=()):
        usernames = values.get('username') or values.get('usernames')
        if isinstance(usernames, six.string_types):
            usernames = usernames.split(",")
        usernames = set(x.lower() for x in usernames or ())

        result = {}
        for username in usernames:
            user = User.get_user(username)
            if not IUser.providedBy(user):
                msg = translate(_(u"Could not find user ${user}.",
                                  mapping={'user': username}))
                warnings.append(msg)
                continue
            profile = IUserProfile(user)
            realname = profile.realname or user.username
            email = getattr(profile, 'email', None)
            if not email:
                msg = translate(_(u"User ${user} does not have a valid email.",
                                  mapping={'user': username}))
                warnings.append(msg)
                continue
            result[email] = (realname, user.username)
        return result

    def get_user_course_invitations(self, values, warnings=(), invalid_emails=()):
        result = {}
        if     values.get(MIMETYPE) == USER_COURSE_INVITATIONS_MIMETYPE \
            or values.get(CLASS) == USER_COURSE_INVITATIONS_CLASS:
            items = values.get(ITEMS) or ()
            for idx, entry in enumerate(items):
                email = entry.get('email')
                realname = entry.get('name') or email
                if not email:
                    msg = translate(_(u"Missing email at index ${idx}.",
                                      mapping={'idx': idx + 1}))
                    warnings.append(msg)
                    continue
                if not isValidMailAddress(email):
                    invalid_emails.append(email)
                    continue
                result[email] = (realname, email)
        return result

    def get_name_email(self, values, warnings=()):
        result = {}
        email = values.get('email')
        name = values.get('name') or email
        if name or email:
            if not email:
                msg = _(u"Missing email.")
                warnings.append(msg)
            elif not isValidMailAddress(email):
                msg = translate(_(u"Invalid email ${email}.",
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
        if      not is_course_instructor(self._course, self.remoteUser) \
            and not has_permission(nauth.ACT_NTI_ADMIN, self._course, self.request):
            raise hexc.HTTPForbidden()

        values = self.readInput()
        force = (values.get('force') or '').lower() in TRUE_VALUES
        if not force:
            links = (
                Link(self.request.path, rel='confirm',
                     params={'force': True}, method='POST'),
            )
        else:
            links = None

        warnings = []
        invalid_emails = []
        course, scope = self.get_course_and_scope(values)
        user_invitations = self.get_user_course_invitations(values,
                                                            warnings,
                                                            invalid_emails)
        if not force and (warnings or invalid_emails):
            err_json = {
                'warnings':  warnings,
                'message': _(u'There are errors in the user invitation source.'),
                'code': 'SendCourseInvitationError',
                LINKS: to_external_object(links) if links else None,
            }
            if invalid_emails:
                invalid = dict()
                invalid['message'] = _(u"Invalid emails.")
                invalid[ITEMS] = invalid_emails
                err_json['InvalidEmails'] = invalid
            raise_json_error(
                self.request,
                hexc.HTTPUnprocessableEntity,
                err_json,
                None)

        warnings = []
        direct_users = self.get_direct_users(values, warnings)
        if not force and warnings:
            raise_json_error(
                self.request,
                hexc.HTTPUnprocessableEntity,
                {
                    'warnings':  warnings,
                    'message': _(u'Could not process all direct user invitations.'),
                    'code': 'SendCourseInvitationError',
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
                    'warnings':  warnings,
                    'message': _(u'Could not process single user invitation.'),
                    'code': 'SendCourseInvitationError',
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
                    'message': _(u'There are no invitations to process.'),
                    'code': 'SendCourseInvitationError',
                },
                None)

        # send invites
        message = values.get('message')
        entry_ntiid = ICourseCatalogEntry(course).ntiid
        logger.info('Sending emails to %s users (%s)', len(all_users), entry_ntiid)
        sent = self.send_invitations(all_users,
                                     entry_ntiid,
                                     scope,
                                     message=message)
        result = LocatedExternalDict()
        result[CLASS] = 'CourseInvitationsSent'
        result[MIMETYPE] = COURSE_INVITATIONS_SENT_MIMETYPE
        result[ITEMS] = sent
        result[TOTAL] = result[ITEM_COUNT] = len(sent)
        return result


@view_config(context=ICourseInstance)
@view_defaults(route_name='objects.generic.traversal',
               renderer='rest',
               request_method='POST',
               name=VIEW_CREATE_COURSE_INVITATION,
               permission=ACT_CONTENT_EDIT)
class CreateGenericCourseInvitationView(AbstractAuthenticatedView,
                                        ModeledContentUploadRequestUtilsMixin):
    """
    Create a generic :class:`ICourseInvitation` object.
    """

    def readInput(self, value=None):
        if self.request.body:
            result = super(CreateGenericCourseInvitationView, self).readInput(value)
            result = CaseInsensitiveDict(result)
        else:
            result = dict()
        return result

    def _scope_lookup(self, scope_name):
        """
        Case insensitive lookup of given scope.
        """
        scope_dict = dict()
        for scope in ENROLLMENT_SCOPE_NAMES:
            scope_dict[scope.lower()] = scope
        scope_name = scope_name.lower()
        result = scope_dict.get(scope_name)
        if result is None:
            raise_json_error(
                self.request,
                hexc.HTTPUnprocessableEntity,
                {
                    'message': _(u'This is an invalid course invitation scope.'),
                    'code': 'InvalidCourseInvitationScope',
                },
                None)
        return result

    def __call__(self):
        params = self.readInput()
        scope_name = params.get('scope')
        if scope_name:
            scope = self._scope_lookup(scope_name)
        else:
            scope = ES_PUBLIC
        invitation = create_course_invitation(self.context, scope=scope, is_generic=True)
        logger.info('Created course invitation (%s) (%s)',
                    invitation.code,
                    ICourseCatalogEntry(self.context).ntiid)
        return invitation


class InvitationEditMixin(object):

    def check_access(self, context):
        """
        Can only edit persisted invitations as users with EDIT access
        on the invitation course.
        """
        if not getattr(context, '_p_jar', None):
            raise_json_error(
                self.request,
                hexc.HTTPUnprocessableEntity,
                {
                    'message': _(u'Cannot edit configured course invitation.'),
                    'code': 'CannotEditConfiguredInvitationError',
                },
                None)
        entry = find_object_with_ntiid(context.course)
        course = ICourseInstance(entry, None)
        if not has_permission(ACT_CONTENT_EDIT, course, self.request):
            raise_json_error(
                self.request,
                hexc.HTTPForbidden,
                {
                    'message': _(u'Invalid permission for course invitation.'),
                    'code': 'CourseInvitationAccessError',
                },
                None)

@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInvitation,
             request_method='DELETE',
             permission=nauth.ACT_CONTENT_EDIT)
class DisableInvitationView(AbstractAuthenticatedView, InvitationEditMixin):
    """
    A view to disable a course invitation.
    """

    def __call__(self):
        self.check_access(self.context)
        interface.alsoProvides(self.context, IDisabledInvitation)
        logger.info('Disabled invitation (%s)', self.context.code)
        return hexc.HTTPNoContent()


@view_config(route_name='objects.generic.traversal',
             renderer='rest',
             context=ICourseInvitation,
             request_method='POST',
             name=VIEW_ENABLE_INVITATION,
             permission=nauth.ACT_CONTENT_EDIT)
class EnableInvitationView(AbstractAuthenticatedView, InvitationEditMixin):
    """
    A view to enable a disabled course invitation.
    """

    def __call__(self):
        self.check_access(self.context)
        if IDisabledInvitation.providedBy(self.context):
            interface.noLongerProvides(self.context, IDisabledInvitation)
        logger.info('Enabling disabled invitation (%s)', self.context.code)
        return self.context
