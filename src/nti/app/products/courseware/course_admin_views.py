#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views related to administration of courses.


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface
from zope import lifecycleevent

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutline


from pyramid import httpexceptions as hexc
from pyramid.view import view_config
from nti.appserver._view_utils  import AbstractAuthenticatedView

from nti.dataserver import authorization as nauth

from . import VIEW_CONTENTS
from . import VIEW_COURSE_ENROLLMENT_ROSTER
from . import VIEW_COURSE_ACTIVITY



from nti.contenttypes.courses.interfaces import is_instructed_by_name
from nti.contenttypes.courses.interfaces import ICourseInstance
from .interfaces import ICourseCatalog
from nti.externalization.interfaces import LocatedExternalDict

from nti.externalization.interfaces import ILocatedExternalSequence
from nti.externalization.externalization import to_external_object



import csv

from nti.ntiids import ntiids

from nti.dataserver.contenttypes.forums.ace import ForumACE

from nti.dataserver.contenttypes.forums.interfaces import IACLCommunityBoard
from nti.dataserver.contenttypes.forums.forum import ACLCommunityForum

from nti.dataserver.contenttypes.forums.post import CommunityHeadlinePost
from nti.dataserver.contenttypes.forums.topic import CommunityHeadlineTopic

from nti.appserver._view_utils import UploadRequestUtilsMixin

from nti.dataserver.users import Entity

from nti.dataserver.interfaces import IDataserverFolder
from collections import defaultdict

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='POST',
			 context=IDataserverFolder,
			 permission=nauth.ACT_COPPA_ADMIN, # XXX FIXME
			 name='LegacyCourseTopicCreator')
class CourseTopicCreationView(AbstractAuthenticatedView,UploadRequestUtilsMixin):
	"""
	POST a CSV file to create topics::

		course id, title, headline content

	We create and permission also all the boards and forums,
	one public and one private.

	.. note:: this rips heavily from forum_admit_views
		and simply forums.views.
	"""

	def __call__(self):

		body_content = self._get_body_content().split('\n')
		if len(body_content) == 1:
			body_content = body_content[0].split('\r')
		__traceback_info__ = body_content
		reader = csv.reader(body_content)
		rows = list(reader)
		__traceback_info__ = rows

		course_instance_ids = set()
		course_instance_ids_to_rows = defaultdict(list)
		for row in rows:
			course_instance_ids.add(row[0])
			course_instance_ids_to_rows[row[0]].append(row)

		catalog = component.getUtility(ICourseCatalog)

		def _create_forum(instance, forum_name, forum_readable):
			try:
				instructor = instance.instructors[0]
			except IndexError:
				logger.debug("Course %s has no instructors, not creating %s", instance, forum_name)
				return

			instructor = instructor.context # XXX implementation detail
			discussions = instance.Discussions

			if not IACLCommunityBoard.providedBy(discussions):
				interface.alsoProvides(discussions, IACLCommunityBoard)
			name = ntiids.make_specific_safe(forum_name)
			try:
				forum = discussions[name]
				logger.debug("Found existing forum %s", forum_name)
			except KeyError:
				forum = ACLCommunityForum()
				forum.creator = instructor if 'Open' not in forum_name else Entity.get_entity(forum_readable)
				acl = [ForumACE(Permissions=("All",), Entities=[instructor.username],Action='Allow'),
					   ForumACE(Permissions=("Read",),Entities=[forum_readable],Action='Allow')]
				forum.ACL = acl
				forum.title = forum_name
				discussions[name] = forum
				logger.debug('Created forum %s', forum)
				return forum.NTIID


		created_ntiids = list()
		for catalog_entry in catalog:
			if catalog_entry.StartDate.year != 2014:
				continue
			instance = ICourseInstance(catalog_entry)

			# Everybody should have announcements
			for forum_name, forum_readable  in (('Open Announcements', unicode(instance.LegacyScopes['public'])),
												('In-Class Announcements', unicode(instance.LegacyScopes['restricted']))):

				created_ntiid = _create_forum(instance, forum_name, forum_readable)
				if created_ntiid:
					created_ntiids.append(created_ntiid)


		for course_instance_id in course_instance_ids:
			logger.debug("making entries for %s", course_instance_id)
			catalog_entry = catalog[course_instance_id]
			__traceback_info__ = catalog_entry

			instance = ICourseInstance(catalog_entry)
			instructor = instance.instructors[0]
			instructor = instructor.context # XXX implementation detail
			discussions = instance.Discussions

			if not IACLCommunityBoard.providedBy(discussions):
				interface.alsoProvides(discussions, IACLCommunityBoard)

			for forum_name, forum_readable  in (('Open Discussions', unicode(instance.LegacyScopes['public'])),
												('In-Class Discussions', unicode(instance.LegacyScopes['restricted']))):
				created_ntiid = _create_forum(instance, forum_name, forum_readable)
				if created_ntiid:
					created_ntiids.append(created_ntiid)

				forum = discussions[ntiids.make_specific_safe(forum_name)]
				for row in course_instance_ids_to_rows[course_instance_id]:
					title = unicode(row[1], 'utf-8')
					content = unicode(row[2], 'utf-8')
					if title in forum:
						logger.debug("Found existing topic %s", title)

					name = ntiids.make_specific_safe(title)


					if name not in forum:
						post = CommunityHeadlinePost()
						post.title = title
						post.body = [content]

						topic = CommunityHeadlineTopic()
						topic.title = title
						topic.creator = instructor
						topic.description = title

						lifecycleevent.created(topic)
						forum[name] = topic

						post.__parent__ = topic
						post.creator = topic.creator
						topic.headline = post

						lifecycleevent.created(post)
						lifecycleevent.added(post)

						created_ntiids.append(topic.NTIID)
						logger.debug('Created topic %s with NTIID %s', topic, topic.NTIID)
		return created_ntiids
