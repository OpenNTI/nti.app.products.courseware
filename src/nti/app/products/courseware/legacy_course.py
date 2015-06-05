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

from urlparse import urljoin

from zope import interface
from zope import component
from zope.component.interfaces import IComponents

from zope.event import notify
from zope.lifecycleevent import IObjectAddedEvent

from zope.security.interfaces import IPrincipal

from zope.cachedescriptors.property import Lazy

from BTrees import OOBTree
from persistent import Persistent

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.common.property import CachedProperty

from nti.contenttypes.courses.courses import CourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.courses import CourseAdministrativeLevel
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel
from nti.contenttypes.courses.interfaces import CourseInstanceAvailableEvent

from nti.dataserver.users import User
from nti.dataserver.users import Entity
from nti.dataserver.users import Community
from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.dataserver.interfaces import ICommunity
from nti.dataserver.interfaces import IUseNTIIDAsExternalUsername

from nti.externalization.externalization import to_external_object

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider

from nti.schema.field import TextLine

from nti.wref.interfaces import IWeakRef

from .interfaces import ICourseCatalogLegacyContentEntry
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

	old_rendering = False # Some things were different with the courses produced for Fall 2013
	if not entry.StartDate or not entry.EndDate:
		# Hmm...something very fishy about this one...ancient legacy?
		logger.warn("Course info has no start date and/or duration: %s", entry)
		old_rendering = True
	else:
		old_rendering = entry.StartDate.year == 2013

	sig_lines = []
	for inst in entry.Instructors:
		sig_lines.append( inst.Name )
		sig_lines.append( inst.JobTitle )
		policy.extend_signature_for_instructor( inst, sig_lines )

		sig_lines.append( "" )
	del sig_lines[-1] # always at least one instructor. take off the last trailing line
	signature = '\n'.join( sig_lines )
	entry.InstructorsSignature = signature
	entry.ProviderDepartmentTitle = policy.department_title_for_entry(entry)

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

	else:
		purch_ntiid = make_ntiid( provider=provider, nttype='course', specific=purch_id )

	logger.debug("Purchasable '%s' was created for course using content package'%s'",
				 purch_ntiid, entry.ContentPackageNTIID)

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
		logger.info('Registering course %s/%s in site %s',
					purch_ntiid, entry.ContentPackageNTIID,
					policy.register_courses_in_components_named)
		# If they give us one, it MUST be non-persistent (programming error
		# otherwise). And anything we derive overrides what may have
		# been statically registered.
		assert not isinstance(components, Persistent)

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


	# Cache some lazy attributes /now/ while we now we have
	# access to the volatile parts of the content package:

	# ...Ensure we can parse the outline...
	getattr( the_course, 'Outline' )

	# ...and get the sharing scopes...
	# NOTE: The 'public' and restricted scopes must already exist,
	# otherwise they will be automatically created (public by definition
	# does)
	_update_scopes(the_course, purch_ntiid, entry.legacy_content_package)


	the_course.updateInstructors( entry )

	_update_vendor_info(the_course, entry.legacy_content_package.root)

	# Always let people know it's available so they can do any
	# synchronization work that needs to pull from the external
	# content into the database
	notify(CourseInstanceAvailableEvent(the_course))

from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo

def _update_vendor_info(course, bucket):
	# See also nti.contenttypes.courses._synchronizer
	vendor_json_key = bucket.getChildNamed('vendor_info.json')
	vendor_info = ICourseInstanceVendorInfo(course)
	if not vendor_json_key:
		vendor_info.clear()
		vendor_info.lastModified = 0
		vendor_info.createdTime = 0
	elif vendor_json_key.lastModified > vendor_info.lastModified:
		vendor_info.clear()
		vendor_info.update(vendor_json_key.readContentsAsJson())
		vendor_info.lastModified = vendor_json_key.lastModified
		vendor_info.createdTime = vendor_json_key.createdTime

from pyramid.traversal import find_interface

from .legacy_courses import get_scopes_from_course_element
from .legacy_courses import get_scopes_for_purchasable_ntiid

def _update_scopes(course, purchsable_ntiid, package): #pylint:disable=I0011,W0212
	scopes = course.SharingScopes
	# Bypass __setitem__ because we already have parents,
	# and we don't conform anyway
	if ES_PUBLIC not in scopes:
		scopes._SampleContainer__data[ES_PUBLIC] = find_interface(course, ICommunity)

	if ES_CREDIT not in scopes:
		legacy_scopes = get_scopes_for_purchasable_ntiid(purchsable_ntiid)
		if legacy_scopes is None:
			course_element = next(package._v_toc_node.iterchildren(tag='course'))
			legacy_scopes = get_scopes_from_course_element(course_element)
		if legacy_scopes is not None:
			restricted_id = legacy_scopes['restricted']
			restricted = Entity.get_entity(restricted_id) if restricted_id else None
			if restricted is not None:
				scopes._SampleContainer__data[ES_CREDIT] = restricted


	scopes.initScopes()

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

	if not IUseNTIIDAsExternalUsername.providedBy(community):
		interface.alsoProvides(community, IUseNTIIDAsExternalUsername)

	# Course instances live inside ICourseAdminLevels
	community_courses = ICourseAdministrativeLevel( community )
	if purch_id not in community_courses:
		community_courses[purch_id] = _LegacyCommunityBasedCourseInstance(entry.ContentPackageNTIID)

	result = community_courses[purch_id]
	return result

@interface.implementer(ILegacyCommunityBasedCourseInstance)
@component.adapter(ICommunity)
def _course_instance_for_community( community ):
	courses_for_community = ICourseAdministrativeLevel(community)
	assert len(courses_for_community) <= 1
	if len(courses_for_community):
		return list(courses_for_community.values())[0]

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

from nti.dataserver.interfaces import IEntityContainer
from nti.dataserver.contenttypes.forums.interfaces import ICommunityBoard

from nti.externalization.persistence import NoPickle

@NoPickle
class _LegacyCommunityBasedCourseInstanceFakeBundle(object):

	def __init__(self, content_packages):
		self.ContentPackages = content_packages

	def toExternalObject(self, *args, **kwargs):
		return {'ContentPackages': self.ContentPackages,
				'Class': 'ContentPackageBundle'}

from zope.schema.vocabulary import SimpleVocabulary

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.sharing import CourseInstanceSharingScopes
from nti.contenttypes.courses.interfaces import ENROLLMENT_SCOPE_VOCABULARY
from nti.contenttypes.courses.interfaces import ICourseInstanceSharingScopes


_LEGACY_ENROLLMENT_SCOPE_VOCABULARY = SimpleVocabulary(
	[ENROLLMENT_SCOPE_VOCABULARY.getTerm(ES_CREDIT),
	 ENROLLMENT_SCOPE_VOCABULARY.getTerm(ES_PUBLIC)])

@interface.implementer(ICourseInstanceSharingScopes)
@NoPickle
class _LegacyCommunityBasedCourseInstanceFakeSharingScopes(CourseInstanceSharingScopes):

	__name__ = 'SharingScopes'
	__external_class_name__ = 'CourseInstanceSharingScopes'

	def _vocabulary(self):
		# override to return a subset, the only
		# ones we support
		return _LEGACY_ENROLLMENT_SCOPE_VOCABULARY

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

	def __init__(self, content_package_ntiid):
		"""
		Create a new instance. We will look up the ``community_name``
		on demand.
		"""
		super(_LegacyCommunityBasedCourseInstance,self).__init__()

		self.ContentPackageNTIID = content_package_ntiid

	@CachedProperty
	def legacy_community(self):
		return self.SharingScopes[ES_PUBLIC]

	@CachedProperty
	def restricted_scope_entity(self):
		return self.SharingScopes[ES_CREDIT]

	@CachedProperty
	def restricted_scope_entity_container(self):
		"checking membership in this is pretty common, so caching it has measurable benefits"
		return IEntityContainer(self.restricted_scope_entity, ())

	def _make_sharing_scopes(self):
		return _LegacyCommunityBasedCourseInstanceFakeSharingScopes()

	@property
	def Discussions(self):
		return ICommunityBoard(self.legacy_community)

	@property
	def legacy_content_package(self):
		library = component.getUtility(IContentPackageLibrary)
		package = None
		try:
			package = library[self.ContentPackageNTIID]
		except KeyError:
			logger.exception('The content package for %s/%s is gone',
							 self, self.ContentPackageNTIID)
		return package

	@property
	def ContentPackageBundle(self):
		package = self.legacy_content_package
		if package is not None:
			packages = (package,)
		else:
			packages = ()
		return _LegacyCommunityBasedCourseInstanceFakeBundle(packages)

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
		if package is None:
			logger.warn("No content package found for %s/%s; no outline and other bad things may happen",
						self, self.ContentPackageNTIID)
		else:
			fill_outline_from_key(self._LegacyOutline, package.index, xml_parent_name='course')
		return self._LegacyOutline

	@Lazy
	def LegacyScopes(self):
		scopes = self.SharingScopes
		return {'public': scopes[ES_PUBLIC].NTIID,
				'restricted': scopes[ES_CREDIT].NTIID}

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
				ntiid = getattr(entry, 'ContentPackageNTIID', None)
				if ntiid == my_ntiid:
					self._v_catalog_entry = entry
					break
			if self._v_catalog_entry is None:
				logger.warn("Unable to find any catalog entry with ContentPackageNTIID %s",
							my_ntiid)
		return self._v_catalog_entry

	@property
	def instructors(self):
		if '_instructor_storage' in self.__dict__:
			return [IPrincipal(x()) for x in self._instructor_storage if x()]
		return ()

@interface.implementer(ICourseCatalogLegacyContentEntry)
@component.adapter(_LegacyCommunityBasedCourseInstance)
def _legacy_course_instance_to_catalog_entry(instance):
	result = instance.legacy_catalog_entry
	if result is None:
		logger.warn("Failed to find any legacy course catalog entry claiming the package %s",
					instance.ContentPackageNTIID)
	return result

from nti.dataserver.interfaces import IACLProvider
from nti.dataserver.interfaces import ALL_PERMISSIONS

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization_acl import ace_allowing
from nti.dataserver.authorization_acl import acl_from_aces

@interface.implementer(IACLProvider)
@component.adapter(_LegacyCommunityBasedCourseInstance)
class _LegacyCourseInstanceACLProvider(object):

	def __init__(self, context):
		self.context = context
		# TODO: This isn't right. What are instructor permissions?
		aces = [ace_allowing(x,ALL_PERMISSIONS) for x in self.context.instructors]
		aces.append( ace_allowing(self.context.legacy_community, ACT_READ ))
		self.__acl__ = acl_from_aces( aces )
