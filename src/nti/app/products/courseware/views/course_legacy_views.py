#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views related to administration of courses (legacy)

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import io
import csv
from collections import defaultdict

from zope import component
from zope import interface
from zope import lifecycleevent

from pyramid.view import view_config
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.externalization.view_mixins import UploadRequestUtilsMixin

from nti.contentfragments.interfaces import CensoredPlainTextContentFragment

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import ICourseInstancePublicScopedForum
from nti.contenttypes.courses.interfaces import ICourseInstanceForCreditScopedForum

from nti.dataserver import traversal
from nti.dataserver.interfaces import IDataserverFolder

from nti.dataserver import authorization as nauth

from nti.dataserver.users import Entity

from nti.dataserver.contenttypes.forums.ace import ForumACE
from nti.dataserver.contenttypes.forums.forum import ACLCommunityForum
from nti.dataserver.contenttypes.forums.post import CommunityHeadlinePost
from nti.dataserver.contenttypes.forums.topic import CommunityHeadlineTopic
from nti.dataserver.contenttypes.forums.interfaces import IACLCommunityBoard
from nti.dataserver.contenttypes.forums.interfaces import IACLCommunityForum

from nti.externalization.internalization import update_from_external_object

from nti.ntiids import ntiids

from ..interfaces import NTIID_TYPE_COURSE_SECTION_TOPIC

from ..legacy_courses import _copy_enrollments_from_legacy_to_new

## LEGACY views

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='POST',
			 context=IDataserverFolder,
			 permission=nauth.ACT_COPPA_ADMIN, # XXX FIXME
			 name='LegacyCourseTopicCreator')
class CourseTopicCreationView(AbstractAuthenticatedView,UploadRequestUtilsMixin):
	"""
	POST a CSV file to create topics.

	One header row is required, and then each row following
	corresponds to a particular course instance that will get a copy
	of that discussion. (Note that if both open and in-class
	discussions for that course are enabled, one row may translate
	into upto two discussions, depending on the ``scope`` argument.)
	In the documentation that follows, optional columns have their
	names surrounded by square brackets; those brackets should not be
	in the actual CSV file. The columns can be in any order in the CSV::

		NTIID, DiscussionTitle, [DiscussionScope], Body 1, [Body 2], ...


	NTIID
		The course catalog entry NTIID.
	DiscussionTitle
		The exact string that will make up the title of the discussion.
	DiscussionScope
		Optional columns. If it is missing or a row has the value
		``All``, then we create and permission both open and in-class
		versions of the discussion (if the course settings allow it).
		Otherwise, if the scope is ``Open`` or ``In-Class``, only discussions
		in the corresponding forum will be created (again, assuming the course
		settings allow it.)
	Body 1...Body n
		A series of numbered columns (up to 9 )that will make up the body of the discussion
		(the contents of the headline topic), in numeric order. At least one
		column is required and is required to not be empty for each row.

		If the column text starts with ``[ntivideo][TYPE]``, then the
		remainder of the string gives a URL to embed as a video, for
		example ``[ntivideo][kaltura]kaltura://1500101/1_vkxo2g66/``.
		(In the special case of a kaltura URL, the ``[TYPE]``
		specifier is optional.)

		Otherwise, the column is interpreted exactly as given.

	.. note:: this rips heavily from forum_admin_views
		and simply forums.views.
	"""


	def _create_forum(self, instance, forum_name, forum_readable_ntiid, forum_owner_ntiid,
					  forum_display_name=None,
					  forum_interface=interface.Interface):
		try:
			# In the past we really had to have instructors because they
			# were used as the creator; now we just require at least one so
			# that the ACL is semi-right to start with (otherwise it would be
			# totally wrong until the user ran the tool again)
			_ = instance.instructors[0]
		except IndexError:
			logger.debug("Course %s has no instructors, not creating %s",
						 instance, forum_name)
			return

		instructors = [instructor.context for instructor in instance.instructors] # XXX implementation detail
		discussions = instance.Discussions

		acl = [ForumACE(Permissions=("All",), Entities=[i.username for i in instructors], Action='Allow'),
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

		def _assign_iface(obj, iface):
			action = False
			if not iface.providedBy(obj):
				interface.alsoProvides(obj, iface)
			if action:
				logger.debug("Added interface to object %s %s", iface, obj)

		name = ntiids.make_specific_safe(forum_name)
		creator = Entity.get_entity(forum_owner_ntiid)
		try:
			forum = discussions[name]
			logger.debug("Found existing forum %s", forum_name)
			_assign_acl(forum, IACLCommunityForum)
			_assign_iface(forum,forum_interface)
			if forum.creator is not creator:
				forum.creator = creator
		except KeyError:
			forum = ACLCommunityForum()
			forum.creator = creator
			forum.title = forum_display_name or forum_name
			_assign_acl(forum,IACLCommunityForum)
			_assign_iface(forum,forum_interface)

			discussions[name] = forum
			logger.debug('Created forum %s', forum)
			return forum.NTIID

	def _forums_for_instance(self, name, instance):
		info = ICourseInstanceVendorInfo(instance)
		forum_types = info.get('NTI', {}).get('Forums', {})

		forums = []
		for prefix, key_prefix, scope, iface in (
				('Open', 'Open', 'Public', ICourseInstancePublicScopedForum),
				('In-Class', 'InClass', 'ForCredit', ICourseInstanceForCreditScopedForum)):
			has_key = 'Has' + key_prefix + name
			dpy_key = key_prefix + name + 'DisplayName'

			if forum_types.get(has_key, True):
				title = prefix + ' ' + name
				forums.append( (
					# This value CAN NOT CHANGE: Open Discussions,
					# In-Class Discussions. NTIIDS depend on it. Hence
					# the display name.
					title,
					instance.SharingScopes[scope],
					forum_types.get(dpy_key, title),
					iface) )
		return forums

	def _extract_content(self, row):
		# We expect 'Body 1', 'Body 2', etc.
		# If we start getting more than 10, we need to use natsort
		body_keys = [k for k in row if k.startswith('Body ')]
		body_keys = sorted(body_keys)

		body = list()
		for k in body_keys:
			content = row[k].decode('utf-8', 'ignore')
			# If they were on a mac, we might have \r instead of \n
			content = content.replace('\r', '\n')

			# Should it be a video?
			if content.startswith("[ntivideo]"):
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
				update_from_external_object(video, 
											{'embedURL': vid_url, 'type': vid_type})
				content = video
			elif content:
				# Avoid the automatic conversion that assumes the incoming
				# is meant to be HTML
				content = CensoredPlainTextContentFragment(content)

			if content:
				# Let some columns be blank on some rows
				body.append(content)
		return tuple(body)


	def _create_topics_in_instance(self, instance, rows, ntprovider):
		discussions = instance.Discussions

		created_ntiids = []
		_discussions = self._forums_for_instance('Discussions', instance)
		for forum_name, forum_readable, forum_display_name, iface in _discussions:
			created_ntiid = \
				self._create_forum(instance,
								   forum_name,
								   forum_readable.NTIID,
								   # Always created by the public community
								   # (because legacy courses might have a DFL
								   # for the non-public)
								   instance.SharingScopes['Public'].NTIID,
								   forum_display_name=forum_display_name,
								   forum_interface=iface)
			if created_ntiid:
				created_ntiids.append(created_ntiid)

			__traceback_info__ = {'known-forums': list(discussions),
								  'forum name': forum_name,
								  'forum display name': forum_display_name}
			try:
				forum = discussions[ntiids.make_specific_safe(forum_name)]
			except KeyError:
				logger.exception("No forum %s; no instructors?", forum_name)
				created_ntiids.append("WARNING: Missing forum %s in %s. No instructors?" %
									  (forum_name, traversal.resource_path(discussions)))
				continue

			for row in rows:
				title = row['DiscussionTitle'].decode('utf-8', 'ignore')
				name = ntiids.make_specific_safe(title)
				content = self._extract_content(row)
				scope = row['DiscussionScope'].decode('utf-8') \
						if 'DiscussionScope' in row else 'All'
				# Simplest thing to do is a prefix match on the forum_name, because
				# those are fixed
				if scope != 'All' and not forum_name.startswith(scope):
					logger.debug("Ignoring %s in %s because of scope mismatch %s",
								 name, forum, scope)
					continue

				logger.debug("Looking for %s in %s in %s", name, forum, instance)
				topic = None
				if name in forum:
					logger.debug("Found existing topic %s", title)
					topic = forum[name]
					if topic.creator != forum_readable:
						topic.creator = forum_readable
					if topic.headline is not None and topic.headline.creator != forum_readable:
						topic.headline.creator = forum_readable
				else:
					post = CommunityHeadlinePost()
					post.title = title
					post.body = content
					for i in post.body:
						if hasattr(i, '__parent__'):
							i.__parent__ = post

					topic = CommunityHeadlineTopic()
					topic.title = title
					topic.creator = forum_readable
					topic.description = title

					lifecycleevent.created(topic)
					forum[name] = topic

					post.__parent__ = topic
					post.creator = topic.creator
					topic.headline = post

					lifecycleevent.created(post)
					lifecycleevent.added(post)


					ntiid = topic.NTIID
					if ntiids.is_ntiid_of_type(ntiid, ntiids.TYPE_OID):
						# Got a new style course. Convert this into a useful
						# course relative reference. Of course, we have to pick
						# either section or global for the type and the provider unique
						# id may not really be the right thing depending on if we're
						# creating at a course instance or subinstance...
						# XXX: This is assumming quite a bit about the way these work.
						entry = ICourseCatalogEntry(instance)
						ntiid = ntiids.make_ntiid(provider=entry.ProviderUniqueID,
												 nttype=NTIID_TYPE_COURSE_SECTION_TOPIC,
												 specific=topic._ntiid_specific_part)
					created_ntiids.append(ntiid)
					logger.debug('Created topic %s with NTIID %s', topic, ntiid)

				topic.publish()

		return created_ntiids

	def __call__(self):
		body_content = self._get_body_content()

		__traceback_info__ = body_content
		# Use TextIOWrapper to try to get universal newline;
		# unfortunately, it doesn't deal with the Mac \r\r, but the only consequence
		# is that we get empty rows; sadly, we have to convert back to bytes for
		# the reader to read it.
		# Excel is going to be outputting in a windows encoding (also sadly)
		body_content = io.TextIOWrapper(io.BytesIO(body_content),
										encoding='windows-1252').read(None)
		body_content = io.BytesIO(body_content.encode('utf-8'))

		reader = csv.DictReader(body_content)
		rows = list(reader)
		__traceback_info__ = rows

		if not rows:
			return hexc.HTTPNoContent()

		course_instance_ids = set()
		course_instance_ids_to_rows = defaultdict(list)
		for row in rows:
			if not row.get("NTIID"):
				logger.debug("Ignoring row with no NTIID: %s", row)
				continue

			course_instance_ids.add(row['NTIID'])
			course_instance_ids_to_rows[row['NTIID']].append(row)

		catalog = component.getUtility(ICourseCatalog)

		created_ntiids = list()
		for catalog_entry in catalog.iterCatalogEntries():
			# FIXME Are we avoiding creating these for legacy 2013 courses?
			if catalog_entry.StartDate.year < 2014:
				continue
			instance = ICourseInstance(catalog_entry)

			# Everybody should have announcements, unless the vendor info says otherwise
			_announcements = self._forums_for_instance('Announcements', instance)
			for forum_name, forum_readable, forum_display_name, iface  in _announcements:
				created_ntiid = \
					self._create_forum(instance,
									   forum_name,
									   forum_readable.NTIID,
									   instance.SharingScopes['Public'].NTIID,
									   forum_display_name=forum_display_name,
									   forum_interface=iface)
				if created_ntiid:
					created_ntiids.append(created_ntiid)


		for course_instance_id in course_instance_ids:
			logger.debug("making entries for %s", course_instance_id)
			catalog_entry = catalog.getCatalogEntry(course_instance_id)
			__traceback_info__ = catalog_entry

			instance = ICourseInstance(catalog_entry)
			__traceback_info__ = instance, repr(catalog_entry)

			rows = course_instance_ids_to_rows[course_instance_id]
			# Note that we do not try to do this in sub-instances (if
			# any); administrators prefer to explicitly
			# list each instance
			topic_list = \
				self._create_topics_in_instance(instance, rows,
												catalog_entry.ProviderUniqueID)
			created_ntiids.extend(topic_list)


		return created_ntiids

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IDataserverFolder,
			 permission=nauth.ACT_COPPA_ADMIN, # XXX FIXME
			 name='LegacyCourseEnrollmentMigrator')
class LegacyCourseEnrollmentMigrationView(AbstractAuthenticatedView):
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
