#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various course pieces.

.. $Id$
"""

from zope import component
from zope import interface

from pyramid.interfaces import IRequest

from zope.cachedescriptors.property import Lazy

from nti.app.contenttypes.completion.views import progress_link
from nti.app.contenttypes.completion.views import completed_items_link

from nti.app.products.courseware import VIEW_CERTIFICATE
from nti.app.products.courseware import VIEW_CERTIFICATE_PREVIEW
from nti.app.products.courseware import VIEW_ACKNOWLEDGE_COMPLETION

from nti.app.products.courseware.completion.interfaces import ICourseCompletedNotification

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.app.site.decorators import SiteBrandAuthDecorator

from nti.appserver.brand.interfaces import ISiteBrand

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.coremetadata.interfaces import IUser

from nti.dataserver.authorization import ACT_READ

from nti.externalization.interfaces import IExternalMappingDecorator
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.interfaces import IExternalObjectDecorator

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

    def has_acknowledged_completion(self):
        completion_notification = ICourseCompletedNotification(self.context, None)
        return completion_notification is not None and completion_notification.IsAcknowledged

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
                and completed_item.Success:

                if not self.has_acknowledged_completion():
                    # Link for acknowledging completion
                    _links.append(Link(context,
                                       method='POST',
                                       rel=VIEW_ACKNOWLEDGE_COMPLETION,
                                       elements=("@@" + VIEW_ACKNOWLEDGE_COMPLETION,)))

                if self.policy.offers_completion_certificate:
                    _links.append(Link(context,
                                       rel=VIEW_CERTIFICATE,
                                       elements=("@@" + VIEW_CERTIFICATE,)))


@component.adapter(IUser)
@interface.implementer(IExternalMappingDecorator)
class _UserLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):
    """
    Marker rel saying certificates are enabled.
    """

    def _predicate(self, context, unused_result):
        return has_permission(ACT_READ, context)

    def _do_decorate_external(self, context, mapping):
        _links = mapping.setdefault(LINKS, [])
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


@component.adapter(ISiteBrand, IRequest)
@interface.implementer(IExternalObjectDecorator)
class _SiteBrandEditDecorator(SiteBrandAuthDecorator):

    def _do_decorate_external(self, unused_context, result_map):
        edit_context = self._current_site_sitebrand()
        links = result_map.setdefault("Links", [])
        # Can only edit (and thus preview them in the completion
        # certificate) with a fs location
        if self._can_edit_sitebrand() is not None:
            link = Link(edit_context,
                        elements=("@@" + VIEW_CERTIFICATE_PREVIEW,),
                        rel='certificate_preview',
                        method='PUT')
            links.append(link)
