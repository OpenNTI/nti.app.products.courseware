#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
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

from nti.base._compat import text_

from nti.base.interfaces import IFile

from nti.common.iterables import to_list

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussionTopic

from nti.contenttypes.courses.discussions.utils import get_topic_key
from nti.contenttypes.courses.discussions.utils import get_forum_scopes
from nti.contenttypes.courses.discussions.utils import is_nti_course_bundle
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

from nti.dataserver.interfaces import ICanvas
from nti.dataserver.interfaces import IACLProvider
from nti.dataserver.interfaces import ICanvasURLShape

from nti.dataserver.users.entity import Entity

from nti.externalization.internalization import update_from_external_object

from nti.ntiids.ntiids import TYPE_OID
from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import is_ntiid_of_type
from nti.ntiids.ntiids import make_provider_safe
from nti.ntiids.ntiids import make_specific_safe

from nti.publishing.interfaces import IDefaultPublished

from nti.traversal.traversal import find_interface

NTI_FORUMS_PUBLIC = (OPEN, OPEN, ES_PUBLIC, ICourseInstancePublicScopedForum)
NTI_FORUMS_FORCREDIT = (IN_CLASS, IN_CLASS_PREFIX,
                        ES_CREDIT, ICourseInstanceForCreditScopedForum)

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
        has_key = u'Has' + key_prefix + name
        displayname_key = key_prefix + name + u'DisplayName'
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
            # raise errors on malformed
            if content[0] == '[':
                vid_type_end = content.index(']')
                vid_type = content[1:vid_type_end]
                vid_url = content[vid_type_end + 1:]
            else:
                vid_url = content
                vid_type = u'kaltura'

            name = "application/vnd.nextthought.embeddedvideo"
            video = component.getUtility(component.IFactory, name=name)()
            update_from_external_object(video, {'embedURL': vid_url,
                                                'type': vid_type})
            content = video

        if content:
            result.append(content)
    return result


def extract_content(discussion):
    return _extract_content(discussion.body)


def announcements_forums(context):
    return _forums_for_instance(context, u'Announcements')


def discussions_forums(context):
    return _forums_for_instance(context, u'Discussions')


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
    # XXX: This seems fragile; we cannot adjust ACL easily for new
    # instructors/editors.
    aces = [ace_allowing(ROLE_ADMIN, ALL_PERMISSIONS)]

    # Instructors get all
    instructors = {
        IPrincipal(x, None) for x in get_course_instructors(course)
    }
    instructors.discard(None)
    for user in instructors:
        aces.append(ace_allowing(user, ALL_PERMISSIONS))

    # Editors get read perms
    editors = set(get_course_editors(course) or ())
    editors = editors - instructors
    editors.discard(None)
    for user in editors:
        aces.append(ace_allowing(user, ACT_READ))

    # Specified entities (e.g. students) get read permission
    entities = {
        IPrincipal(Entity.get_entity(e), None) for e in entities or ()
    }
    entities.discard(None)
    aces.extend([ace_allowing(e, ACT_READ) for e in entities])

    def _get_users(context):
        course_users = {
            IPrincipal(x, None) for x in get_course_instructors(context)
        }
        course_users.update(get_course_editors(context))
        course_users.discard(None)
        return course_users

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
    result = {u'discussions': {}, u'announcements': {}}
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

    _creator(result[u'discussions'], discussions_forums(course))
    _creator(result[u'announcements'], announcements_forums(course))
    return result
update_course_forums = create_course_forums


def create_topics(discussion, update=True, topics=None):
    course = ICourseInstance(discussion)
    all_forums = create_course_forums(course)
    discussions = all_forums[u'discussions']
    topics = dict() if topics is None else topics

    # get all scopes for topics
    scopes = get_discussion_mapped_scopes(discussion)
    if not scopes:
        logger.error("Cannot create discussions %s. Invalid scopes",
                     discussion)
        return ()

    # get/decode topic name
    name = get_topic_key(discussion)
    title = text_(discussion.title or u'')

    def set_post(post, title, content):
        post.title = title
        if content:
            post.body = content
        for i in post.body or ():
            if hasattr(i, '__parent__'):
                i.__parent__ = post
            # check for canvas objects
            if ICanvas.providedBy(i):
                for shape in i.shapeList or ():
                    if ICanvasURLShape.providedBy(shape) and IFile.providedBy(shape.file):
                        shape.file.__parent__ = shape.__parent__
    result = []
    content = extract_content(discussion)
    for scope in scopes:
        data = discussions.get(scope)
        if not data:
            logger.warn("No forum for scope %s was found", scope)
            continue
        _, forum = data

        created = True
        creator = course.SharingScopes[scope]
        if name in forum:
            topic = forum[name]
            if not update:
                continue
            logger.debug('Found existing topic "%s" in "%s"',
                         title, forum.title)
            if topic.creator != creator:
                topic.creator = creator
            if topic.headline is not None and topic.headline.creator != creator:
                topic.headline.creator = creator

            post = topic.headline
            set_post(post, title, content)
            lifecycleevent.modified(post)
            created = False
        else:
            # create post
            post = CommunityHeadlinePost()
            set_post(post, title, content)
            # create topic
            topic = CommunityHeadlineTopic()
            topic.title = title
            topic.creator = creator
            topic.description = title

            lifecycleevent.created(topic)
            forum[name] = topic
            # take ownership
            post.__parent__ = topic
            post.creator = topic.creator
            topic.headline = post
            # raise events and get intid
            lifecycleevent.created(post)
            lifecycleevent.added(post)
            logger.info('Topic "%s" has been created in forum "%s"',
                        title, forum.title)

        if is_nti_course_bundle(discussion):
            if not getattr(topic, 'discussion_id', None):
                topic.discussion_id = discussion.id  # save discusion id
            if not ICourseDiscussionTopic.providedBy(topic):
                interface.alsoProvides(topic, ICourseDiscussionTopic)

        # check ntiid
        ntiid = topic.NTIID
        if is_ntiid_of_type(ntiid, TYPE_OID):
            # Got a new style course. Convert this into a useful
            # course relative reference. Of course, we have to pick
            # either section or global for the type and the provider unique
            # id may not really be the right thing depending on if we're
            # creating at a course instance or subinstance...
            # XXX: This is assumming quite a bit about the way these work.
            entry = ICourseCatalogEntry(course)
            provider = make_provider_safe(entry.ProviderUniqueID)
            ntiid = make_ntiid(provider=provider,
                               nttype=NTIID_TYPE_COURSE_SECTION_TOPIC,
                               specific=topic._ntiid_specific_part)
            logger.debug('%s topic %s with NTIID %s',
                         ('Created' if created else 'Updated'), topic, ntiid)
        result.append(ntiid)
        topics[ntiid] = topic
        # always publish
        topic.publish()
        # mark
        if not IDefaultPublished.providedBy(topic):
            interface.alsoProvides(topic, IDefaultPublished)
    return result
