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
             renderer="rest",
             request_method='GET',
             context=ICourseInstanceEnrollment,
             name="Progress",
             permission=nauth.ACT_READ)
class CourseProgressView(AbstractAuthenticatedView, EnrollmentProgressViewMixin):

    def __call__(self):
        if self.course_policy is None:
            raise hexc.HTTPNotFound()
        return self.progress


@view_config(route_name='objects.generic.traversal',
             renderer="templates/completion_certificate.rml",
             request_method='GET',
             context=ICourseInstanceEnrollment,
             name="Certificate",
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
            u'Hours': None
        }

@view_config(route_name='objects.generic.traversal',
             renderer="rest",
             request_method='GET',
             context=ICourseInstance,
             name="ProgressStats",
             permission=nauth.ACT_READ)
class ProgressStatsView(AbstractAuthenticatedView):

    DISTRIBUTION_BUCKET_SIZE = 5
    
    @Lazy
    def course_policy(self):
        return ICompletionContextCompletionPolicy(self.context, None)
    
    def __call__(self):
        if self.course_policy is None:
            raise hexc.HTTPNotFound()

        enrollments = ICourseEnrollments(self.context)
        total_students = enrollments.count_enrollments()
        accumulated_progress = 0
        count_started = 0
        count_completed = 0
        distribution = Counter()

        for enrollment in enrollments.iter_enrollments():
            user = IUser(enrollment.Principal)
            progress = component.queryMultiAdapter((user, self.context), IProgress)
            if progress.MaxPossibleProgress:
                percentage_complete = float(progress.AbsoluteProgress) / float(progress.MaxPossibleProgress)
            else:
                percentage_complete = 0
            bucketed = self.DISTRIBUTION_BUCKET_SIZE * math.floor(percentage_complete * 100 / self.DISTRIBUTION_BUCKET_SIZE)
            distribution[bucketed] += 1
            

            accumulated_progress += percentage_complete

            if progress.AbsoluteProgress:
                count_started += 1
            if self.course_policy.is_complete(progress) is not None:
                count_completed += 1

        result = LocatedExternalDict()
        result.__name__ = self.request.view_name
        result.__parent__ = self.request.context

        result['MaxPossibleProgress'] = total_students
        result['AbsoluteProgress'] = accumulated_progress
        result['PercentageProgress'] = accumulated_progress / total_students if total_students else 0.0
        result['TotalUsers'] = total_students
        result['CountHasProgress'] = count_started
        result['CountCompleted'] = count_completed
        result['ProgressDistribution'] = {k/100.0: distribution[k]
                                          for k in range(0,101,self.DISTRIBUTION_BUCKET_SIZE)}
            
        return result
