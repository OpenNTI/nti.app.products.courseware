#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views related to course emails.

.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from requests.structures import CaseInsensitiveDict

from zope.cachedescriptors.property import Lazy

from zope.i18n import translate

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from nti.app.externalization.error import raise_json_error

from nti.app.mail.views import AbstractMemberEmailView

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.products.courseware.views import VIEW_COURSE_MAIL

from nti.common.string import is_true

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import is_course_instructor

from nti.dataserver import authorization as nauth

from nti.dataserver.interfaces import IEnumerableEntityContainer

from nti.dataserver.users.interfaces import IUserProfile

from nti.dataserver.users.users import User


@view_config(route_name='objects.generic.traversal',
             context=ICourseInstance,
             permission=nauth.ACT_READ,
             renderer='rest',
             request_method='POST',
             name=VIEW_COURSE_MAIL)
class CourseMailView(AbstractMemberEmailView):
    """
    Support emailing one or many students from the roster.

    We do not currently gather students from subinstances automatically.

    Params:

    scope
            We support scope filters of: `All`, `ForCredit`, `Public`
            and `Open`, case insensitive. By default, all users are
            emailed.

    replyToScope
            The same values as `scope`.  Only users in this scope
            will get reply addresses. This is only valid if the email
            itself allows replies.

    include-instructors
            If true, email all instructors in the course as well
            as the students in this scope. Defaults to false.
    """
    @Lazy
    def _context_display_name(self):
        cat_entry = ICourseCatalogEntry(self.course, None)
        result = getattr(cat_entry, 'title', None)
        if not result:
            result = getattr(cat_entry, 'ProviderUniqueID', '')
        return result

    @Lazy
    def _context_logged_info(self):
        cat_entry = ICourseCatalogEntry(self.course, None)
        return getattr(cat_entry, 'ProviderUniqueID', self.course.__name__)

    def _default_subject(self):
        profile = IUserProfile(self.sender)
        display_name = profile.realname or self.sender.username
        return u'Email from %s' % display_name

    @property
    def course(self):
        return self.context

    @Lazy
    def _reply_to_scope_usernames(self):
        values = CaseInsensitiveDict(self.request.params)
        scope_name = values.get('replyToScope')
        if not scope_name or scope_name.lower() == 'all':
            result = None
        elif scope_name.lower() == 'forcredit':
            result = self._for_credit_usernames
        elif scope_name.lower() in ('public', 'open'):
            result = self._only_public_usernames
        return result

    def _get_scope_usernames(self, scope):
        result = set()
        if scope:
            result = {
                x.lower() for x in IEnumerableEntityContainer(scope).iter_usernames()
            }
        return result

    @Lazy
    def _instructors(self):
        instructor_usernames = {
            x.username.lower() for x in self.course.instructors or ()
        }
        return instructor_usernames

    @Lazy
    def _all_students(self):
        enrollments = ICourseEnrollments(self.course)
        result = set(x.lower() for x in enrollments.iter_principals())
        return result - self._instructors

    @Lazy
    def _only_public_usernames(self):
        # PURCHASED falls in this category.
        return self._all_students - self._for_credit_usernames

    @Lazy
    def _for_credit_scope(self):
        return self.course.SharingScopes.get(ES_CREDIT)

    @Lazy
    def _for_credit_usernames(self):
        result = self._get_scope_usernames(self._for_credit_scope)
        return result & self._all_students

    def _copy_instructors_if_necessary(self, members, params):
        instructor_usernames = self._instructors
        include_instructors = params.get('include-instructors')
        if include_instructors and is_true(include_instructors):
            return members | instructor_usernames - {self.sender.username.lower()}
        return members - instructor_usernames

    def _get_member_names(self):
        values = CaseInsensitiveDict(self.request.params)
        scope_name = values.get('scope')

        if not scope_name or scope_name.lower() == 'all':
            result = self._all_students
        elif scope_name.lower() == 'forcredit':
            result = self._for_credit_usernames
        elif scope_name.lower() in ('public', 'open'):
            result = self._only_public_usernames
        else:
            msg = translate(_(u"Invalid scope ${scope}",
                              mapping={'scope': scope_name}))
            raise_json_error(self.request,
                             hexc.HTTPUnprocessableEntity,
                             {
                                 'message': msg,
                             },
                             None)
        return result

    def reply_addr_for_recipient(self, recipient):
        """
        If the user specifies that we only supply a ReplyTo on a certain
        type of enrollee of a course, do so.
        """
        result = self._no_reply_addr
        normed_username = recipient.username.lower()
        if     not self._reply_to_scope_usernames \
            or normed_username in self._reply_to_scope_usernames \
            or normed_username in self._instructors:
            result = self._sender_reply_addr
        return result

    def iter_members(self):
        values = CaseInsensitiveDict(self.request.params)
        for username in self._copy_instructors_if_necessary(self._get_member_names(), values):
            user = User.get_user(username)
            if user is not None:
                yield user

    def predicate(self):
        return is_course_instructor(self.course, self.remoteUser)

    def _get_reply_addr(self, to_user, email):
        # Overriding this method, because we always want
        # to provide a reply-to email address for
        # instructors, even if students don't get one.
        if email.NoReply and to_user.username.lower() not in self._instructors:
            result = self._no_reply_addr
        else:
            result = self.reply_addr_for_recipient(to_user)
        return result


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

    @Lazy
    def _context_logged_info(self):
        course = super(EnrollmentRecordMailView, self)._context_display_name
        result = u'%s in %s' % (self.context.Username, course)
        return result

    @Lazy
    def course(self):
        return ICourseInstance(self.context, None)

    def _get_member_names(self):
        return {self.context.Username, }

    def predicate(self):
        return  self.course is not None \
            and is_course_instructor(self.course, self.remoteUser)

    def reply_addr_for_recipient(self, unused_recipient):
        return self._sender_reply_addr
