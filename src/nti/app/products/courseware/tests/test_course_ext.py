#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import all_of
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import has_item
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_entries
from hamcrest import has_property
from hamcrest import same_instance
from hamcrest import has_properties
does_not = is_not

from nti.testing.matchers import verifiably_provides

import fudge

from zope import interface

from zope.security.interfaces import IPrincipal

from nti.contenttypes.courses import acl
from nti.contenttypes.courses import courses
from nti.contenttypes.courses import interfaces
from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ES_CREDIT
from nti.contenttypes.courses.interfaces import ES_PURCHASED

from nti.app.products.courseware.decorators import _SharingScopesAndDiscussionDecorator

from nti.dataserver.interfaces import IUser
from nti.dataserver.authorization import ACT_READ

from nti.externalization.tests import externalizes

from nti.contenttypes.courses.tests import MockPrincipal

import nti.dataserver.tests.mock_dataserver as mock_dataserver
from nti.dataserver.tests.mock_dataserver import WithMockDSTrans

from nti.app.products.courseware.tests import CourseLayerTest

class TestCourseInstance(CourseLayerTest):

	def test_course_implements(self):
		assert_that( courses.CourseInstance(), verifiably_provides(interfaces.ICourseInstance) )

	def test_course_containment(self):
		inst = courses.CourseInstance()
		parent = courses.CourseAdministrativeLevel()
		parent['Course'] = inst
		gp = courses.CourseAdministrativeLevel()
		gp['Child'] = parent
		assert_that( gp, verifiably_provides(interfaces.ICourseAdministrativeLevel) )

	def test_course_instance_discussion(self):
		assert_that( courses.CourseInstance(), has_property( 'Discussions', not_none() ) )
		inst = courses.CourseInstance()
		assert_that( inst.Discussions, is_( same_instance( inst.Discussions )))

	def test_course_externalizes(self):
		inst = courses.CourseInstance()
		getattr(inst, 'Discussions' ) # this creates the Public scope
		getattr(inst, 'SubInstances')
		ntiid =  'tag:nextthought.com,2011-10:NTI-OID-0x12345'
		inst.SharingScopes['Public'].to_external_ntiid_oid = lambda: ntiid

		assert_that( unicode(inst.SharingScopes['Public']),
					 is_(ntiid))
		assert_that( inst,
					 externalizes(has_entries('Class', 'CourseInstance',
											  'Discussions', has_entries('Class', 'CommunityBoard', # Reall course instance board
																		 'MimeType', 'application/vnd.nextthought.forums.communityboard',
																		 'title', 'Discussions',
																		 'Creator', ntiid,
																	 ),
											  'MimeType', 'application/vnd.nextthought.courses.courseinstance',
							  ) ) )

		assert_that( inst,
					 externalizes( all_of(
						 does_not( has_key('SubInstances')),
						 # No sharing scopes, no request
						 does_not( has_key('SharingScopes'))) ) )

		assert_that(hash(inst), is_not(none()))

	@WithMockDSTrans
	def test_course_acl(self):
		connection = mock_dataserver.current_transaction
		inst = courses.CourseInstance()
		connection.add(inst)

		sharing_scopes = inst.SharingScopes
		sharing_scopes.initScopes()

		public = IPrincipal(sharing_scopes[ES_PUBLIC])
		IPrincipal(sharing_scopes[ES_CREDIT])
		IPrincipal(sharing_scopes[ES_PURCHASED])

		provider = acl.CourseInstanceACLProvider(inst)

		inst_acl = provider.__acl__
		assert_that(inst_acl, has_length(1))
		assert_that(inst_acl,
					has_item(has_properties('actor', is_(public),
											'action', 'Allow',
											'permission', is_([ACT_READ]) )))

		# Non public is same ACL
		interface.alsoProvides(inst, interfaces.INonPublicCourseInstance)
		provider = acl.CourseInstanceACLProvider(inst)
		inst_acl = provider.__acl__

		inst_acl = provider.__acl__
		assert_that(inst_acl, has_length(1))
		assert_that(inst_acl,
					has_item(has_properties('actor', is_(public),
											'action', 'Allow',
											'permission', is_([ACT_READ]) )))

		# Subinstances
		instructor = IPrincipal( 'instructor-bob' )
		subinstance = courses.CourseInstance()
		connection.add(subinstance)
		inst.SubInstances = { 'section-01' : subinstance }
		subinstance.instructors = (instructor,)

		provider = acl.CourseInstanceACLProvider(inst)
		inst_acl = provider.__acl__
		assert_that(inst_acl, has_length(2))
		assert_that(inst_acl,
					has_item(has_properties('actor', is_(public),
											'action', 'Allow',
											'permission', is_([ACT_READ]) )))
		assert_that(inst_acl,
					has_item(has_properties('actor', is_(instructor),
											'action', 'Allow',
											'permission', is_([ACT_READ]) )))

	@fudge.patch('nti.app.products.courseware.decorators.IEntityContainer',
				 'nti.app.renderers.decorators.get_remote_user')
	def test_course_sharing_scopes_externalizes(self, mock_container, mock_rem_user):
		class Container(object):
			def __contains__(self, _): return True
		mock_container.is_callable().returns(Container())
		mock_rem_user.is_callable()

		inst = courses.CourseInstance()
		getattr(inst, 'Discussions' ) # this creates the Public scope
		getattr(inst, 'SubInstances')
		ntiid =  'tag:nextthought.com,2011-10:NTI-OID-0x12345'
		inst.SharingScopes['Public'].to_external_ntiid_oid = lambda: ntiid

		subinst = courses.ContentCourseSubInstance()
		inst.SubInstances['sec1'] = subinst
		getattr(subinst, 'Discussions')
		ntiid2 = ntiid + '2'
		subinst.SharingScopes['Public'].to_external_ntiid_oid = lambda: ntiid2

		result = {}
		_SharingScopesAndDiscussionDecorator(subinst, None)._do_decorate_external(subinst, result)

		assert_that( result, has_entry( 'SharingScopes',
										has_entries( 'Class', 'CourseInstanceSharingScopes',
													 'Items', has_entries(
														 'Public', has_entries('Creator', 'system',
																			   'Class', 'Community', # Really CourseInstanceSharingScope
																			   'MimeType', 'application/vnd.nextthought.community',
																			   'NTIID', ntiid2,
																			   'ID', ntiid2,
																			   'Username', ntiid2))) ) )
		assert_that( result, has_entry( 'ParentSharingScopes',
										has_entries('Class', 'CourseInstanceSharingScopes',
													'Items', has_entry(
														'Public', has_entries('Creator', 'system',
																			  'NTIID', ntiid,
																			  'ID', ntiid,
																			  'Username', ntiid))) ) )

		assert_that( result, has_entry('ParentDiscussions',
									   has_entries('Creator', ntiid)))

	def _course_setup(self):
		principal = MockPrincipal()
		self.ds.root[principal.id] = principal
		interface.alsoProvides(principal, IUser)

		admin = courses.CourseAdministrativeLevel()
		self.ds.root['admin'] = admin
		for name in ('course',):
			course = courses.ContentCourseInstance()
			admin[name] = course
			course.SharingScopes.initScopes()

		self.principal  = principal
		self.course = admin['course']
		self.admin = self.ds.root['admin']

	@WithMockDSTrans
	def test_course_deletion(self):
		self._course_setup()
		admin = self.admin
		course = self.course
		principal = self.principal

		manager = interfaces.ICourseEnrollmentManager(course)
		manager.enroll(principal, scope='Public')

		ce = interfaces.ICourseEnrollments(course)
		assert_that(ce.count_enrollments(), is_(1))

		del admin['course']
		ce = interfaces.ICourseEnrollments(course)
		assert_that(ce.count_enrollments(), is_(0))
