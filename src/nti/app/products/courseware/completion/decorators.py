#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various course pieces.

.. $Id$
"""

from zope import component
from zope import interface

from zope.cachedescriptors.property import Lazy

from nti.app.contenttypes.completion.views import progress_link
from nti.app.contenttypes.completion.views import completed_items_link

from nti.app.products.courseware import VIEW_CERTIFICATE

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import IUser

from nti.externalization.interfaces import IExternalMappingDecorator
from nti.externalization.interfaces import StandardExternalFields

from nti.externalization.singleton import Singleton

from nti.links.links import Link

LINKS = StandardExternalFields.LINKS

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstanceEnrollment)
@interface.implementer(IExternalMappingDecorator)
class _CourseCompletionDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorates progress information on a course
    """

    def __init__(self, context, request):
        super(_CourseCompletionDecorator, self).__init__(context, request)
        self.context = context

    @Lazy
    def course(self):
        return ICourseInstance(self.context)

    @Lazy
    def user(self):
        return IUser(self.context)

    @Lazy
    def policy(self):
        return ICompletionContextCompletionPolicy(self.course, None)

    def has_policy(self):
        return self.policy != None

    @Lazy
    def progress(self):
        return component.queryMultiAdapter((self.user, self.course),
                                           IProgress)

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        # Provide a link to the user's completed items
        _links.append(completed_items_link(self.course, self.user))
        if self.has_policy():
            _links.append(progress_link(self.course,
                                        user=self.user,
                                        rel='Progress'))
            if 'CourseProgress' not in result:
                result['CourseProgress'] = self.progress
            completed_item = self.policy.is_complete(self.progress)
            # pylint: disable=no-member
            if      completed_item is not None \
                and completed_item.Success \
                and self.policy.offers_completion_certificate:
                _links.append(Link(context,
                                   rel=VIEW_CERTIFICATE,
                                   elements=("@@" + VIEW_CERTIFICATE,)))


@component.adapter(IUser)
@interface.implementer(IExternalMappingDecorator)
class _UserLinkDecorator(Singleton):
    """
    Marker rel saying certificates are enabled.
    """

    def decorateExternalMapping(self, context, result):
        _links = result.setdefault(LINKS, [])
        _links.append(Link(context, elements=(VIEW_CERTIFICATE,), rel=VIEW_CERTIFICATE))


@component.adapter(ICourseInstance)
@interface.implementer(IExternalMappingDecorator)
class _CourseProgressStatsDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Decorates a progress stats link on the course
    """

    def _predicate(self, context, unused_result):
        return ICompletionContextCompletionPolicy(context, None) != None

    def _do_decorate_external(self, context, result):
        _links = result.setdefault(LINKS, [])
        _links.append(progress_link(context, rel='ProgressStats'))


@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalMappingDecorator)
class _CatalogCertificateDecorator(_CourseCompletionDecorator):
    """
    Decorates a progress stats link on the course
    """

    def _predicate(self, unused_context, unused_result):
        return self.policy is not None

    def _do_decorate_external(self, unused_context, result):
        if     'AwardsCertificate' not in result \
           and getattr(self.policy, 'offers_completion_certificate', False):
            result['AwardsCertificate'] = True
