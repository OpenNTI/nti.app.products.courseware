#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from collections import namedtuple

from zope import component

from zope.lifecycleevent import IObjectAddedEvent
from zope.lifecycleevent import IObjectModifiedEvent

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import ICourseInstancePublicScopedForum
from nti.contenttypes.courses.interfaces import ICourseInstanceForCreditScopedForum

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion 

NTI_FORUMS_PUBLIC = ('Open', 'Open', 'Public', ICourseInstancePublicScopedForum)
NTI_FORUMS_INCLASS = ('In-Class', 'InClass', 'ForCredit', ICourseInstanceForCreditScopedForum)

CourseForum = namedtuple('Forum', 'name scope display_name interface')

def get_vendor_info(context):
    course = ICourseInstance(context, None)
    result = ICourseInstanceVendorInfo(course, None) or {}
    return result
                             
def _forums_for_instance(context, name):
    forums = []
    info = get_vendor_info(context)
    instance = ICourseInstance(context, None)
    if instance is None:
        return forums

    forum_types = info.get('NTI', {}).get('Forums', {})
    for prefix, key_prefix, scope, iface in ( NTI_FORUMS_PUBLIC,
                                              NTI_FORUMS_INCLASS):
        has_key = 'Has' + key_prefix + name
        displayname_key = key_prefix + name + 'DisplayName'
        if forum_types.get(has_key, True):
            title = prefix + ' ' + name
            forum = CourseForum(title, 
                                instance.SharingScopes[scope],
                                forum_types.get(displayname_key, title),
                                iface)
            forums.append( forum )
    return forums
    
def announcements_forums(context):
    return _forums_for_instance(context, 'Announcements')

def discussions_forums(context):
    return _forums_for_instance(context, 'Discussions')

@component.adapter(ICourseDiscussion, IObjectAddedEvent)
def _discussions_added(record, event):
    pass
    
@component.adapter(ICourseDiscussion, IObjectModifiedEvent)
def _discussions_modified(record, event):
    pass
