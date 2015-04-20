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
from zope import interface

from zope.lifecycleevent import IObjectAddedEvent
from zope.lifecycleevent import IObjectModifiedEvent

from zope.security.interfaces import IPrincipal

from nti.common.iterables import to_list

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import ICourseInstancePublicScopedForum
from nti.contenttypes.courses.interfaces import ICourseInstanceForCreditScopedForum

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussion 

from nti.dataserver.users import Entity
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.interfaces import ALL_PERMISSIONS
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.contenttypes.forums.forum import CommunityForum

from nti.ntiids.ntiids import make_specific_safe

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

def get_acl(course, *entities):
	# Our instance instructors get all permissions.
	instructors = [i for i in course.instructors or ()]
	aces = [ace_allowing( i, ALL_PERMISSIONS ) for i in instructors]
	
	# specifed entities (e.g. students) get read permission 
	entities = {IPrincipal(Entity.get_entity(e), None) for e in entities or ()}
	entities.discard(None)
	aces.extend([ace_allowing( i, ACT_READ ) for e in entities])
	
	# Subinstance instructors get the same permissions as their students.
	for subinstance in course.SubInstances.values():
		instructors = [i for i in subinstance.instructors or ()]
		aces.extend([ace_allowing( i, ACT_READ ) for i in instructors])
	
	acl = acl_from_aces(aces)
	return acl
	
def create_forum(course, name, owner, display_name=None, entities=None, implement=None):
	discussions = course.Discussions
	entities = to_list(entities, ())
	acl = get_acl( course, *entities)
	
	CommunityForum
	safe_name = make_specific_safe(name)
	creator = Entity.get_entity(owner)
	try:
		forum = discussions[safe_name]
		forum.__acl__ = acl   
		if forum.creator is not creator:
			forum.creator = creator
	except KeyError:
		forum = CommunityForum()
		forum.creator = creator
		forum.title = display_name or name
		discussions[safe_name] = forum
		logger.debug('Created forum %s', forum)
	
	## udpate ACL
	old_acl = getattr(forum, '__acl__', None)
	if old_acl != acl:
		forum.__acl__ = acl
	if implement is not None:
		interface.alsoProvides(forum, implement)
	return forum

def create_course_forums(context):
	result = []
	course = ICourseInstance(context)
	
	def _creator(forums=()):
		for forum in forums:
			created = create_forum(course,
								   name=forum.name,
								   display_name=forum.display_name,
								   entities=[forum.scope.NTIID],
								   implement=forum.interface,
								   ##  Always created by the public community
								   owner=course.SharingScopes['Public'].NTIID)
			result.append(created)
		
	_creator ( discussions_forums(course) )
	_creator ( announcements_forums(course) )
	return result

@component.adapter(ICourseDiscussion, IObjectAddedEvent)
def _discussions_added(record, event):
	pass
	
@component.adapter(ICourseDiscussion, IObjectModifiedEvent)
def _discussions_modified(record, event):
	pass
