#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from collections import Counter

import math

from slugify import slugify

from zope import component

from pyramid import httpexceptions as hexc

from pyramid.view import view_config

from zc.displayname.interfaces import IDisplayNameGenerator

from zope.cachedescriptors.property import Lazy

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.appserver.policies.site_policies import guess_site_display_name

from nti.dataserver import authorization as nauth

from nti.dataserver.users import User

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware import VIEW_CERTIFICATE

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy
from nti.contenttypes.completion.interfaces import IProgress

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments

from nti.dataserver.interfaces import IUser

from nti.externalization.interfaces import LocatedExternalDict

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
class CompletionCertificateView(AbstractAuthenticatedView, EnrollmentProgressViewMixin):

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
            name = component.getMultiAdapter((self.user, self.request), IDisplayNameGenerator)()
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

    def __call__(self):
        if self._course_completable_item is None:
            raise hexc.HTTPNotFound()

        entry = ICourseCatalogEntry(self.course)

        response = self.request.response
        response.content_disposition = 'attachment; filename="%s"' % self._filename(entry)

        return {
            u'Brand': self._brand,
            u'Name': self._name,
            u'Course': entry.title,
            u'Date': self._completion_date_string,
            u'Facilitators': self._facilitators(entry)
        }

