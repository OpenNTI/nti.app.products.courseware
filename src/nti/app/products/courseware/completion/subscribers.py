#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import isodate
import datetime

from pyramid.threadlocal import get_current_request

from six.moves import urllib_parse

from zc.displayname.interfaces import IDisplayNameGenerator

from zope.component.hooks import getSite

from zope.i18n import translate

from zope.lifecycleevent.interfaces import IObjectRemovedEvent

from zope import component
from zope import interface

from zope.event import notify

from nti.app.products.courseware import MessageFactory as _

from nti.app.products.courseware import VIEW_CERTIFICATE

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.contenttypes.completion.subscribers import completion_context_deleted_event

from nti.contenttypes.completion.interfaces import IProgress
from nti.contenttypes.completion.interfaces import IUserProgressUpdatedEvent
from nti.contenttypes.completion.interfaces import ICompletionContextCompletedItem
from nti.contenttypes.completion.interfaces import IPrincipalCompletedItemContainer
from nti.contenttypes.completion.interfaces import ICompletionContextCompletionPolicy

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import CourseCompletedEvent
from nti.contenttypes.courses.interfaces import ICourseCompletedEvent

from nti.dataserver.users.interfaces import IUserProfile

from nti.links.externalization import render_link

from nti.links.interfaces import ILinkExternalHrefOnly

from nti.links.links import Link

from nti.mailer.interfaces import ITemplatedMailer

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance, IObjectRemovedEvent)
def _on_course_deleted(course, unused_event=None):
    # clear containers. sections have their own
    completion_context_deleted_event(course)


@component.adapter(ICourseInstance, IUserProgressUpdatedEvent)
def _course_progress_updated(course, event):
    """
    The user has successfully completed a required item. If the user course
    progress moves from a state of incomplete to (successfully) complete,
    broadcast an appropriate event.

    Since we are storing course completion persistently, this means this
    event will only be fired once, upon the first successful completion.

    This object is not used when querying course completion state. To do
    that correctly, we'd have to determine how to handle shifting
    requirements.
    """
    user = event.user
    principal_container = component.queryMultiAdapter((user, course),
                                                      IPrincipalCompletedItemContainer)
    # If this has already been completed successfully, take no action.
    if     principal_container \
       and principal_container.ContextCompletedItem is not None\
       and principal_container.ContextCompletedItem.Success:
        return

    policy = ICompletionContextCompletionPolicy(course, None)
    if not policy:
        return

    progress = component.queryMultiAdapter((user, course),
                                           IProgress)
    if      progress.CompletedItem \
        and progress.CompletedItem.Success:
        # Newly successful completion, store and notify
        course_completed_item = progress.CompletedItem
        interface.alsoProvides(course_completed_item, ICompletionContextCompletedItem)
        course_completed_item.__parent__ = principal_container
        principal_container.ContextCompletedItem = course_completed_item
        notify(CourseCompletedEvent(course, user))


@component.adapter(ICourseInstance, ICourseCompletedEvent)
def send_course_completed_email(course, event):
    """
    Send the user an email notifying they've completed the course.

    We should include a link to the certificate if there is one.
    """
    request = getattr(event, 'request', None) or get_current_request()
    user = event.user
    profile = IUserProfile(user)
    email = getattr(profile, 'email', None)

    entry = ICourseCatalogEntry(course)
    policy = component.getUtility(ISitePolicyUserEventListener)
    support_email = getattr(policy, 'SUPPORT_EMAIL', 'support@nextthought.com')
    brand_name = component.getMultiAdapter((getSite(), request),
                                           IDisplayNameGenerator)()

    informal_username = component.getMultiAdapter((user, request),
                                                  IDisplayNameGenerator)()

    cert_link = None
    completion_policy = ICompletionContextCompletionPolicy(course, None)
    has_cert = getattr(completion_policy, 'offers_completion_certificate', False)
    if has_cert:
        enrollment = component.queryMultiAdapter((course, user),
                                                 ICourseInstanceEnrollment)
        cert_link = Link(enrollment,
                         rel=VIEW_CERTIFICATE,
                         elements=("@@" + VIEW_CERTIFICATE,))
        interface.alsoProvides(cert_link, ILinkExternalHrefOnly)
        cert_link = render_link(cert_link)
        cert_link = urllib_parse.urljoin(request.application_url, cert_link)
    args = {
        'informal_username': informal_username,
        'support_email': support_email,
        'course_title': entry.title,
        'cert_link': cert_link,
        'brand_name': brand_name,
        'today': isodate.date_isoformat(datetime.datetime.now())
    }

    try:
        mailer = component.getUtility(ITemplatedMailer)
        mailer.queue_simple_html_text_email(
            'course_completed_email',
            subject=translate(_(u"You've completed ${title}!",
                                mapping={'title': entry.Title})),
            recipients=[email],
            template_args=args,
            request=request,
            text_template_extension='.mak')
    except Exception:  # pylint: disable=broad-except
        logger.exception("Cannot send course completion email to %s (%s)",
                         email, user.username)
        return False
    return True
