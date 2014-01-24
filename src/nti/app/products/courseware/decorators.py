#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various course pieces.

$Id$
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
from nti.dataserver.interfaces import ILinkExternalHrefOnly

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import is_instructed_by_name

from .interfaces import ICourseCatalogEntry

from nti.dataserver.links import Link

from pyramid.threadlocal import get_current_request

LINKS = StandardExternalFields.LINKS
from . import VIEW_CONTENTS
from . import VIEW_CATALOG_ENTRY
from . import VIEW_COURSE_ENROLLMENT_ROSTER
from . import VIEW_COURSE_ACTIVITY


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

		username = None
		request = get_current_request()
		if request:
			username = request.authenticated_userid
		if is_instructed_by_name(context, username):
			# Give instructors the enrollment roster
			# and activity
			for rel in VIEW_COURSE_ENROLLMENT_ROSTER, VIEW_COURSE_ACTIVITY:
				_links.append( Link( context,
									 rel=rel,
									 elements=(rel,) ) )

		if 'href' not in result:
			link = Link(context)
			interface.alsoProvides( link, ILinkExternalHrefOnly )
			result['href'] = link

		# XXX: SLOW!
		#result['TotalEnrolledCount'] = ICourseEnrollments(context).count_enrollments()

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
