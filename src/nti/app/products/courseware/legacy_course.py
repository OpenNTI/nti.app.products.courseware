#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Given legacy-style content packages and thus catalog
entries, create and register legacy-style courses
from them. In this context, legacy-style courses means at least
the following:

* They are bound tightly to one community, using its discussion forums

* Enrollment status is managed via a shop (store) purchasable


.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import isodate
from urlparse import urljoin

from zope import interface
from zope import component
from zope.component.interfaces import IComponents

from zope.lifecycleevent import IObjectAddedEvent
from zope.event import notify

from zope.security.interfaces import IPrincipal

from zope.cachedescriptors.property import Lazy

from BTrees import OOBTree
from persistent import Persistent

from nti.contentlibrary.interfaces import ILegacyCourseConflatedContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.courses import CourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.courses import CourseAdministrativeLevel
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel
from nti.contenttypes.courses.interfaces import ICourseCatalog

from nti.app.products.courseware.interfaces import ICourseCatalogLegacyContentEntry
from nti.app.products.courseware.interfaces import IPrincipalEnrollmentCatalog

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ICommunity
from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.wref.interfaces import IWeakRef

from nti.utils.property import CachedProperty

from nti.dataserver.users import User
from nti.dataserver.users import Entity
from nti.dataserver.users import Community

from nti.externalization.externalization import to_external_object

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider

from nti.store import course
from nti.store.interfaces import ICourse

from nti.schema.field import TextLine

from nti.contenttypes.courses.interfaces import CourseInstanceAvailableEvent
from .interfaces import ILegacyCommunityBasedCourseInstance

class ICourseCatalogLegacyEntryInstancePolicy(interface.Interface):
	"""
	Named utility registered by the name of the content package
	provider to fill in details.

	Some of these are optional and can be unimplemented.
	"""

	register_courses_in_components_named = TextLine(
		title="If given, the ICourse objects will be registered in this components",
		description="A non-persistent IComponents utility that will hold the courses."
		" Any matching courses will be unregistered from it.")

	def purch_id_for_entry(entry):
		"""
		The condensed identifier is the provider's unique ID, with all
		spaces stripped and no section number "ENGR 1515-900" ->
		"ENGR1515"

		This becomes part of the purchasables NTIID, and the picture
		names, and should match the community.
		"""

	def extend_signature_for_instructor(inst, sig_lines):
		"Optionally add any additional signature lines for the instructor."

	def department_title_for_entry(entry):
		"""Optionally modify the purchasable's title; otherwise this comes from the catalog's
		``ProviderDepartmentTitle``, which ultimately currently comes from the ``school`` value."""

@interface.implementer(ICourseCatalogLegacyEntryInstancePolicy)
class DefaultCourseCatalogLegacyEntryInstancePolicy(object):
	"""
	Default implementation of a policy. Can be extended or directly
	registered for a provider.
	"""

	register_courses_in_components_named = None

	def __init__(self):
		if not self.register_courses_in_components_named:
			logger.warn("Courses for %s will be registered globally", self)


	def purch_id_for_entry(self, entry):
		"""
		By default, the condensed identifier is the provider's unique
		 ID, with all spaces stripped and no section number
		"ENGR 1515-900" -> "ENGR1515"

		This becomes part of the purchasables NTIID,
		and the picture names, and should match the community.
		"""

		purch_id = entry.ProviderUniqueID.replace(' ','').split('-')[0]
		if entry.Term:
			purch_id += entry.Term.replace(' ', '').replace('-', '')

		if not entry.Communities or not entry.Communities[0].startswith( purch_id ):
			__traceback_info__ = purch_id, entry
			raise ValueError("Community name not as expected")

		return purch_id

	def department_title_for_entry(self, entry):
		return entry.ProviderDepartmentTitle

	def extend_signature_for_instructor(self, instructor, sig_lines):
		return

@component.adapter(ICourseCatalogLegacyContentEntry, IObjectAddedEvent)
def _register_course_purchasable_from_catalog_entry( entry, event ):
	"""
	When a catalog entry is added to the course catalog,
	if it is a legacy catalog entry, and there is a registered
	legacy policy for its provider, we will create and update
	a legacy course instance.
	"""
	provider = get_provider(entry.ContentPackageNTIID)
	policy = component.queryUtility(ICourseCatalogLegacyEntryInstancePolicy, name=provider)
	if policy is None:
		logger.debug( "Ignoring legacy catalog entry (%r) for provider (%s) without policy",
					  entry, provider )
		return

	assert len(entry.Communities) == 1
	purch_id = policy.purch_id_for_entry( entry )

	# We have to externalize the package to get correct URLs
	# to the course. They need to be absolute because there is no context
	# in the purchasable.
	ext_package = to_external_object( entry.legacy_content_package )
	icon = urljoin( ext_package['href'],
					'images/' + purch_id + '_promo.png' )
	thumbnail = urljoin( ext_package['href'],
						 'images/' + purch_id + '_cover.png' )
	# Temporarily also stash these things on the entry itself too
	# where they can be externalized in the course catalog
	entry.LegacyPurchasableIcon = icon
	entry.LegacyPurchasableThumbnail = thumbnail

	author = ' and '.join( [x.Name for x in entry.Instructors] )

	preview = False
	startdate = None
	old_rendering = False # Some things were different with the courses produced for Fall 2013
	if not entry.StartDate or not entry.EndDate:
		# Hmm...something very fishy about this one...ancient legacy?
		logger.warn("Course info has no start date and/or duration: %s", entry)
		old_rendering = True
	else:
		# We can probably do better with this. Plus we probably need a schedule
		# to update without restarting the server...
		preview = entry.Preview
		startdate = unicode(isodate.date_isoformat(entry.StartDate))

		old_rendering = entry.StartDate.year == 2013

	sig_lines = []
	for inst in entry.Instructors:
		sig_lines.append( inst.Name )
		sig_lines.append( inst.JobTitle )
		policy.extend_signature_for_instructor( inst, sig_lines )

		sig_lines.append( "" )
	del sig_lines[-1] # always at least one instructor. take off the last trailing line
	signature = '\\n\n'.join( sig_lines )

	# Now the NTIID of the purchasable. The "new" renderings use a consistent
	# NTIID based simply on the provider's unique id. But the old renderings
	# use an NTIID containing the title as well, and we can't change that...
	# except for social stats
	if old_rendering and purch_id != 'SOC3123': # with one exception
		# Old style is the title, minus whitespace and puncctuation, each word capitalized.
		# we could delegate this to the policy, but it shouldn't be
		# happening anymore
		ntiid_title = entry.Title.replace(',', '' )
		ntiid_title = ''.join( [x.capitalize() for x in ntiid_title.split()] )

		specific = purch_id + ntiid_title
		purch_ntiid = make_ntiid( provider=provider, nttype='course', specific=specific )

		items = (entry.ContentPackageNTIID,)
		if entry.ProviderUniqueID == 'PHIL 1203':
			# This one has a typo. Now, the server can deal with
			# multiple items for the purchasable, but it's not clear the
			# webapp can. so we HACK. Both of these can go away at the same time.
			entry._v_LegacyHackItemNTIID = "tag:nextthought.com,2011-10:OU-HTML-PHIL1203_HumanDestiny.phil_1203__philosophy_and_human_destiny,_east_and_west"
	else:
		purch_ntiid = make_ntiid( provider=provider, nttype='course', specific=purch_id )
		logger.debug("Purchasable '%s' was created for course '%s'",
					 purch_ntiid, entry.ContentPackageNTIID)
		items = (entry.ContentPackageNTIID,)

	the_course = course.create_course( ntiid=purch_ntiid,
									   title=entry.Title,
									   author=author,
									   name=entry.ProviderUniqueID,
									   description=entry.Description,
									   items=items,
									   icon=icon,
									   preview=preview,
									   thumbnail=thumbnail, # Not used
									   communities=entry.Communities,
									   featured=False,
									   department=policy.department_title_for_entry(entry),
									   signature=signature,
									   startdate=startdate,     # Legacy
									   EndDate=entry.EndDate,   # New
									   Duration=entry.Duration, # New
									   # Things ignored
									   amount=None,
									   currency=None,
									   fee=None,
									   license_=None,
									   discountable=False,
									   bulk_purchase=False )

	# Be careful what site we stick these in. Ideally we'd want to stick them in
	# site the library is loaded in in case we are configuring multiple libraries
	# for multiple sites. But in tests especially the current site might be a persistent
	# site, and purchasables aren't meant to be persisted (depending on when the added
	# events are fired).
	#
	# Because library setup happens in the dataserver's site, so that
	# we can make persistent changes, we explicitly use the global site, unless
	# some other IComponents is defined (which should be the non-persistent baseregistery.BaseComponents)
	if not policy.register_courses_in_components_named:
		components = component.getGlobalSiteManager()
		logger.info('Registering course %s globally for all sites', purch_ntiid)
	else:
		components = component.getGlobalSiteManager().getUtility(IComponents,
																 name=policy.register_courses_in_components_named)
		logger.info('Registering course %s in site %s',
					purch_ntiid, policy.register_courses_in_components_named)
		# If they give us one, it MUST be non-persistent (programming error
		# otherwise). And anything we derive overrides what may have
		# been statically registered.
		assert not isinstance(components, Persistent)
		if components.queryUtility( ICourse, name=purch_ntiid ):
			logger.warn( "Found existing ZCML course for %s; replacing", purch_ntiid )
			old_course = components.getUtility( ICourse, name=purch_ntiid )
			components.unregisterUtility( old_course, provided=ICourse, name=purch_ntiid )

		# Now move the catalog entry down to this level too.
		# It gets added by default globally but we need them to match
		# XXX: NOTE: We actually require this to be IWritableCourseCatalog!
		global_catalog = component.getGlobalSiteManager().getUtility(ICourseCatalog)
		local_catalog = components.queryUtility(ICourseCatalog)
		if local_catalog is None or local_catalog is global_catalog:
			local_catalog = type(global_catalog)()
			components.registerUtility(local_catalog, provided=ICourseCatalog)
			assert components.getUtility(ICourseCatalog) is local_catalog

		# By definition it is in the global
		global_catalog.removeCatalogEntry(entry, event=False)
		entry.__parent__ = None
		try:
			local_catalog.addCatalogEntry(entry, event=False)
		except ValueError: # A re-enumeration; typically tests
			logger.info("Found duplicate local course catalog entry %s", entry.ProviderUniqueID)
			local_catalog.removeCatalogEntry(entry, event=False)
			local_catalog.addCatalogEntry(entry, event=False)
		assert entry.__name__ not in global_catalog
		assert entry.__parent__ is local_catalog

	components.registerUtility( the_course, ICourse, name=purch_ntiid )

	# Ensure the referenced community exists if it doesn't, and
	# give it a course instance.

	# NOTE: This requires that we are operating in a transaction
	# with a real database.
	the_course = _course_instance_for_catalog_entry(entry)  # MAY send IObjectAdded if new

	# Defend against content package IDs changing
	if the_course.ContentPackageNTIID != entry.ContentPackageNTIID:
		__traceback_info__ = entry, the_course
		raise ValueError("The root NTIID for course %s has changed!", the_course)

	the_course.setCatalogEntry(entry)
	the_course.updateInstructors( entry )
	# Ensure we can parse the outline (this is not an optimization, to pre
	# cache before forking, as the volatile attributes are likely to get
	# ghosted)
	getattr( the_course, 'Outline' )

	# Always let people know it's available so they can do any
	# synchronization work that needs to pull from the external
	# content into the database
	notify(CourseInstanceAvailableEvent(the_course))

from nti.store.enrollment import get_enrollment
from nti.store.purchasable import get_all_purchasables
from nti.dataserver.datastructures import LastModifiedCopyingUserList

from .interfaces import ICourseCatalogLegacyContentEntry

@interface.implementer(ICourseInstance)
@component.adapter(ICourseCatalogLegacyContentEntry)
def _course_instance_for_catalog_entry(entry):
	if not entry.ContentPackageNTIID:
		return None

	provider = get_provider(entry.ContentPackageNTIID)
	policy = component.queryUtility(ICourseCatalogLegacyEntryInstancePolicy, name=provider)
	if policy is None:
		return None

	purch_id = policy.purch_id_for_entry(entry)
	community = Entity.get_entity( entry.Communities[0] )
	if community is None:
		community = Community.create_community( username=entry.Communities[0] )
		names = IFriendlyNamed(community)
		names.realname = purch_id
		names.alias = entry.Title

	# Course instances live inside ICourseAdminLevels
	community_courses = ICourseAdministrativeLevel( community )
	if purch_id not in community_courses:
		community_courses[purch_id] = _LegacyCommunityBasedCourseInstance(community.username,
																		  entry.ContentPackageNTIID)

	result = community_courses[purch_id]
	return result

@interface.implementer(ILegacyCommunityBasedCourseInstance)
@component.adapter(ICommunity)
def _course_instance_for_community( community ):
	course_catalog = component.getUtility(ICourseCatalog)
	for entry in course_catalog.iterCatalogEntries():
		course = ICourseInstance( entry )
		if getattr(course, 'legacy_community', None) == community:
			return course

@interface.implementer(ICourseInstance)
@component.adapter(ILegacyCourseConflatedContentPackage)
def _course_content_package_to_course(package):
	# We go via the defined adapter from the catalog entry
	course_catalog = component.getUtility(ICourseCatalog)
	for entry in course_catalog.iterCatalogEntries():
		if getattr(entry, 'ContentPackageNTIID', None) == package.ntiid:
			return ICourseInstance(entry, None)

from pyramid.traversal import find_interface
from nti.contentlibrary.interfaces import IContentUnit
from nti.contentlibrary.interfaces import IContentPackage

@interface.implementer(ICourseInstance)
@component.adapter(IContentUnit)
def _content_unit_to_course(unit):
	package = find_interface(unit,ILegacyCourseConflatedContentPackage)
	if package is not None:
		return ICourseInstance(package, None)

	package = find_interface(unit, IContentPackage)
	# XXX: We probably need to check and see who's enrolled
	# to find the most specific course instance to return
	# XXX: FIXME: This requires a one-to-one mapping
	course_catalog = component.getUtility(ICourseCatalog)
	for entry in course_catalog.iterCatalogEntries():
		instance = ICourseInstance(entry)
		try:
			packages = instance.ContentPackageBundle.ContentPackages
		except AttributeError:
			packages = (instance.legacy_content_package,)

		if package in packages:
			return instance

@interface.implementer(IPrincipalEnrollmentCatalog)
@component.adapter(IUser)
class _PurchaseHistoryEnrollmentStatus(object):
	"""
	Greps through the user's purchase history to find
	courses he is enrolled in, and matches their items
	to a an item in the course catalog and its course instance.
	"""

	def __init__( self, context ):
		self.context = context

	def iter_enrollments(self):
		# First, map the catalog content package NTIIDs to the catalog entry
		course_catalog = component.getUtility(ICourseCatalog)
		item_ntiid_to_entry = dict()
		for entry in course_catalog.iterCatalogEntries():
			ntiid = getattr(entry, 'ContentPackageNTIID', None)
			if ntiid:
				item_ntiid_to_entry[ntiid] = entry
			# XXX HACK for PHIL1203
			ntiid = getattr(entry, '_v_LegacyHackItemNTIID', None)
			if ntiid:
				item_ntiid_to_entry[ntiid] = entry

		# Now match up purchased things (enrolled courses) to these
		# content packages

		result = LastModifiedCopyingUserList()
		for the_purchasable in get_all_purchasables():
			enrollment = get_enrollment( self.context, the_purchasable.NTIID )
			if enrollment is None:
				continue

			for item in the_purchasable.Items:
				catalog_entry = item_ntiid_to_entry.get( item )
				if catalog_entry:
					result.append( ICourseInstance(catalog_entry) )
					result.updateLastModIfGreater( catalog_entry.lastModified )

		return result



@interface.implementer(ICourseAdministrativeLevel)
@component.adapter(ICommunity)
class _LegacyCommunityBasedCourseAdministrativeLevel(CourseAdministrativeLevel):
	"""
	An administrative level for old community based courses. We
	inherit, but reimplement much functionality.
	"""

	def __init__(self):
		super(_LegacyCommunityBasedCourseAdministrativeLevel,self).__init__()

# The key becomes the __name__, which is useful for traversal
from zope.annotation.factory import factory as an_factory
_LegacyCommunityBasedCourseAdministrativeLevelFactory = an_factory(_LegacyCommunityBasedCourseAdministrativeLevel,
																   key='LegacyCourses')

from nti.dataserver.contenttypes.forums.interfaces import ICommunityBoard
from nti.dataserver.interfaces import IEntityContainer

@interface.implementer(ILegacyCommunityBasedCourseInstance)
class _LegacyCommunityBasedCourseInstance(CourseInstance):
	"""
	A course instance that derives most of its data from
	the legacy structure used by courses structured around
	nothing more than a community or two.

	We derive from the main implementation but override most things.
	"""

	__external_class_name__ = 'LegacyCommunityBasedCourseInstance'

	# Mime type is location independent ATM
	mime_type = 'application/vnd.nextthought.courses.legacycommunitybasedcourseinstance'

	def __init__(self, community_name, content_package_ntiid):
		"""
		Create a new instance. We will look up the ``community_name``
		on demand.
		"""
		super(_LegacyCommunityBasedCourseInstance,self).__init__()
		self.__legacy_community_name = community_name

		if self.legacy_community is None:
			raise ValueError("The community doesn't exist", community_name)

		self.ContentPackageNTIID = content_package_ntiid

	@CachedProperty
	def legacy_community(self):
		return Entity.get_entity( self.__legacy_community_name )

	@CachedProperty
	def restricted_scope_entity(self):
		restricted_id = self.LegacyScopes.get('restricted')
		restricted = Entity.get_entity(restricted_id) if restricted_id else None
		return restricted

	@CachedProperty
	def restricted_scope_entity_container(self):
		"checking membership in this is pretty common, so caching it has measurable benefits"
		return IEntityContainer(self.restricted_scope_entity, ())

	@property
	def SharingScopes(self):
		"""
		We fake the real sharing scopes interface. Read-only.
		"""
		return {'Public': self.legacy_community,
				'ForCredit': self.restricted_scope_entity}

	@property
	def legacy_purchasable(self):
		# purchasables aren't persistent so could be cached,
		# but only if we find one, because it depends on the site policy
		for the_purchasable in get_all_purchasables():
			if not ICourse.providedBy(the_purchasable):
				continue

			for item in the_purchasable.Items:
				if item == self.ContentPackageNTIID:
					return the_purchasable

	@property
	def Discussions(self):
		return ICommunityBoard(self.legacy_community)

	@property
	def legacy_content_package(self):
		library = component.getUtility(IContentPackageLibrary)
		package = library[self.ContentPackageNTIID]
		return package

	@property
	def _course_toc_element(self):
		course_element = next(self.legacy_content_package._v_toc_node.iterchildren(tag='course'))
		return course_element

	@Lazy
	def _LegacyOutline(self):
		return self._make_Outline()

	@CachedProperty
	def Outline(self):
		from nti.contenttypes.courses._outline_parser import fill_outline_from_key
		# In the past, we used the non-persistent version and parsed it
		# from a cached ETree node each time a thread needed it.
		# However, now that we have reliable modification date tracking
		# everywhere, and a function that checks modification dates before
		# parsing, we can store a persistent version, simply
		# checking the date on each access as needed (the _v_toc_node didn't change,
		# though, ever, could that be an issue?)
		package = self.legacy_content_package
		fill_outline_from_key(self._LegacyOutline, package.index, xml_parent_name='course')
		return self._LegacyOutline

	@CachedProperty
	def LegacyScopes(self):
		result = {'public': None, 'restricted': None}
		course_element = self._course_toc_element
		for scope in course_element.xpath(b'scope'):
			type_ = scope.get(b'type', '').lower()
			entries = scope.xpath(b'entry')
			entity_id = entries[0].text if entries else None
			if type_ and entity_id:
				result[type_] = entity_id
		return result

	@CachedProperty
	def LegacyInstructorForums(self):
		# TODO: We should be the one creating these and ignoring what's in the ToC
		result = unicode(self._course_toc_element.get(b'instructorForum', ''))
		return result

	@Lazy
	def _instructor_storage(self):
		"A persistent set that holds weak references to entities"
		self._p_changed = True
		return OOBTree.Set()

	def updateInstructors(self, catalog_entry):
		"""
		Call this if the externally defined instructor information
		may have changed. We will examine the usernames
		in the catalog entry, and for every one that can
		be resolved to a real user, we will list it as an instructor.
		Anyone not listed will be removed.
		"""

		found_instructors = set()
		community = self.legacy_community
		for i in catalog_entry.Instructors:
			user = User.get_user(i.username) if i.username else None
			if user:
				found_instructors.add( user )
				user.record_dynamic_membership(community)


		if found_instructors:
			storage = self._instructor_storage
			storage.clear()
			storage.update( [IWeakRef(user) for user in found_instructors] )
		elif '_instructor_storage' in self.__dict__:
			# Clear it, but only if we had it
			self._instructor_storage.clear()

	_v_catalog_entry = None

	def setCatalogEntry(self, entry):
		self._v_catalog_entry = entry

	@property
	def legacy_catalog_entry(self):
		"""
		Because of a mismatch in names, it's hard to get the
		catalog entry for the course. This provides direct
		access.
		"""
		if self._v_catalog_entry is None:
			catalog = component.getUtility(ICourseCatalog)
			my_ntiid = self.ContentPackageNTIID
			for entry in catalog.iterCatalogEntries():
				ntiid = getattr( entry, 'ContentPackageNTIID', None)
				if ntiid == my_ntiid:
					self._v_catalog_entry = entry
					break
		return self._v_catalog_entry

	@property
	def instructors(self):
		if '_instructor_storage' in self.__dict__:
			return [IPrincipal(x()) for x in self._instructor_storage if x()]
		return ()

@interface.implementer(ICourseCatalogLegacyContentEntry)
@component.adapter(_LegacyCommunityBasedCourseInstance)
def _legacy_course_instance_to_catalog_entry(instance):
	return instance.legacy_catalog_entry

from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.dataserver.interfaces import ILengthEnumerableEntityContainer

@interface.implementer(ICourseEnrollments)
@component.adapter(_LegacyCommunityBasedCourseInstance)
class _LegacyCourseInstanceEnrollments(object):

	def __init__( self, context ):
		self.context = context

	def iter_enrollments(self):
		community = self.context.legacy_community
		instructor_usernames = {x.username for x in self.context.instructors}
		for member in community.iter_members():
			if member.username in instructor_usernames:
				continue
			yield member

	def count_enrollments(self):
		community = self.context.legacy_community
		container = ILengthEnumerableEntityContainer(community)
		i = len(container)

		# Now, in legacy courses, the instructors appear
		# enrolled because they are also a community
		# member. So account for that?
		i -= len(self.context.instructors)
		return i

	# Non-interface methods
	def count_legacy_open_enrollments(self):
		all_enrollments = self.count_enrollments()
		credit_enrollments = self.count_legacy_forcredit_enrollments()
		return all_enrollments - credit_enrollments

	def count_legacy_forcredit_enrollments(self):
		forcredit = self.context.restricted_scope_entity
		container = ILengthEnumerableEntityContainer(forcredit, ())
		i = len(container)
		# Off by owner maybe?
		return i

from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from pyramid.interfaces import IRequest
from nti.appserver.httpexceptions import HTTPNotFound

@interface.implementer(ICourseEnrollmentManager)
@component.adapter(_LegacyCommunityBasedCourseInstance, IRequest)
class _LegacyCourseInstanceEnrollmentManager(object):
	"""
	Uses the legacy views exactly as-is to ensure compatibility.

	Note that our action indications are not correct; we always
	return true.
	"""
	def __init__(self, context, request):
		self.context = context
		self.request = request

	@property
	def courseID(self):
		return self.context.legacy_purchasable.NTIID

	@property
	def username(self):
		return self.request.environ['REMOTE_USER']

	@property
	def user(self):
		return User.get_user(self.username)

	def _make_subrequest(self, path):
		if self.context.legacy_purchasable is None:
			raise HTTPNotFound("No such course in this site")

		body = {'courseID': self.courseID}
		subrequest = self.request.blank(path)
		subrequest.method = b'POST'
		subrequest.json = body
		subrequest.content_type = 'application/json'
		subrequest.possible_site_names = self.request.possible_site_names
		subrequest.environ[b'REMOTE_USER'] = self.username
		subrequest.environ[b'repoze.who.identity'] = self.request.environ['repoze.who.identity'].copy()

		return self.request.invoke_subrequest( subrequest )

	def enroll(self, user, scope=ES_PUBLIC):
		self._make_subrequest( '/dataserver2/store/enroll_course' )
		return True

	def drop(self, user):
		self._make_subrequest( '/dataserver2/store/unenroll_course' )
		return True

from nti.dataserver.interfaces import IACLProvider
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces
from nti.dataserver.authorization import ACT_READ
from nti.dataserver.interfaces import ALL_PERMISSIONS

@interface.implementer(IACLProvider)
@component.adapter(_LegacyCommunityBasedCourseInstance)
class _LegacyCourseInstanceACLProvider(object):

	def __init__(self, context):
		self.context = context
		# TODO: This isn't right. What are instructor permissions?
		aces = [ace_allowing(x,ALL_PERMISSIONS) for x in self.context.instructors]
		aces.append( ace_allowing(self.context.legacy_community, ACT_READ ))
		self.__acl__ = acl_from_aces( aces )
