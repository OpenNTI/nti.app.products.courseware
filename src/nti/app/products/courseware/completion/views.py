#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from slugify import slugify

from zope import component

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from zc.displayname.interfaces import IDisplayNameGenerator

from zope.cachedescriptors.property import Lazy

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.appserver.policies.site_policies import guess_site_display_name

from nti.common.string import is_true

from nti.dataserver import authorization as nauth

from nti.dataserver.users import User

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.contenttypes.credit.interfaces import ICreditTranscript

from nti.app.products.courseware import VIEW_CERTIFICATE

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy
from nti.contenttypes.completion.interfaces import IProgress

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

class EnrollmentProgressViewMixin(object):

    @Lazy
    def course(self):
        return self.context.CourseInstance

    @Lazy
    def user(self):
        username = self.context.Username
        return User.get_user(username)

    @Lazy
    def course_policy(self):
        return ICompletionContextCompletionPolicy(self.course, None)

    @Lazy
    def progress(self):
        return component.queryMultiAdapter((self.user, self.course), IProgress)


@view_config(route_name='objects.generic.traversal',
             renderer="templates/completion_certificate.rml",
             request_method='GET',
             context=ICourseInstanceEnrollment,
             name=VIEW_CERTIFICATE,
             permission=nauth.ACT_READ)
class CompletionCertificateView(AbstractAuthenticatedView,
                                EnrollmentProgressViewMixin):

    Title = u'Completion Certificate'

    @Lazy
    def course(self):
        return self.context.CourseInstance

    @Lazy
    def user(self):
        username = self.context.Username
        return User.get_user(username)

    @Lazy
    def _name(self):
        # A certificate is fairly formal so try and use realname first
        name = IFriendlyNamed(self.user).realname
        if not name:
            # Otherwise just fallback to whatever is our display name generator
            name = component.getMultiAdapter((self.user, self.request),
                                             IDisplayNameGenerator)()
        return name

    @Lazy
    def _brand(self):
        policy = component.getUtility(ISitePolicyUserEventListener)
        display_name = getattr(policy, 'BRAND', '')
        if display_name:
            display_name = display_name.strip()
        else:
            display_name = guess_site_display_name(self.request)
        return display_name

    @Lazy
    def _course_completable_item(self):
        if self.course_policy is None:
            return None

        return self.course_policy.is_complete(self.progress)

    def _filename(self, entry, suffix='completion', ext='pdf'):
        filename = '%s %s %s' % (self.user, entry.ProviderUniqueID, suffix)
        slugged = slugify(filename, seperator='_', lowercase=True)
        return '%s.%s' % (slugged, ext)

    @property
    def _completion_date_string(self):
        completed = self._course_completable_item.CompletedDate
        return completed.strftime('%B %d, %Y')

    def _facilitators(self, entry):
        facilitators = []
        for i in entry.Instructors:
            facilitator = {}
            for attr in ('Name', 'JobTitle'):
                facilitator[attr] = getattr(i, attr, '')
            facilitators.append(facilitator)
        return facilitators[:6]

    def _awarded_credit(self, transcript):
        if not transcript:
            return ()
        def _for_display(awarded_credit):
            return {
                u'Amount': u'%.2f' % awarded_credit.amount,
                u'Type': awarded_credit.credit_definition.credit_type,
                u'Units': awarded_credit.credit_definition.credit_units.capitalize()
            }
        return [_for_display(credit) for credit in transcript.iter_awarded_credits()]

    def __call__(self):
        if     self._course_completable_item is None \
            or not self.course_policy.offers_completion_certificate:
            raise hexc.HTTPNotFound()

        entry = ICourseCatalogEntry(self.course)

        download = is_true(self.request.params.get('download', False))
        if download:
            response = self.request.response
            response.content_disposition = 'attachment; filename="%s"' % self._filename(entry)

        transcript = component.queryMultiAdapter((self.user, self.course),
                                                 ICreditTranscript)

        return {
            u'Brand': self._brand,
            u'Name': self._name,
            u'Course': entry.title,
            u'Date': self._completion_date_string,
            u'Facilitators': self._facilitators(entry),
            u'Credit': self._awarded_credit(transcript)
        }

