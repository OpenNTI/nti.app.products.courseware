#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six
from collections import namedtuple

from zope import component
from zope import interface
from zope import lifecycleevent

from zope.security.interfaces import IPrincipal

from nti.app.products.courseware.interfaces import NTIID_TYPE_COURSE_SECTION_TOPIC

from nti.app.products.courseware.utils import get_vendor_info

from nti.common.iterables import to_list

from nti.contenttypes.courses.discussions.utils import get_topic_key
from nti.contenttypes.courses.discussions.utils import get_course_for_discussion
from nti.contenttypes.courses.discussions.utils import get_discussion_mapped_scopes

from nti.contenttypes.courses.interfaces import OPEN
from nti.contenttypes.courses.interfaces import IN_CLASS
from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import IN_CLASS_PREFIX

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstancePublicScopedForum
from nti.contenttypes.courses.interfaces import ICourseInstanceForCreditScopedForum

from nti.contenttypes.courses.utils import get_course_editors
from nti.contenttypes.courses.utils import get_course_instructors
from nti.contenttypes.courses.utils import get_course_subinstances

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ROLE_ADMIN

from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

from nti.dataserver.contenttypes.forums.forum import CommunityForum
from nti.dataserver.contenttypes.forums.post import CommunityHeadlinePost
from nti.dataserver.contenttypes.forums.topic import CommunityHeadlineTopic

from nti.dataserver.interfaces import ACE_DENY_ALL
from nti.dataserver.interfaces import ACE_ACT_ALLOW
from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.interfaces import IACLProvider
from nti.dataserver.interfaces import IDefaultPublished

from nti.dataserver.users import Entity

from nti.externalization.internalization import update_from_external_object

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import is_ntiid_of_type
from nti.ntiids.ntiids import make_provider_safe
from nti.ntiids.ntiids import make_specific_safe

from nti.traversal.traversal import find_interface

NTI_FORUMS_PUBLIC = (OPEN, OPEN, ES_PUBLIC, ICourseInstancePublicScopedForum)
NTI_FORUMS_FORCREDIT = (IN_CLASS, IN_CLASS_PREFIX, ES_CREDIT, ICourseInstanceForCreditScopedForum)

CourseForum = namedtuple('Forum', 'name scope display_name interface')

def get_forum_types(context):
	info = get_vendor_info(context)
	result = info.get('NTI', {}).get('Forums', {})
	return result

def auto_create_forums(context):
	forum_types = get_forum_types(context)
	result = forum_types.get('AutoCreate', False)
	return result
_auto_create_forums = auto_create_forums

def _forums_for_instance(context, name):
	forums = []
	forum_types = get_forum_types(context)
	instance = ICourseInstance(context, None)
	if instance is None:
		return forums

	for prefix, key_prefix, scope, iface in (NTI_FORUMS_PUBLIC, NTI_FORUMS_FORCREDIT):
		has_key = 'Has' + key_prefix + name
		displayname_key = key_prefix + name + 'DisplayName'
		if forum_types.get(has_key):
			title = prefix + ' ' + name
			forum = CourseForum(title,
								instance.SharingScopes[scope],
								forum_types.get(displayname_key, title),
								iface)
			forums.append(forum)
	return forums

def _extract_content(body=()):
	result = list()
	for content in body or ():
		# Should it be a video?
		if isinstance(content, six.string_types) and content.startswith("[ntivideo]"):
			content = content[len("[ntivideo]"):]
			# A type, or kaltura?
			# raise erros on malformed
			if content[0] == '[':
				vid_type_end = content.index(']')
				vid_type = content[1:vid_type_end]
				vid_url = content[vid_type_end + 1:]
			else:
				vid_url = content
				vid_type = 'kaltura'

			name = "application/vnd.nextthought.embeddedvideo"
			video = component.getUtility(component.IFactory, name=name)()
			update_from_external_object(video, {'embedURL': vid_url, 'type': vid_type})
			content = video

		if content:
			result.append(content)
	result = tuple(result)
	return result

def extract_content(discussion):
	return _extract_content(discussion.body)

def announcements_forums(context):
	return _forums_for_instance(context, 'Announcements')

def discussions_forums(context):
	return _forums_for_instance(context, 'Discussions')

def get_forum_scopes(forum):
	result = None
	course = find_interface(forum, ICourseInstance, strict=False)
	m = {v.NTIID:k for k, v in course.SharingScopes.items()} if course else {}
	if hasattr(forum, '__entities__'):
		result = {m[k] for k, v in m.items() if k in forum.__entities__}
	elif hasattr(forum, '__acl__'):
		result = set()
		for ace in forum.__acl__:
			if IPrincipal(ace.actor).id in m and ace.action == ACE_ACT_ALLOW:
				result.add(m[k])
	return result or ()

def get_forums_for_discussion(discussion, context=None):
	result = {}
	scopes = get_discussion_mapped_scopes(discussion)
	course = get_course_for_discussion(discussion, context=context)
	if course is not None and scopes:
		# find all forums for which the discussion has access
		for k, v in course.Discussions.items():
			forum_scopes = get_forum_scopes(v)
			if scopes.intersection(forum_scopes):
				result[k] = v
		return result
	return result

def get_acl(course, *entities):
	# XXX: This seems fragile; we cannot adjust ACL easily for new instructors/editors.
	aces = [ ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS) ]

	def _get_users(context):
		course_users = set(IPrincipal(x, None) for x in get_course_instructors(context))
		course_users.update(get_course_editors(context))
		course_users.discard(None)
		return course_users

	for user in _get_users(course):
		aces.append(ace_allowing(user, ALL_PERMISSIONS))

	# Specified entities (e.g. students) get read permission
	entities = {IPrincipal(Entity.get_entity(e), None) for e in entities or ()}
	entities.discard(None)
	aces.extend([ace_allowing(e, ACT_READ) for e in entities])

	# Subinstance instructors/editors get READ access.
	for subinstance in get_course_subinstances(course):
		for user in _get_users(subinstance):
			aces.append(ace_allowing(user, ACT_READ))

	aces.append(ACE_DENY_ALL)
	acl = acl_from_aces(aces)
	return acl

def create_forum(course, name, owner, display_name=None, entities=None, implement=None):
	discussions = course.Discussions
	entities = to_list(entities, ())
	acl = get_acl(course, *entities)

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
		logger.info('Created forum %s', forum)

	# Update ACL
	old_acl = getattr(forum, '__acl__', None)
	if old_acl != acl:
		forum.__acl__ = acl
	if acl:
		interface.alsoProvides(forum, IACLProvider)

	# save entities
	forum.__entities__ = {str(x) for x in entities}
	# update interface
	if implement is not None:
		interface.alsoProvides(forum, implement)
	return safe_name, forum

def create_course_forums(context):
	result = {'discussions':{}, 'announcements':{}}
	course = ICourseInstance(context)

	def _creator(data, forums=()):
		for forum in forums:
			entities = [forum.scope.NTIID]
			name, created = create_forum(course,
										 name=forum.name,
										 display_name=forum.display_name,
										 entities=entities,
										 implement=forum.interface,
										 owner=forum.scope.NTIID)
			data[forum.scope.username] = (name, created)

	_creator(result['discussions'], discussions_forums(course))
	_creator(result['announcements'], announcements_forums(course))
	return result
update_course_forums = create_course_forums

def create_topics(discussion):
	course = ICourseInstance(discussion)
	all_fourms = create_course_forums(course)
	discussions = all_fourms['discussions']

	# get all scopes for topics
	scopes = get_discussion_mapped_scopes(discussion)
	if not scopes:
		logger.error("Cannot create discussions %s. Invalid scopes", discussion)
		return ()

	# get/decode topic name
	name = get_topic_key(discussion)
	title = discussion.title
	if not title:
		title = u''
	elif not isinstance(title, unicode):
		title = title.decode('utf-8', 'ignore')

	def _set_post(post, title, content):
		post.title = title
		if content:
			post.body = content
		for i in post.body or ():
			if hasattr(i, '__parent__'):
				i.__parent__ = post

	result = []
	content = extract_content(discussion)
	for scope in scopes:
		data = discussions.get(scope)
		if not data:
			logger.debug("No forum for scope %s was found", scope)
			continue
		_, forum = data

		created = True
		creator = course.SharingScopes[scope]
		if name in forum:
			logger.debug('Found existing topic "%s" in "%s"',
						 title, forum.title)
			topic = forum[name]
			if topic.creator != creator:
				topic.creator = creator
			if topic.headline is not None and topic.headline.creator != creator:
				topic.headline.creator = creator

			post = topic.headline
			_set_post(post, title, content)
			lifecycleevent.modified(post)
			created = False
		else:
			post = CommunityHeadlinePost()
			_set_post(post, title, content)

			topic = CommunityHeadlineTopic()
			topic.title = title
			topic.creator = creator
			topic.description = title

			lifecycleevent.created(topic)
			forum[name] = topic

			post.__parent__ = topic
			post.creator = topic.creator
			topic.headline = post

			lifecycleevent.created(post)
			lifecycleevent.added(post)
			logger.info('Topic "%s" has been created in fourm "%s"',
						title, forum.title)

		ntiid = topic.NTIID
		if is_ntiid_of_type(ntiid, TYPE_OID):
			# Got a new style course. Convert this into a useful
			# course relative reference. Of course, we have to pick
			# either section or global for the type and the provider unique
			# id may not really be the right thing depending on if we're
			# creating at a course instance or subinstance...
			# XXX: This is assumming quite a bit about the way these work.
			entry = ICourseCatalogEntry(course)
			ntiid = make_ntiid(provider=make_provider_safe(entry.ProviderUniqueID),
							   nttype=NTIID_TYPE_COURSE_SECTION_TOPIC,
							   specific=topic._ntiid_specific_part)
			logger.debug('%s topic %s with NTIID %s',
						 ('Created' if created else 'Updated'), topic, ntiid)
		result.append(ntiid)
		# always publish
		topic.publish()
		# mark
		if not IDefaultPublished.providedBy(topic):
			interface.alsoProvides(topic, IDefaultPublished)
	return result
