#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Given legacy-style content packages and thus catalog
entries, create and register legacy-style courses
from them. In this context, legacy-style courses means at least
the following:

* They are bound tightly to one community, using its discussion forums

* Enrollment status is managed via a shop (store) purchasable


$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from urlparse import urljoin
import isodate

from zope import interface
from zope import component
from zope.component.interfaces import IComponents
from nti.utils import schema

from zope.lifecycleevent import IObjectAddedEvent
from zope.event import notify
from .interfaces import CourseInstanceAvailableEvent

from zope.security.interfaces import IPrincipal

from zope.cachedescriptors.property import Lazy

from BTrees import OOBTree

from pyramid.threadlocal import get_current_request

from nti.contentlibrary.interfaces import ILegacyCourseConflatedContentPackage
from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.courses import CourseInstance
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.courses import CourseAdministrativeLevel
from nti.contenttypes.courses.interfaces import ICourseAdministrativeLevel

from nti.contenttypes.courses.outlines import CourseOutline
from nti.contenttypes.courses.outlines import CourseOutlineNode
from nti.contenttypes.courses.outlines import CourseOutlineContentNode

from nti.app.products.courseware.interfaces import ICourseCatalog
from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment
from nti.app.products.courseware.interfaces import ICourseCatalogLegacyEntry
from nti.app.products.courseware.interfaces import IEnrolledCoursesCollection
from nti.app.products.courseware.interfaces import IPrincipalEnrollmentCatalog
from .interfaces import ILegacyCommunityBasedCourseInstance

from nti.dataserver import users
from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import ICommunity
from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.wref.interfaces import IWeakRef

from nti.utils.property import CachedProperty

from nti.dataserver.users import User
from nti.dataserver.users import Entity
from nti.dataserver.users import Community

from nti.ntiids.ntiids import make_ntiid
from nti.ntiids.ntiids import get_provider

from nti.externalization.singleton import SingletonDecorator
from nti.externalization import interfaces as ext_interfaces
from nti.externalization.externalization import to_external_object

from nti.store import course
from nti.store.interfaces import ICourse

class ICourseCatalogLegacyEntryInstancePolicy(interface.Interface):
	"""
	Named utility registered by the name of the content package
	provider to fill in details.

	Some of these are optional and can be unimplemented.
	"""

	unregister_courses_from_components_named = schema.TextLine(title="If given, we will unregister ICourse objects found in this component")

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

	unregister_courses_from_components_named = ()

	def purch_id_for_entry(self, entry):
		"""
		By default, the condensed identifier is the provider's unique
		 ID, with all spaces stripped and no section number
		"ENGR 1515-900" -> "ENGR1515"

		This becomes part of the purchasables NTIID,
		and the picture names, and should match the community.
		"""

		purch_id = entry.ProviderUniqueID.replace(' ','').split('-')[0]

		if not entry.Communities or not entry.Communities[0].startswith( purch_id ):
			__traceback_info__ = purch_id, entry
			raise ValueError("Community name not as expected")

		return purch_id

	def department_title_for_entry(self, entry):
		return entry.ProviderDepartmentTitle

	def extend_signature_for_instructor(self, instructor, sig_lines):
		return

@component.adapter(ICourseCatalogLegacyEntry, IObjectAddedEvent)
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
	# ATM, we only have this data for preview classes; currently
	# running classes have no startdate.
	# Obviously this will change soon
	startdate = entry.StartDate
	if startdate:
		preview = True
		startdate = unicode(isodate.date_isoformat(startdate))
	else:
		preview = False

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
	if preview or purch_id == 'SOC3123' or provider != 'OU':
		purch_ntiid = make_ntiid( provider=provider, nttype='course', specific=purch_id )
	else:
		# Old style is the title, minus whitespace and puncctuation, each word capitalized.
		# we could delegate this to the policy, but it shouldn't be
		# happening anymore
		ntiid_title = entry.Title.replace(',', '' )
		ntiid_title = ''.join( [x.capitalize() for x in ntiid_title.split()] )

		specific = purch_id + ntiid_title
		purch_ntiid = make_ntiid( provider=provider, nttype='course', specific=specific )

	the_course = course.create_course( ntiid=purch_ntiid,
									   title=entry.Title,
									   author=author,
									   name=entry.ProviderUniqueID,
									   description=entry.Description,
									   items=(entry.ContentPackageNTIID,),
									   icon=icon,
									   preview=preview,
									   thumbnail=thumbnail, # Not used
									   communities=entry.Communities,
									   featured=False,
									   department=policy.department_title_for_entry(entry),
									   signature=signature,
									   startdate=startdate,
									   # Things ignored
									   amount=None,
									   currency=None,
									   fee=None,
									   license_=None,
									   discountable=False,
									   bulk_purchase=False )

	if policy.unregister_courses_from_components_named:
		OU = component.getGlobalSiteManager().getUtility(IComponents, name=policy.unregister_courses_from_components_named)
		if OU.queryUtility( ICourse, name=purch_ntiid ):
			logger.warn( "Found existing ZCML course for %s; replacing", purch_ntiid )
			old_course = OU.getUtility( ICourse, name=purch_ntiid )
			OU.unregisterUtility( old_course, provided=ICourse, name=purch_ntiid )

	# Be careful what site we stick these in. Ideally we'd want to stick them in
	# site the library is loaded in in case we are configuring multiple libraries
	# for multiple sites. But in tests especially the current site might be a persistent
	# site, and purchasables aren't meant to be persisted (depending on when the added
	# events are fired).
	# Registering just in the non-persistent site may be a decent compromise, but it's also a
	# change from what we were doing.
	# Because library setup happens in the dataserver's site, so that
	# we can make persistent changes, we explicitly use the global site
	component.getGlobalSiteManager().registerUtility( the_course, ICourse,
													  name=purch_ntiid )


	# Ensure the referenced community exists if it doesn't, and
	# give it a course instance.

	# NOTE: This requires that we are operating in a transaction
	# with a real database.
	the_course = _course_instance_for_catalog_entry( entry ) # MAY send IObjectAdded if new
	the_course.updateInstructors( entry )

	# Always let people know it's available so they can do any
	# synchronization work that needs to pull from the external
	# content into the database
	notify(CourseInstanceAvailableEvent(the_course))

from nti.store.purchasable import get_all_purchasables
from nti.store.enrollment import get_enrollment
from nti.dataserver.datastructures import LastModifiedCopyingUserList

@interface.implementer(ICourseInstance)
@component.adapter(ICourseCatalogLegacyEntry)
def _course_instance_for_catalog_entry(entry):
	provider = get_provider(entry.ContentPackageNTIID)
	policy = component.queryUtility(ICourseCatalogLegacyEntryInstancePolicy, name=provider)

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

@interface.implementer(ICourseInstance)
@component.adapter(ILegacyCourseConflatedContentPackage)
def _course_content_package_to_course(package):
	# We go via the defined adapter from the catalog entry
	course_catalog = component.getUtility(ICourseCatalog)
	for entry in course_catalog:
		if getattr(entry, 'ContentPackageNTIID', None) == package.ntiid:
			return ICourseInstance(entry)

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
		for entry in course_catalog:
			ntiid = getattr( entry, 'ContentPackageNTIID', None)
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

	def __init__(self, community_name, content_package_ntiid ):
		"""
		Create a new instance. We will look up the ``community_name``
		on demand.
		"""
		super(_LegacyCommunityBasedCourseInstance,self).__init__()
		self.__legacy_community_name = community_name

		if self.legacy_community is None:
			raise ValueError("The community doesn't exist", community_name)

		self.ContentPackageNTIID = content_package_ntiid

	@property
	def legacy_community(self):
		return Entity.get_entity( self.__legacy_community_name )

	@property
	def legacy_purchasable(self):
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

	@CachedProperty
	def Outline(self):
		"""
		Parses the outline from the ToC on demand.

		This is not a persistent value, it is loaded directly
		from the content, and its modification dates come
		from there.
		"""
		package = self.legacy_content_package

		outline = CourseOutline()
		outline.__name__ = 'Outline'
		# TODO: Storing this persistent ref shouldn't work
		# across connections, since we're caching this object.
		# however, it might just be squeaking through because
		# we're caching it in a non-persistent property, and
		# objects are cached per-connection? The tests pass anyway.
		# If something breaks later, we could cache the list of
		# top-level units and copy those to a new Outline
		outline.__parent__ = self

		course_element = self._course_toc_element
		# TODO: Why do units in the toc have an NTIID?
		# and then, why do lessons NOT have an NTIID?
		for unit in course_element.iterchildren(tag='unit'):
			# lxml returns attributes as bytestrings
			unit_node = CourseOutlineNode()
			unit_node.title = unit.get('label').decode('utf-8')
			outline.append(unit_node)
			for lesson in unit.iterchildren(tag='lesson'):
				lesson_node = CourseOutlineContentNode()
				lesson_node.ContentNTIID = lesson.get('topic-ntiid').decode('utf-8')
				unit_node.append(lesson_node)
				# Sigh. It looks like date is optionally a comma-separated
				# list of datetimes. If there is only one, that looks like
				# the end date, not the beginning date.
				dates = lesson.get('date').split(',')
				if len(dates) == 1:
					lesson_node.AvailableEnding = dates[0]
				else:
					lesson_node.AvailableBeginning = dates[0]
					lesson_node.AvailableEnding = dates[1]

		# Finally, after all the children have been added (which
		# changes lastModified), set the lastModified to the ToC date.
		outline.lastModified = package.index_last_modified
		return outline


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
		for i in catalog_entry.Instructors:
			user = User.get_user(i.username) if i.username else None
			if user:
				found_instructors.add( user )

		if found_instructors:
			storage = self._instructor_storage
			storage.clear()
			storage.update( [IWeakRef(user) for user in found_instructors] )
		elif '_instructor_storage' in self.__dict__:
			# Clear it, but only if we had it
			self._instructor_storage.clear()

	@property
	def instructors(self):
		if '_instructor_storage' in self.__dict__:
			return [IPrincipal(x()) for x in self._instructor_storage if x()]
		return ()

@interface.implementer(ICourseCatalogLegacyEntry)
@component.adapter(_LegacyCommunityBasedCourseInstance)
def _legacy_course_instance_to_catalog_entry(instance):
	course_catalog = component.getUtility(ICourseCatalog)
	for entry in course_catalog:
		ntiid = getattr( entry, 'ContentPackageNTIID', None)
		if ntiid == instance.ContentPackageNTIID:
			return entry

from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.dataserver.interfaces import IEntityContainer
from nti.dataserver.interfaces import IDataserver

@interface.implementer(ICourseEnrollments)
@component.adapter(_LegacyCommunityBasedCourseInstance)
class _LegacyCourseInstanceEnrollments(object):

	def __init__( self, context ):
		self.context = context

	def iter_enrollments(self):
		# XXX: This is incredibly inefficient, waking
		# all known users in the system
		community = self.context.legacy_community
		container = IEntityContainer(community)
		ds = component.getUtility(IDataserver)
		for user in ds.users_folder.values():
			if user in container:
				yield user

from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from pyramid.interfaces import IRequest

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

	def _make_subrequest(self, path, body):
		subrequest = self.request.blank(path)
		subrequest.method = b'POST'
		subrequest.json = body
		subrequest.environ[b'REMOTE_USER'] = self.request.environ['REMOTE_USER']
		subrequest.environ[b'repoze.who.identity'] = self.request.environ['repoze.who.identity'].copy()

		return self.request.invoke_subrequest( subrequest )

	def enroll(self, user):
		self._make_subrequest( '/dataserver2/store/enroll_course',
							   {'courseID': self.context.legacy_purchasable.NTIID})
		return True

	def drop(self, user):
		self._make_subrequest( '/dataserver2/store/unenroll_course',
							   {'courseID': self.context.legacy_purchasable.NTIID})
		return True


@component.adapter(ICourseInstanceEnrollment)
@interface.implementer(ext_interfaces.IExternalObjectDecorator)
class _EnrollmentStatusDecorator(object):

	__metaclass__ = SingletonDecorator

	def decorateExternalObject(self, original, external):
		course_inst = original.CourseInstance
		if not ILegacyCommunityBasedCourseInstance.providedBy(course_inst):
			return

		if IEnrolledCoursesCollection.providedBy(getattr(original, '__parent__', None)):
			ec_collection = original.__parent__
			user = ec_collection.__parent__.__parent__
		else:
			request = get_current_request()
			user = request.authenticated_userid if request else None
			user = users.User.get_user(user) if user else None

		# get restricted scope entity from TOC
		restricted_id = course_inst.LegacyScopes['restricted']
		restricted = users.Entity.get_entity(restricted_id) if restricted_id else None
		# check user belongs to restricted entity
		for_credit = restricted in tuple(getattr(user, 'dynamic_memberships', ()))
		external["LegacyEnrollmentStatus"] = "ForCredit" if for_credit else "Open"

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
