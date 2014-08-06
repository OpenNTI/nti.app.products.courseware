#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various course pieces.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from zope.location.interfaces import ILocation

from nti.externalization.interfaces import IExternalMappingDecorator
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.singleton import SingletonDecorator
from nti.externalization.externalization import to_external_object

from nti.dataserver.interfaces import ILinkExternalHrefOnly

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseSubInstance

from nti.dataserver.interfaces import IUser

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from .interfaces import ICourseInstanceEnrollment

from nti.dataserver.links import Link

from pyramid.threadlocal import get_current_request

from . import VIEW_CONTENTS
from . import VIEW_CATALOG_ENTRY
from . import VIEW_COURSE_ENROLLMENT_ROSTER
from . import VIEW_COURSE_ACTIVITY

LINKS = StandardExternalFields.LINKS

from .interfaces import ACT_VIEW_ACTIVITY
from nti.appserver.pyramid_authorization import has_permission

@interface.implementer(IExternalMappingDecorator)
@component.adapter(ICourseInstance)
class _CourseInstanceLinkDecorator(object):
	"""
	If a course instance can find its catalog entry, return that as a link.
	Also make it return an href, even if it isn't top-level,
	and adds the enrollment stats (XXX That may be really slow.)
	"""

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping( self, context, result ):
		# We have no way to know what order these will be
		# called in, so we must preserve anything that exists
		_links = result.setdefault( LINKS, [] )
		entry = ICourseCatalogEntry(context, None)
		if entry:
			_links.append( Link( entry, rel=VIEW_CATALOG_ENTRY )  )

		request = get_current_request()
		if request is not None and has_permission(ACT_VIEW_ACTIVITY, context, request):
			# Give instructors the enrollment roster
			# and activity.
			# NOTE: Assuming the two permissions are concordant; at worst this is a UI
			# issue though, the actual views are protected with individual permissions
			for rel in VIEW_COURSE_ENROLLMENT_ROSTER, VIEW_COURSE_ACTIVITY:
				_links.append( Link( context,
									 rel=rel,
									 elements=(rel,) ) )

		if 'href' not in result:
			link = Link(context)
			interface.alsoProvides( link, ILinkExternalHrefOnly )
			result['href'] = link

		enrollments = ICourseEnrollments(context)
		result['TotalEnrolledCount'] = enrollments.count_enrollments()
		# Legacy, non-interface methods
		try:
			result['TotalLegacyForCreditEnrolledCount'] = enrollments.count_legacy_forcredit_enrollments()
			result['TotalLegacyOpenEnrolledCount'] = enrollments.count_legacy_open_enrollments()
		except AttributeError:
			pass

@interface.implementer(IExternalMappingDecorator)
@component.adapter(ICourseOutline)
class _CourseOutlineContentsLinkDecorator(object):
	"""
	Adds the Contents link to the course outline to fetch its children.
	"""
	# See comments in other places about generalization

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping( self, context, result ):
		_links = result.setdefault(LINKS, [])
		link = Link(context, rel=VIEW_CONTENTS, elements=(VIEW_CONTENTS,))
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		_links.append(link)

@interface.implementer(IExternalMappingDecorator)
@component.adapter(ICourseInstanceEnrollment)
class _CourseEnrollmentUserProfileDetailsDecorator(object):
	"""
	Because we are now typically waking up the user profile from the
	database *anyway* when we request enrollment rosters (to sort on),
	it's relatively cheap and useful to the (current) UI to send back
	some extra details.
	"""

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping(self, context, result):
		user = IUser(context)
		ext_profile = to_external_object(user, name='summary')
		result['UserProfile'] = ext_profile

@interface.implementer(IExternalMappingDecorator)
@component.adapter(ICourseCatalogEntry)
class _CourseCatalogEntryLegacyDecorator(object):
	"""
	Restore some legacy fields used by existing applications.
	"""

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping(self, context, result):
		result['Title'] = context.title
		result['Description'] = context.description
