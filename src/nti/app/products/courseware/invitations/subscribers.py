#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import os
import isodate
import datetime

from urllib import urlencode
from urlparse import urljoin

from zope import component

from zope.dottedname import resolve as dottedname

from zope.i18n import translate

from pyramid.threadlocal import get_current_request

from nti.app.products.courseware import MessageFactory as _
from nti.app.products.courseware import ACCEPT_COURSE_INVITATIONS

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IJoinCourseInvitation

from nti.dataserver.users import User

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.invitations.interfaces import IInvitationSentEvent

from nti.mailer.interfaces import ITemplatedMailer

from nti.ntiids.ntiids import find_object_with_ntiid


def get_ds2(request):
    try:
        result = request.path_info_peek() if request else None
    except AttributeError:  # in unit test we may see this
        result = None
    return result or "dataserver2"


def get_policy_package():
    policy = component.getUtility(ISitePolicyUserEventListener)
    return getattr(policy, 'PACKAGE', None)


def get_template_and_package(entry, base_template, default_package=None):
    package = get_policy_package()
    if not package:
        return base_template, default_package

    package = dottedname.resolve(package)
    provider_unique_id = entry.ProviderUniqueID.replace(' ', '').lower()
    full_provider_id = provider_unique_id.replace('-', '')
    template = full_provider_id + "_" + base_template

    path = os.path.join(os.path.dirname(package.__file__), 'templates')
    if not os.path.exists(os.path.join(path, template + ".pt")):
        # Full path doesn't exist; Drop our specific id part and try that
        provider_unique_prefix = provider_unique_id.split('-')[0]
        provider_unique_prefix = provider_unique_prefix.split('/')[0]
        template = provider_unique_prefix + "_" + base_template
        if not os.path.exists(os.path.join(path, template + ".pt")):
            template = base_template
    if template == base_template:
        package = default_package
    return template, package


def send_invitation_email(invitation,
                          sender,
                          receiver_name,
                          receiver_email,
                          receiver_username=None,
                          message=None,
                          request=None):

    if not request or not receiver_email:
        logger.warn("Not sending an invitation email because of no email or request")
        return False

    course = ICourseInstance(find_object_with_ntiid(invitation.course), None)
    if not ICourseInstance.providedBy(course):
        logger.warn("Not sending an invitation email because course could not be found")
        return False

    entry = ICourseCatalogEntry(course)
    template = 'course_invitation_email'
    template, package = get_template_and_package(entry, template)

    policy = component.getUtility(ISitePolicyUserEventListener)
    support_email = getattr(policy, 'SUPPORT_EMAIL', 'support@nextthought.com')
    brand = getattr(policy, 'BRAND', 'NextThought')
    brand_tag = 'Presented by NextThought'
    if brand.lower() != 'nextthought':
        brand_tag = 'Presented by %s and NextThought' % brand

    names = IFriendlyNamed(sender)
    informal_username = names.alias or names.realname or sender.username

    params = {'code': invitation.code}
    query = urlencode(params)
    url = '/%s/Objects/%s/%s?%s' % (get_ds2(request),
                                    entry.ntiid,
                                    ACCEPT_COURSE_INVITATIONS,
                                    query)
    redemption_link = urljoin(request.application_url, url)
    receiver_name = receiver_name or receiver_username
    args = {
        'sender_name': informal_username,
        'receiver_name': receiver_name,
        'support_email': support_email,
        'course_title': entry.title,
        'invitation_code': invitation.code,
        'invitation_message': message,
        'redemption_link': redemption_link,
        'brand': brand,
        'brand_tag': brand_tag,
        'today': isodate.date_isoformat(datetime.datetime.now())
    }

    try:
        mailer = component.getUtility(ITemplatedMailer)
        mailer.queue_simple_html_text_email(
            template,
            subject=translate(_(u"You're invited to ${title}",
                                mapping={'title': entry.Title})),
            recipients=[receiver_email],
            template_args=args,
            request=request,
            package=package,
            text_template_extension='.mak')
    except Exception:
        logger.exception("Cannot send course invitation email to %s",
                         receiver_email)
        return False
    return True


@component.adapter(IJoinCourseInvitation, IInvitationSentEvent)
def _on_invitation_sent(invitation, event):
    request = getattr(event, 'request', None) or get_current_request()
    sender = User.get_user(invitation.sender)
    send_invitation_email(invitation,
                          sender=sender,
                          receiver_name=invitation.name,
                          receiver_email=invitation.email,
                          receiver_username=invitation.receiver,
                          message=invitation.message,
                          request=request)
