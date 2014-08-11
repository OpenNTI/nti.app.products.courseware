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

from pyramid.view import view_config
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.dataserver import authorization as nauth

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.app.notabledata.interfaces import IUserNotableData

import csv

from nti.ntiids import ntiids

from nti.dataserver.contenttypes.forums.ace import ForumACE

from nti.dataserver.contenttypes.forums.interfaces import IACLCommunityBoard
from nti.dataserver.contenttypes.forums.interfaces import IACLCommunityForum
from nti.dataserver.contenttypes.forums.forum import ACLCommunityForum

from nti.dataserver.contenttypes.forums.post import CommunityHeadlinePost
from nti.dataserver.contenttypes.forums.topic import CommunityHeadlineTopic


from nti.app.externalization.view_mixins import UploadRequestUtilsMixin

from nti.dataserver.users import Entity

from nti.dataserver.interfaces import IDataserverFolder
from collections import defaultdict

from zope.securitypolicy.interfaces import IPrincipalRoleManager
from zope.securitypolicy.interfaces import Allow
from nti.contenttypes.courses.interfaces import RID_INSTRUCTOR

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


	def _create_forum(self, instance, forum_name, forum_readable_ntiid, forum_owner_ntiid):
		try:
			_ = instance.instructors[0]
		except IndexError:
			logger.debug("Course %s has no instructors, not creating %s", instance, forum_name)
			return

		instructors = [instructor.context for instructor in instance.instructors] # XXX implementation detail
		discussions = instance.Discussions

		acl = [ForumACE(Permissions=("All",), Entities=[i.username for i in instructors],Action='Allow'),
			   ForumACE(Permissions=("Read",),Entities=[forum_readable_ntiid],Action='Allow')]

		def _assign_acl(obj, iface):
			action = False
			if not iface.providedBy(obj):
				interface.alsoProvides(obj, iface)
				action = True
			if not hasattr(obj, 'ACL') or obj.ACL != acl:
				obj.ACL = acl
				action = True
			if action:
				logger.debug("Added/set ACL on existing object %s to %s", obj, acl)

		_assign_acl(discussions, IACLCommunityBoard)

		name = ntiids.make_specific_safe(forum_name)
		creator = Entity.get_entity(forum_owner_ntiid)
		try:
			forum = discussions[name]
			logger.debug("Found existing forum %s", forum_name)
			_assign_acl(forum, IACLCommunityForum)
			if forum.creator is not creator:
				forum.creator = creator
		except KeyError:
			forum = ACLCommunityForum()
			forum.creator = creator
			forum.title = forum_name
			_assign_acl(forum,IACLCommunityForum)
			discussions[name] = forum
			logger.debug('Created forum %s', forum)
			return forum.NTIID

	def _forums_for_instance(self, name, instance):
		return (('Open ' + name, instance.SharingScopes['Public'].NTIID),
				('In-Class ' + name, instance.SharingScopes['ForCredit'].NTIID))

	def _main_instructor(self, instance):
		roles = IPrincipalRoleManager(instance)
		for pid, setting in roles.getPrincipalsForRole(RID_INSTRUCTOR):
			if setting is Allow:
				user = Entity.get_entity(pid)
				if user is not None:
					return user

	def _create_topics_in_instance(self, instance, rows, ntprovider):
		try:
			instructor = instance.instructors[0]
		except IndexError:
			logger.debug("Course %s has no instructors", instance)
			return ()

		instructor = self._main_instructor(instance) or instructor.context # XXX implementation detail
		discussions = instance.Discussions

		created_ntiids = []
		for forum_name, forum_readable in self._forums_for_instance('Discussions', instance):
			created_ntiid = self._create_forum(instance, forum_name, forum_readable, instance.SharingScopes['Public'].NTIID)
			if created_ntiid:
				created_ntiids.append(created_ntiid)

			forum = discussions[ntiids.make_specific_safe(forum_name)]
			for row in rows:
				title = row[1].decode('utf-8', 'ignore')
				content = row[2].decode('utf-8', 'ignore')

				name = ntiids.make_specific_safe(title)
				logger.debug("Looking for %s in %s in %s", name, forum, instance)
				topic = None
				if name in forum:
					logger.debug("Found existing topic %s", title)
					topic = forum[name]
					if topic.creator != instructor:
						topic.creator = instructor
					if topic.headline is not None and topic.headline.creator != instructor:
						topic.headline.creator = instructor
				else:
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


					ntiid = topic.NTIID
					# TODO: For new-style courses, we'd like to generate a EnrolledCoursesSection
					# ntiid, but the OID forcing is hard to override.
					created_ntiids.append(ntiid)
					logger.debug('Created topic %s with NTIID %s', topic, ntiid)

				topic.publish()
				# Also make sure it's not considered notable for the instructor
				if topic.creator:
					notable = component.getMultiAdapter((topic.creator, self.request),
														IUserNotableData)
					notable.object_is_not_notable(topic)
		return created_ntiids


	def __call__(self):

		body_content = self._get_body_content().split(b'\n')
		if len(body_content) == 1:
			body_content = body_content[0].split(b'\r')
		__traceback_info__ = body_content
		reader = csv.reader(body_content)
		rows = list(reader)
		__traceback_info__ = rows

		course_instance_ids = set()
		course_instance_ids_to_rows = defaultdict(list)
		for row in rows:
			if not row or not row[0]:
				logger.warn("Ignoring row with no course ID: %s", row)
				continue

			course_instance_ids.add(row[0])
			course_instance_ids_to_rows[row[0]].append(row)

		catalog = component.getUtility(ICourseCatalog)

		created_ntiids = list()
		for catalog_entry in catalog.iterCatalogEntries():
			if catalog_entry.StartDate.year != 2014:
				continue
			instance = ICourseInstance(catalog_entry)

			# Everybody should have announcements
			for forum_name, forum_readable  in self._forums_for_instance('Announcements', instance):
				created_ntiid = self._create_forum(instance, forum_name, forum_readable, instance.SharingScopes['Public'].NTIID)
				if created_ntiid:
					created_ntiids.append(created_ntiid)


		for course_instance_id in course_instance_ids:
			logger.debug("making entries for %s", course_instance_id)
			catalog_entry = catalog.getCatalogEntry(course_instance_id)
			__traceback_info__ = catalog_entry

			instance = ICourseInstance(catalog_entry)
			__traceback_info__ = instance, catalog_entry

			rows = course_instance_ids_to_rows[course_instance_id]

			all_instances = (instance,) + tuple(instance.SubInstances.values())
			for i in all_instances:
				created_ntiids.extend(self._create_topics_in_instance(i, rows, catalog_entry.ProviderUniqueID))


		return created_ntiids


from .legacy_courses import _copy_enrollments_from_legacy_to_new

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IDataserverFolder,
			 permission=nauth.ACT_COPPA_ADMIN, # XXX FIXME
			 name='LegacyCourseEnrollmentMigrator')
class CourseEnrollmentMigrationView(AbstractAuthenticatedView):
	"""
	Migrates the enrollments from legacy placeholder courses to
	their new course instance. If any new course instance does not yet
	exist, it is skipped.

	Call this as a GET request for dry-run processing. POST to it
	to do it for real.

	Can be run as often as needed.
	"""

	def __call__(self):

		return _copy_enrollments_from_legacy_to_new(self.request)
