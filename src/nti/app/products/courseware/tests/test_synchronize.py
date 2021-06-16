#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import raises
from hamcrest import has_key
from hamcrest import calling
from hamcrest import contains
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property
from hamcrest import same_instance
from hamcrest import has_properties
from hamcrest import contains_inanyorder

from nti.testing.matchers import is_empty
from nti.testing.matchers import verifiably_provides

import fudge
import datetime
import pkg_resources

from zope import interface
from zope import component

from persistent.interfaces import IPersistent

from zope.lifecycleevent import notify

from nti.contenttypes.presentation.lesson import NTILessonOverView

from nti.app.products.courseware.decorators import _AnnouncementsDecorator
from nti.app.products.courseware.decorators import _SharingScopesAndDiscussionDecorator

from nti.assessment.interfaces import IQAssignmentDateContext

from nti.assessment.interfaces import IQAssignmentPolicies

from nti.contentlibrary import filesystem
from nti.contentlibrary import ContentRemovalException

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.dataserver.contenttypes.forums.forum import CommunityForum

from nti.dataserver.interfaces import EVERYONE_GROUP_NAME
from nti.dataserver.interfaces import AUTHENTICATED_GROUP_NAME

from nti.externalization.externalization import to_external_object

from nti.contenttypes.courses import catalog
from nti.contenttypes.courses import legacy_catalog

from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import INonPublicCourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseInstanceVendorInfo
from nti.contenttypes.courses.interfaces import CourseBundleWillUpdateEvent
from nti.contenttypes.courses.interfaces import IEnrollmentMappedCourseInstance

from nti.contenttypes.courses.discussions.interfaces import ICourseDiscussions

from nti.contenttypes.courses.outlines import CourseOutlineContentNode

from nti.contenttypes.courses._synchronize import synchronize_catalog_from_root

from nti.dataserver.authorization import ACT_READ
from nti.dataserver.authorization import ACT_CREATE
from nti.dataserver.authorization import CONTENT_ROLE_PREFIX

from nti.dataserver.interfaces import IMutableGroupMember
from nti.dataserver.interfaces import ISharingTargetEntityIterable

from nti.dataserver.users.users import User

from nti.externalization.tests import externalizes

from nti.ntiids import ntiids
from nti.ntiids.ntiids import find_object_with_ntiid

from nti.recorder.record import append_records
from nti.recorder.record import get_transactions
from nti.recorder.record import TransactionRecord

from nti.schema.eqhash import EqHash

from nti.app.products.courseware.tests import CourseLayerTest

from nti.dataserver.tests.test_authorization_acl import denies
from nti.dataserver.tests.test_authorization_acl import permits

from nti.dataserver.tests.mock_dataserver import WithMockDS
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans
from nti.dataserver.tests.mock_dataserver import mock_db_trans

from ZODB.interfaces import IConnection

resource_filename = getattr(pkg_resources, 'resource_filename')

@EqHash( 'ntiid' )
class MockContentPackage(object):

	def __init__(self, ntiid):
		self.ntiid = ntiid

# This probably belongs in nti.contenttypes.courses, but some
# tests below employ the decorators now in app.
class TestFunctionalSynchronize(CourseLayerTest):

	def setUp(self):
		subscribers = resource_filename( 'nti.contenttypes.courses.tests', 'test_subscribers' )
		self.library = filesystem.GlobalFilesystemContentPackageLibrary( subscribers )
		self.library.syncContentPackages()
		component.getGlobalSiteManager().registerUtility(self.library, IContentPackageLibrary)

		root_name = 'TestSynchronizeWithSubInstances'
		synchronize = resource_filename( 'nti.contenttypes.courses.tests', root_name )
		bucket = filesystem.FilesystemBucket(name=root_name)
		bucket.absolute_path = synchronize

		folder = catalog.CourseCatalogFolder()

		self.folder = folder
		self.bucket = bucket

	def tearDown(self):
		component.getGlobalSiteManager().unregisterUtility(self.library, IContentPackageLibrary)

	@WithMockDSTrans
	def test_synchronize_with_sub_instances(self):
		bucket = self.bucket
		folder = self.folder
		IConnection(self.ds.root).add(folder)

		synchronize_catalog_from_root(folder, bucket)

		# Now check that we get the structure we expect
		spring = folder['Spring2014']
		gateway = spring['Gateway']

		# Define our scope ntiids
		public_ntiid = gateway.SharingScopes['Public'].NTIID
		restricted_ntiid = gateway.SharingScopes['ForCredit'].NTIID

		assert_that(gateway, verifiably_provides(IEnrollmentMappedCourseInstance))
		assert_that(gateway, externalizes())

		assert_that(gateway.Outline, has_length(7))

		assert_that(gateway.ContentPackageBundle.__parent__,
					 is_(gateway))

		# The bundle's NTIID is derived from the path
		assert_that(gateway.ContentPackageBundle,
					has_property('ntiid', 'tag:nextthought.com,2011-10:NTI-Bundle:CourseBundle-Spring2014_Gateway'))

		# assert_that( gateway.instructors, is_((IPrincipal('harp4162'),)))

		assert_that(ICourseInstanceVendorInfo(gateway),
					has_entry('OU', has_entry('key', 42)))

		assert_that(ICourseCatalogEntry(gateway),
					has_properties( 'ProviderUniqueID', 'CLC 3403',
									'Title', 'Law and Justice',
									'creators', ('Jason',)))
		assert_that(ICourseInstance(ICourseCatalogEntry(gateway)),
					is_(gateway))

		assert_that(ICourseCatalogEntry(gateway),
					 verifiably_provides(IPersistent))
		# Ensure we're not proxied
		assert_that(type(ICourseCatalogEntry(gateway)),
					is_(same_instance(legacy_catalog._CourseInstanceCatalogLegacyEntry)))

		sec1 = gateway.SubInstances['01']
		sec_public_ntiid = sec1.SharingScopes['Public'].NTIID
		sec_restricted_ntiid = sec1.SharingScopes['ForCredit'].NTIID

		assert_that(ICourseInstanceVendorInfo(sec1),
					 has_entry('OU', has_entry('key2', 72)))

		assert_that(sec1.ContentPackageBundle,
					is_(gateway.ContentPackageBundle))

		assert_that(sec1.Outline, is_(gateway.Outline))

		for o in sec1.SharingScopes[ES_CREDIT], gateway.SharingScopes[ES_CREDIT]:
			assert_that(o, verifiably_provides(ISharingTargetEntityIterable))

		# partially overridden course info
		sec1_cat = ICourseCatalogEntry(sec1)
		assert_that(sec1_cat,
					 has_property('key',
								   is_(bucket.getChildNamed('Spring2014')
									   .getChildNamed('Gateway')
									   .getChildNamed('Sections')
									   .getChildNamed('01')
									   .getChildNamed('course_info.json'))))
		assert_that(sec1_cat,
					 is_not(same_instance(ICourseCatalogEntry(gateway))))
		assert_that(sec1_cat,
					 is_(legacy_catalog._CourseSubInstanceCatalogLegacyEntry))
		assert_that(sec1_cat,
					 has_properties('ProviderUniqueID', 'CLC 3403-01',
									'Title', 'Law and Justice',
									'creators', ('Steve',)))

		assert_that(sec1_cat, has_property('links',
											 contains(has_property('target', sec1))))

		gateway.SharingScopes['Public']._v_ntiid = 'gateway-public'
		sec1.SharingScopes['Public']._v_ntiid = 'section1-public'
		sec1.SharingScopes['ForCredit']._v_ntiid = 'section1-forcredit'
		assert_that(sec1,
					 externalizes(has_entries(
						 'Class', 'CourseInstance')))

		gateway_ext = to_external_object(gateway)
		sec1_ext = to_external_object(sec1)
		dec = _SharingScopesAndDiscussionDecorator(sec1, None)
		dec._is_authenticated = False
		dec._do_decorate_external(sec1, sec1_ext)
		dec._do_decorate_external(gateway, gateway_ext)
		assert_that(gateway_ext, has_entry('LegacyScopes',
											has_entries('public', gateway.SharingScopes['Public'].NTIID,
														'restricted', gateway.SharingScopes['ForCredit'].NTIID)))
		assert_that(gateway_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'CLC 3403 - Open')),
						'DefaultSharingScopeNTIID', gateway.SharingScopes['Public'].NTIID)))

		assert_that(sec1_ext,
					 has_entries(
						 'LegacyScopes', has_entries(
							 # public initially copied from the parent
							 'public', gateway.SharingScopes['Public'].NTIID,
							 'restricted', sec1.SharingScopes['ForCredit'].NTIID)))

		assert_that(sec1_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'CLC 3403-01 - Open')),
						'DefaultSharingScopeNTIID', gateway.SharingScopes['Public'].NTIID)))

		# although if we make the parent non-public, we go back to ourself
		interface.alsoProvides(gateway, INonPublicCourseInstance)
		sec1_ext = to_external_object(sec1)
		dec._do_decorate_external(sec1, sec1_ext)
		assert_that(sec1_ext,
					 has_entries(
						 'LegacyScopes', has_entries(
							 'public', sec1.SharingScopes['Public'].NTIID,
							 'restricted', sec1.SharingScopes['ForCredit'].NTIID)))
		interface.noLongerProvides(gateway, INonPublicCourseInstance)

		assert_that(sec1_cat,
					 externalizes(has_key('PlatformPresentationResources')))

		sec2 = gateway.SubInstances['02']
		assert_that(sec2.Outline, has_length(1))

		date_context = IQAssignmentDateContext(sec2)
		assert_that(date_context, has_property('_mapping',
												has_entry(
													"tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg:QUIZ1_aristotle",
													has_entry('available_for_submission_beginning',
															  datetime.datetime(2014, 1, 22, 6, 0)))))

		policies = IQAssignmentPolicies(sec2)
		assert_that(dict(policies.getPolicyForAssignment("tag:nextthought.com,2011-10:OU-NAQ-CLC3403_LawAndJustice.naq.asg:QUIZ1_aristotle")),
					 is_({'auto_grade': {'total_points': 20}, u'maximum_time_allowed': 50}))

		sec2_ext = to_external_object(sec2)
		dec._do_decorate_external(sec2, sec2_ext)
		assert_that(sec2_ext, has_entries(
			'SharingScopes',
			has_entry('Items', has_entry("Public",
										 has_entries('alias', "From Vendor Info",
													 "realname", "Law and Justice - Open",
													 "avatarURL", '/foo/bar.jpg')))))

		# We should have the catalog functionality now
		sec3 = gateway.SubInstances['03']
		cat_entries = list(folder.iterCatalogEntries())
		assert_that(cat_entries, has_length(4))
		assert_that(cat_entries,
					 contains_inanyorder(ICourseCatalogEntry(gateway),
										  ICourseCatalogEntry(sec1),
										  ICourseCatalogEntry(sec2),
										  ICourseCatalogEntry(sec3)))

		# The NTIIDs are derived from the path
		assert_that(cat_entries,
					 contains_inanyorder(
						 has_property('ntiid',
									  'tag:nextthought.com,2011-10:NTI-CourseInfo-Spring2014_Gateway_SubInstances_02'),
						 has_property('ntiid',
									  'tag:nextthought.com,2011-10:NTI-CourseInfo-Spring2014_Gateway_SubInstances_01'),
						 has_property('ntiid',
									  'tag:nextthought.com,2011-10:NTI-CourseInfo-Spring2014_Gateway_SubInstances_03'),
						 has_property('ntiid',
									  'tag:nextthought.com,2011-10:NTI-CourseInfo-Spring2014_Gateway')))

		# And each entry can be resolved by ntiid...
		assert_that([ntiids.find_object_with_ntiid(x.ntiid) for x in cat_entries],
					 is_([None, None, None, None]))
		# ...but only with the right catalog installed
		old_cat = component.getUtility(ICourseCatalog)
		component.provideUtility(folder, ICourseCatalog)
		try:
			assert_that([ntiids.find_object_with_ntiid(x.ntiid) for x in cat_entries],
						 is_(cat_entries))
		finally:
			component.provideUtility(old_cat, ICourseCatalog)

		# course discussions
		discussions = ICourseDiscussions(gateway, None)
		assert_that(discussions, is_not(none()))
		assert_that(discussions, has_key('d0.json'))
		assert_that(discussions['d0.json'], has_property('id', is_(u'nti-course-bundle://Discussions/d0.json')))

		discussions = ICourseDiscussions(sec2, None)
		assert_that(discussions, is_not(none()))
		assert_that(discussions, has_key('d1.json'))
		assert_that(discussions['d1.json'], has_property('id', is_(u'nti-course-bundle://Sections/02/Discussions/d1.json')))

	@fudge.patch( 'nti.contenttypes.courses._outline_parser.find_object_with_ntiid' )
	def test_synchronize_with_locked(self, mock_find_object):
		"""
		Test outline nodes respect sync locks.
		"""
		mock_find_object.is_callable().returns( None )
		bucket = self.bucket
		folder = self.folder
		synchronize_catalog_from_root(folder, bucket)

		# Now check that we get the structure we expect
		spring = folder['Spring2014']
		gateway = spring['Gateway']
		outline = gateway.Outline
		assert_that( outline, has_length(7) )

		def _resync(force=False):
			outline.lastModified = 0
			synchronize_catalog_from_root(folder, bucket, force=force)

		outline_node = tuple(outline.values())[0]
		child_node = tuple(outline_node.values())[0]
		child_ntiid = child_node.ntiid
		old_child_title = child_node.title
		node_ntiid = outline_node.ntiid
		assert_that( outline_node.locked, is_( False ) )
		assert_that( outline_node.title, is_( "Introduction" ) )
		assert_that( outline_node.is_published(), is_( True ) )
		assert_that( outline_node, has_length(2) )

		assert_that( child_node.locked, is_( False ) )

		# 1. Change title and lock object
		outline_node.title = new_title = 'New title'
		outline_node.locked = True
		child_node.title = new_child_title = 'New child title'

		_resync()

		# Our parent title change is preserved, and children are updated.
		outline = gateway.Outline
		assert_that( outline.lastModified, is_not(is_( 0 )))
		outline_node = tuple(outline.values())[0]
		child_node = tuple(outline_node.values())[0]

		assert_that( outline_node.ntiid, is_( node_ntiid ) )
		assert_that( outline_node.locked, is_( True ) )
		assert_that( outline_node.title, is_( new_title ) )
		assert_that( outline_node.is_published(), is_( True ) )
		assert_that( outline_node, has_length(2) )

		# Our unlocked child's title was overwritten
		assert_that( child_node.locked, is_( False ) )
		assert_that( child_node.ntiid, is_( child_ntiid ) )
		assert_that( child_node.title, is_( old_child_title ) )

		# 2. Change child title and lock object. Add new user-created
		# node at index 0. We expect:
		# 	* The changed attributes will stay changed on locked objects.
		#	* The child node order will not be reverted.
		#	* The new child will still exist.
		#	* Unlocked nodes will revert.
		#	* Transaction records are preserved.
		unchanged_node = tuple(outline_node.values())[1]
		old_node_title2 = unchanged_node.title
		unchanged_node.title = 'new child node title 2'
		unchanged_record = TransactionRecord( principal='user1', tid=unchanged_node.ntiid )

		child_node.locked = True
		child_node.title = new_child_title
		child_node_record = TransactionRecord( principal='user1', tid=child_node.ntiid )

		user_child_node = CourseOutlineContentNode()
		user_child_node.ntiid = user_node_ntiid = 'tag:nextthought.com,2011-10:NTI-NTICourseOutlineNode-Spring2014_Gateway.0.1000'
		user_child_node.title = user_node_title = 'User created node'
		user_child_node.locked = True
		user_child_node_record = TransactionRecord( principal='user1', tid=user_child_node.ntiid )
		outline_node.clear()

		append_records(unchanged_node, unchanged_record)
		append_records(child_node, child_node_record)
		append_records(user_child_node, user_child_node_record)
		outline_node.append( user_child_node )
		outline_node.append( child_node )
		outline_node.append( unchanged_node )

		_resync()

		outline = gateway.Outline
		assert_that( outline.lastModified, is_not(is_( 0 )))
		outline_node = tuple(outline.values())[0]
		# New node exists
		assert_that( outline_node, has_length(3) )

		# Unlock our outline node, all children should be preserved.
		outline_node.locked = False
		_resync()

		outline = gateway.Outline
		assert_that( outline.lastModified, is_not(is_( 0 )))
		outline_node = tuple(outline.values())[0]
		# New node exists
		assert_that( outline_node, has_length(3) )

		# User node in slot one; user node stays unpublished.
		child_node = tuple(outline_node.values())[0]
		child_txs = get_transactions( child_node )
		assert_that( child_node.ntiid, is_( user_node_ntiid ) )
		assert_that( child_node.locked, is_( True ) )
		assert_that( child_node.title, is_( user_node_title ) )
		assert_that( child_node.is_published(), is_( False ) )
		assert_that( child_txs, has_length( 1 ))
		assert_that( child_txs[0], is_( user_child_node_record ))

		# Changed title in slot two
		child_node = tuple(outline_node.values())[1]
		child_txs = get_transactions( child_node )
		assert_that( child_node.ntiid, is_( child_node.ntiid ) )
		assert_that( child_node.locked, is_( True ) )
		assert_that( child_node.title, is_( new_child_title ) )
		assert_that( child_node.is_published(), is_( True ) )
		assert_that( child_txs, has_length( 1 ))
		assert_that( child_txs[0], is_( child_node_record ))

		# Reverted node in slot three
		child_node = tuple(outline_node.values())[2]
		child_txs = get_transactions( child_node )
		assert_that( child_node.ntiid, is_( unchanged_node.ntiid ) )
		assert_that( child_node.locked, is_( False ) )
		assert_that( child_node.title, is_( old_node_title2 ) )
		assert_that( child_node.is_published(), is_( True ) )
		assert_that( child_txs, has_length( 1 ))
		assert_that( child_txs[0], is_( unchanged_record ))

		# Reset unit node locks.
		for child in outline.values():
			child.locked = False
		assert_that( outline, has_length(7) )
		_resync()

		# Remove node and test child_order_locked
		del outline[outline.keys()[0]]

		_resync()
		assert_that( outline, has_length(7) )

		outline.child_order_locked = True
		del outline[outline.keys()[0]]
		_resync()
		assert_that( outline, has_length(6) )

		# Reset
		outline.child_order_locked = False
		_resync()
		assert_that( outline, has_length(7) )

		# Add new unit node in outline, with locked children.
		user_child_node.locked = user_child_node.child_order_locked = False
		outline.locked = outline.child_order_locked = False
		grandchild_node = CourseOutlineContentNode()
		grandchild_node.ntiid = 'tag:nextthought.com,2011-10:NTI-NTICourseOutlineNode-Spring2014_Gateway.0.1000.grandchild'
		grandchild_node.title = 'To be deleted'
		grandchild_node.locked = True
		outline.append( user_child_node )
		user_child_node.append( grandchild_node )
		assert_that( calling( _resync ), raises( ContentRemovalException ))
		# Not in transaction, so state is not reverted; re-add.
		assert_that( outline, has_length(7) )
		outline.append( user_child_node )

		# Now force it and the unit node is removed.
		_resync( force=True )
		assert_that( outline, has_length(7) )

		# Deleted node has unlocked children. A non-removed node
		# does have locked children.
		tuple(tuple(outline.values())[0].values())[0].locked = True
		grandchild_node.locked = False
		outline.append( user_child_node )
		_resync()
		assert_that( outline, has_length(7) )

		# Swap node order
		original_ntiid_order = tuple( outline.keys() )
		outline.insert( 0, tuple(outline.values())[-1] )
		move_ntiid_order = tuple( outline.keys() )
		outline.child_order_locked = True
		_resync()

		assert_that( outline, has_length(7) )
		assert_that( move_ntiid_order, is_not( original_ntiid_order ))
		assert_that( tuple( outline.keys() ), is_( move_ntiid_order ))

		# Reset and lock an underlying lesson. The lesson survives.
		# XXX: It may be better to lock the parent node when lessons are edited.
		_resync( force=True )
		content_node = tuple(tuple(outline.values())[0].values())[0]
		content_node.LessonOverviewNTIID = lesson_ntiid = 'about-today'
		locked_lesson = NTILessonOverView()
		locked_lesson.lock()
		mock_find_object.is_callable().returns( locked_lesson )

		_resync()
		content_node = tuple(tuple(outline.values())[0].values())[0]
		assert_that( content_node.LessonOverviewNTIID, is_(lesson_ntiid) )

	@WithMockDSTrans
	def test_default_sharing_scope_use_parent(self):
		"""
		Verify if the 'UseParentDefaultSharingScope' is set in the section, the
		parent's default scope is used.
		"""
		bucket = self.bucket
		folder = self.folder
		IConnection(self.ds.root).add(folder)
		synchronize_catalog_from_root(folder, bucket)

		spring = folder['Spring2014']
		gateway = spring['Gateway']
		# Section 01 tests the non-case; Section 02 verifies toggle;
		# Section 3 verifies negative case.
		sec = gateway.SubInstances['02']

		# Define our scope ntiids
		public_ntiid = gateway.SharingScopes['Public'].NTIID
		restricted_ntiid = gateway.SharingScopes['ForCredit'].NTIID

		sec_public_ntiid = sec.SharingScopes['Public'].NTIID
		sec_restricted_ntiid = sec.SharingScopes['ForCredit'].NTIID

		gateway_ext = to_external_object(gateway)
		sec2_ext = to_external_object(sec)
		dec = _SharingScopesAndDiscussionDecorator(sec, None)
		dec._is_authenticated = False
		dec._do_decorate_external(sec, sec2_ext)
		dec._do_decorate_external(gateway, gateway_ext)

		assert_that(gateway_ext, has_entry('LegacyScopes',
											has_entries('public', gateway.SharingScopes['Public'].NTIID,
														'restricted', gateway.SharingScopes['ForCredit'].NTIID)))

		assert_that(gateway_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'CLC 3403 - Open')),
						'DefaultSharingScopeNTIID', gateway.SharingScopes['Public'].NTIID)))

		assert_that(sec2_ext,
					 has_entries(
						 'LegacyScopes', has_entries(
							 # public initially copied from the parent
							 'public', gateway.SharingScopes['Public'].NTIID,
							 'restricted', sec.SharingScopes['ForCredit'].NTIID)))

		# Our ForCredit section actually defaults to the parent Public scope
		assert_that(sec2_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'From Vendor Info')),
						'DefaultSharingScopeNTIID', gateway.SharingScopes['Public'].NTIID)))

	@WithMockDSTrans
	@fudge.patch('nti.app.products.courseware.decorators.IEntityContainer',
				 'nti.app.renderers.decorators.AbstractAuthenticatedRequestAwareDecorator.remoteUser')
	def test_default_sharing_scope_do_not_use_parent(self, mock_container, mock_rem_user):
		"""
		Verify if the 'UseParentDefaultSharingScope' is set to False, the
		parent's default scope is *not* used.
		"""
		# Make sure we're enrolled in sec03
		class Container(object):
			def __contains__(self, unused_o): return True

		mock_container.is_callable().returns(Container())
		mock_rem_user.is_callable().returns(object())

		bucket = self.bucket
		folder = self.folder
		IConnection(self.ds.root).add(folder)
		synchronize_catalog_from_root(folder, bucket)

		spring = folder['Spring2014']
		gateway = spring['Gateway']
		# Section 01 tests the non-case; Section 02 verifies toggle;
		# Section 3 verifies negative case.
		sec = gateway.SubInstances['03']

		# Define our scope ntiids
		public_ntiid = gateway.SharingScopes['Public'].NTIID
		restricted_ntiid = gateway.SharingScopes['ForCredit'].NTIID

		sec_public_ntiid = sec.SharingScopes['Public'].NTIID
		sec_restricted_ntiid = sec.SharingScopes['ForCredit'].NTIID

		gateway_ext = to_external_object(gateway)
		sec_ext = to_external_object(sec)
		dec = _SharingScopesAndDiscussionDecorator(sec, None)
		dec._is_authenticated = True

		dec._do_decorate_external(sec, sec_ext)
		dec._do_decorate_external(gateway, gateway_ext)

		assert_that(gateway_ext, has_entry('LegacyScopes',
											has_entries('public', gateway.SharingScopes['Public'].NTIID,
														'restricted', gateway.SharingScopes['ForCredit'].NTIID)))

		assert_that(gateway_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'CLC 3403 - Open')),
						'DefaultSharingScopeNTIID', gateway.SharingScopes['ForCredit'].NTIID)))

		assert_that(sec_ext,
					 has_entries(
						 'LegacyScopes', has_entries(
							 # public initially copied from the parent
							 'public', gateway.SharingScopes['Public'].NTIID,
							 'restricted', sec.SharingScopes['ForCredit'].NTIID)))

		# This default comes from our section.
		assert_that(sec_ext, has_entries(
			'SharingScopes',
			has_entries('Items', has_entry('Public',
										   has_entry('alias', 'From Vendor Info')),
						'DefaultSharingScopeNTIID', sec.SharingScopes['ForCredit'].NTIID)))

	def test_synchronize_clears_caches(self):
		# User.create_user(self.ds, username='harp4162')
		bucket = self.bucket
		folder = self.folder

		assert_that(list(folder.iterCatalogEntries()),
					 is_empty())

		synchronize_catalog_from_root(folder, bucket)

		assert_that(list(folder.iterCatalogEntries()),
					 has_length(4))

		# Now delete the course
		del folder['Spring2014']['Gateway']

		# and the entries are gone
		assert_that(list(folder.iterCatalogEntries()),
					 is_empty())

	@WithMockDSTrans
	def test_non_public_parent_course_doesnt_hide_child_section(self):
		bucket = self.bucket
		folder = self.folder
		IConnection(self.ds.root).add(folder)

		synchronize_catalog_from_root(folder, bucket)

		# Now check that we get the structure we expect
		spring = folder['Spring2014']

		gateway = spring['Gateway']

		interface.alsoProvides(gateway, INonPublicCourseInstance)
		cat = ICourseCatalogEntry(gateway)

		sec1 = gateway.SubInstances['01']
		sec1_cat = ICourseCatalogEntry(sec1)

		assert_that(sec1_cat, permits(AUTHENTICATED_GROUP_NAME, ACT_READ))
		assert_that(sec1_cat, permits(AUTHENTICATED_GROUP_NAME, ACT_CREATE))

		# and as joint, just because
		assert_that(sec1_cat, permits([EVERYONE_GROUP_NAME, AUTHENTICATED_GROUP_NAME],
									   ACT_READ))

		# But the CCE for the course is not public
		assert_that(cat, denies(EVERYONE_GROUP_NAME, ACT_READ))
		assert_that(cat, denies(EVERYONE_GROUP_NAME, ACT_CREATE))

	@fudge.patch('nti.app.products.courseware.decorators.IEntityContainer',
				 'nti.app.renderers.decorators.AbstractAuthenticatedRequestAwareDecorator.remoteUser')
	def test_course_announcements_externalizes(self, mock_container, mock_rem_user):
		"""
		Verify course announcements are externalized on the course.
		"""
		# Mock we have a user and they are in a scope
		class Container(object):
			def __contains__(self, unused_o): return True
		mock_container.is_callable().returns(Container())
		mock_rem_user.is_callable().returns(object())

		bucket = self.bucket
		folder = self.folder
		synchronize_catalog_from_root(folder, bucket)

		spring = folder['Spring2014']
		gateway = spring['Gateway']
		section = gateway.SubInstances['03']
		gateway_discussions = getattr(gateway, 'Discussions')

		section_discussions = section.Discussions
		# Setup. Just make sure we have a discussion here.
		section_discussions['booya'] = gateway_discussions['Forum']

		gateway_ext = {}
		section_ext = {}

		decorator = _AnnouncementsDecorator(gateway, None)
		decorator._do_decorate_external(gateway, gateway_ext)
		decorator = _AnnouncementsDecorator(section, None)
		decorator._is_authenticated = True
		decorator._do_decorate_external(section, section_ext)

		# Gateway does not have announcements since it does not have any.
		assert_that(gateway_ext,
					is_not(has_entries(
								'AnnouncementForums',
								has_entries('Items', is_empty()))))

		# Our section has only open announcements.
		assert_that(section_ext,
					has_entries(
								'AnnouncementForums',
								has_entries('Items',
											has_entry('Public', not_none()),
										   	'Class',
										   	'CourseInstanceAnnouncementForums')))

	@WithMockDS
	@fudge.patch( 'nti.contenttypes.courses._synchronize._site_name',
				  'nti.contenttypes.courses.utils.adjust_scope_membership',
				  'nti.contenttypes.courses.utils.get_enrollments' )
	def test_sync_with_multiple_packages(self, mock_get_site, mock_adjust_scope, mock_get_enroll):
		"""
		Test enrollment and permissioning when courses add content packages
		during sync.
		"""
		# Some of this doesn't quite work with this test setup.
		mock_get_site.is_callable().returns( '' )
		mock_adjust_scope.is_callable().returns( None )

		# Create and enroll user
		with mock_db_trans():
			user = User.create_user( username='seveneves' )
		bucket = self.bucket
		folder = self.folder
		synchronize_catalog_from_root(folder, bucket)

		# Now check that we get the structure we expect
		spring = folder['Spring2014']
		gateway = spring['Gateway']

		def _get_role_ids():
			membership = component.getAdapter(user, IMutableGroupMember,
										  	CONTENT_ROLE_PREFIX)
			return [x.id for x in set(membership.groups)]

		package_one_id = 'content-role:ussc:cohen.cohen_v._california.'
		package_two_id = 'content-role:ussc:cohen.cohen_v._california2.'

		# Check base enrollment roles
		with mock_db_trans():
			manager = ICourseEnrollmentManager(gateway)
			record = manager.enroll( user )
			mock_get_enroll.is_callable().returns( (record,) )

			role_ids = _get_role_ids()
			assert_that( role_ids, contains( package_one_id ))

		# Now with another content package
		with mock_db_trans():
			new_cp = MockContentPackage( "tag:nextthought.com,2011-10:USSC-HTML-Cohen.cohen_v._california2." )
			notify( CourseBundleWillUpdateEvent( gateway, (new_cp,), () ) )
			role_ids = _get_role_ids()
			assert_that( role_ids, contains_inanyorder( package_one_id,
														package_two_id ))

		# Remove original during sync (e.g. removed from another course), but we
		# still have access to this package due to our enrollment.
		with mock_db_trans():
			old_cp = find_object_with_ntiid(  "tag:nextthought.com,2011-10:USSC-HTML-Cohen.cohen_v._california." )
			notify( CourseBundleWillUpdateEvent( gateway, (), (old_cp,) ) )
			role_ids = _get_role_ids()
			assert_that( role_ids, contains_inanyorder( package_one_id,
														package_two_id ))

		# Remove new
		with mock_db_trans():
			notify( CourseBundleWillUpdateEvent( gateway, (), (new_cp,) ) )
			role_ids = _get_role_ids()
			assert_that( role_ids, contains( package_one_id ))
