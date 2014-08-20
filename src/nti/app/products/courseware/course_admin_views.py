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
from zope.security.interfaces import IPrincipal

from pyramid.view import view_config
from pyramid import httpexceptions as hexc
from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.dataserver import authorization as nauth

from nti.contentfragments.interfaces import CensoredPlainTextContentFragment

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import ICourseInstancePublicScopedForum
from nti.contenttypes.courses.interfaces import ICourseInstanceForCreditScopedForum

import io
import csv

from nti.ntiids import ntiids

from nti.dataserver.contenttypes.forums.ace import ForumACE

from nti.dataserver.contenttypes.forums.forum import ACLCommunityForum
from nti.dataserver.contenttypes.forums.interfaces import IACLCommunityBoard
from nti.dataserver.contenttypes.forums.interfaces import IACLCommunityForum

from nti.dataserver.contenttypes.forums.post import CommunityHeadlinePost
from nti.dataserver.contenttypes.forums.topic import CommunityHeadlineTopic

from nti.externalization.internalization import update_from_external_object
from nti.app.externalization.view_mixins import UploadRequestUtilsMixin

from nti.dataserver.users import Entity

from nti.dataserver.interfaces import IDataserverFolder
from nti.dataserver import traversal
from collections import defaultdict

from .interfaces import NTIID_TYPE_COURSE_SECTION_TOPIC

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

				video = component.getUtility(component.IFactory, name="application/vnd.nextthought.embeddedvideo")()
				update_from_external_object(video, {'embedURL': vid_url, 'type': vid_type})
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
		for forum_name, forum_readable, forum_display_name, iface in self._forums_for_instance('Discussions', instance):
			created_ntiid = self._create_forum(instance, forum_name, forum_readable.NTIID,
											   # Always created by the public community
											   # (because legacy courses might have a DFL for the non-public)
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
				scope = row['DiscussionScope'].decode('utf-8') if 'DiscussionScope' in row else 'All'
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
						# id may not really be the right thing depending on if we're creating
						# at a course instance or subinstance...
						# XXX: This is assumming quite a bit about the way these work.
						ntiid = ntiids.make_ntiid(provider=ICourseCatalogEntry(instance).ProviderUniqueID,
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
			if catalog_entry.StartDate.year != 2014:
				continue
			instance = ICourseInstance(catalog_entry)

			# Everybody should have announcements, unless the vendor
			# info says otherwise
			for forum_name, forum_readable, forum_display_name, iface  in self._forums_for_instance('Announcements', instance):
				created_ntiid = self._create_forum(instance, forum_name,
												   forum_readable.NTIID, instance.SharingScopes['Public'].NTIID,
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
			created_ntiids.extend(self._create_topics_in_instance(instance, rows, catalog_entry.ProviderUniqueID))


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

# helper admin views

from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.appserver.interfaces import IUserService

from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY

from nti.dataserver.users import User
from nti.dataserver.interfaces import IUser

from nti.utils.maps import CaseInsensitiveDict

from .interfaces import ICoursesWorkspace
from .catalog_views import get_enrollments
from .catalog_views import do_course_enrollment

class AbstractCourseEnrollView(AbstractAuthenticatedView,
							   ModeledContentUploadRequestUtilsMixin):

	def readInput(self):
		values = super(AbstractCourseEnrollView, self).readInput()
		result = CaseInsensitiveDict(values)
		return result

	def parseCommon(self, values):
		# get / validate user
		username = values.get('username') or values.get('user')
		if not username:
			raise hexc.HTTPUnprocessableEntity(detail=_('No username'))

		user = User.get_user(username)
		if not user or not IUser.providedBy(user):
			raise hexc.HTTPNotFound(detail=_('User not found'))

		# get validate course entry
		ntiid = values.get('ntiid') or values.get('EntryNTIID') or \
				values.get('CourseEntryNIID') or values.get('ProviderUniqueID')
		if not ntiid:
			raise hexc.HTTPUnprocessableEntity(detail=_('No course entry identifier'))

		# get catalog entry
		try:
			catalog = component.getUtility(ICourseCatalog)
			catalog_entry = catalog.getCatalogEntry(ntiid)
		except LookupError:
			raise hexc.HTTPNotFound(detail=_('Catalog not found'))
		except KeyError:
			raise hexc.HTTPNotFound(detail=_('Course not found'))

		return (catalog_entry, user)

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='POST',
			 context=IDataserverFolder,
			 permission=nauth.ACT_COPPA_ADMIN,
			 name='AdminUserCourseEnroll')
class AdminUserCourseEnrollView(AbstractCourseEnrollView):

	def __call__(self):
		values = self.readInput()
		# get common
		catalog_entry, user = self.parseCommon(values)
		# get validate scope
		scope = values.get('scope', 'Public')
		if not scope or scope not in ENROLLMENT_SCOPE_VOCABULARY.by_token.keys():
			raise hexc.HTTPUnprocessableEntity(detail=_('Invalid scope'))

		service = IUserService(user)
		workspace = ICoursesWorkspace(service)
		parent = workspace['EnrolledCourses']

		# enroll
		result = do_course_enrollment(catalog_entry, user, scope,
									  parent=parent,
									  request=self.request)
		return result

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='POST',
			 context=IDataserverFolder,
			 permission=nauth.ACT_COPPA_ADMIN,
			 name='AdminUserCourseDrop')
class AdminUserCourseDropView(AbstractCourseEnrollView):

	def __call__(self):
		values = self.readInput()
		# get common
		catalog_entry, user = self.parseCommon(values)
		# get enrollments and drop
		course_instance  = ICourseInstance(catalog_entry)
		enrollments = get_enrollments(course_instance, self.request)
		enrollments.drop(user)
		return hexc.HTTPNoContent()

from nti.contenttypes.courses.sharing import add_principal_to_course_content_roles

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IShardLayout
from nti.dataserver.interfaces import IMutableGroupMember
from nti.dataserver.authorization import CONTENT_ROLE_PREFIX
from nti.dataserver.authorization import role_for_providers_content

from nti.externalization.interfaces import LocatedExternalDict

from .interfaces import ILegacyCommunityBasedCourseInstance

def _content_roles_for_course_instance(course):
	bundle = getattr(course, 'ContentPackageBundle', None)
	packs = getattr(bundle, 'ContentPackages', ())
	roles = []
	for pack in packs:
		ntiid = pack.ntiid
		ntiid = ntiids.get_parts(ntiid)
		provider = ntiid.provider
		specific = ntiid.specific
		roles.append(role_for_providers_content(provider, specific))
	return set(roles)

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=IDataserverFolder,
			 permission=nauth.ACT_COPPA_ADMIN,
			 name='CourseMissingContentRoles')
class CourseMissingContentRolesView(AbstractAuthenticatedView):


	def __call__(self):
		result = LocatedExternalDict()
		items = result['Items'] = LocatedExternalDict()

		dataserver = component.getUtility(IDataserver)

		# get all content roles
		user_info = {}
		users_folder = IShardLayout(dataserver).users_folder
		for user in users_folder.values():
			if not IUser.providedBy(user):
				continue
			principal = IPrincipal(user)
			membership = component.getAdapter(user,
											  IMutableGroupMember,
											  CONTENT_ROLE_PREFIX)
			user_info[principal] = set(membership.groups)

		# check catalogs
		catalog = component.getUtility(ICourseCatalog)
		for catalog_entry in catalog.iterCatalogEntries():
			course = ICourseInstance(catalog_entry, None)
			if course is None:
				continue

			course_roles = _content_roles_for_course_instance(course)
			if not course_roles: # no course roles
				continue

			if ILegacyCommunityBasedCourseInstance.providedBy(course):
				continue

			enrollments = ICourseEnrollments(course)
			course_list = items[catalog_entry.ntiid] = []
			for principal, roles in user_info.items():
				record = enrollments.get_enrollment_for_principal(principal)
				if record is None:
					continue
				# check if course roles are in user roles
				if not all(map(lambda x: x in roles, course_roles)):
					course_list.append(principal.id)
		# return
		return result

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='POST',
			 context=IDataserverFolder,
			 permission=nauth.ACT_COPPA_ADMIN,
			 name='AssignContentRolesView')
class AssignContentRolesView(AbstractCourseEnrollView):

	def __call__(self):
		values = self.readInput()
		catalog_entry, user = self.parseCommon(values)
		course = ICourseInstance(catalog_entry, None)
		if course is not None:
			add_principal_to_course_content_roles(user, course)
		else:
			raise hexc.HTTPUnprocessableEntity(detail=_('Invalid scope'))
		return hexc.HTTPNoContent()

from io import BytesIO
from zope.securitypolicy.interfaces import IPrincipalRoleMap
from nti.dataserver.users.interfaces import IUserProfile
from nti.contenttypes.courses.interfaces import ICourseSubInstance

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IDataserverFolder,
			 request_method='GET',
			 permission=nauth.ACT_MODERATE,
			 name='CourseRoles')
class CourseRolesView(AbstractAuthenticatedView,
					ModeledContentUploadRequestUtilsMixin):

	def __call__(self):
		catalog = component.getUtility(ICourseCatalog)

		bio = BytesIO()
		csv_writer = csv.writer(bio)
		csv_writer.writerow( ['Course', 'SubInstance', 'Role', 'Setting', 'User', 'Email'] )

		for catalog_entry in catalog.iterCatalogEntries():
			course = ICourseInstance( catalog_entry )

			if ICourseSubInstance.providedBy( course ):
				sub_name = course.__name__
				course_name = course.__parent__.__parent__.__name__
			else:
				course_name = course.__name__
				sub_name = ''

			roles = IPrincipalRoleMap( course, None )
			if roles is not None:
				for role_id, prin_id, setting in roles.getPrincipalsAndRoles():
					user = User.get_user( prin_id )
					profile = IUserProfile( user, None )
					email = getattr( profile, 'email', None )
					csv_writer.writerow( [ course_name, sub_name, role_id, setting, prin_id, email ] )

		response = self.request.response
		response.body = bio.getvalue()
		response.content_disposition = b'attachment; filename="CourseRoles.csv"'

		return response

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 context=IDataserverFolder,
			 request_method='GET',
			 permission=nauth.ACT_MODERATE,
			 name='CourseMultiEnrollView')
class CourseMultiEnrollView(AbstractAuthenticatedView,
							ModeledContentUploadRequestUtilsMixin):
	"""
	Check if any users are enrolled in multiple courses/subinstances.
	"""

	def __call__(self):
		catalog = component.getUtility(ICourseCatalog)

		bio = BytesIO()
		csv_writer = csv.writer(bio)
		csv_writer.writerow( ['Course', 'SubInstance', 'User', 'Email'] )

		for catalog_entry in catalog.iterCatalogEntries():
			course = ICourseInstance( catalog_entry )

			if not ICourseSubInstance.providedBy( course ):
				course_enrollments = ICourseEnrollments( course )
				course_enrollments = [x for x in course_enrollments.iter_enrollments()]
				course_enrollees = [x.Principal for x in course_enrollments]
				course_name = course.__name__

				for sub in course.SubInstances.values():
					sub_enrollments = ICourseEnrollments( sub )
					sub_enrollments = [x for x in sub_enrollments.iter_enrollments()]
					sub_enrollees = [x.Principal for x in sub_enrollments]

					for user in sub_enrollees:
						# Do we have to worry about multiple subinstance enrollments? (We don't)
						if user in course_enrollees:
							sub_name = sub.__name__
		 					profile = IUserProfile( user, None )
		 					email = getattr( profile, 'email', None )
		 					csv_writer.writerow( [ course_name, sub_name, user.username, email ] )

		response = self.request.response
		response.body = bio.getvalue()
		response.content_disposition = b'attachment; filename="CourseMultiEnrollView.csv"'

		return response
