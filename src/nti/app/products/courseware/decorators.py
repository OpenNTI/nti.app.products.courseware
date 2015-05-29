#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Decorators for providing access to the various course pieces.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface

from zope.location.interfaces import ILocation

from pyramid.threadlocal import get_current_request

from nti.app.renderers.decorators import AbstractAuthenticatedRequestAwareDecorator

from nti.appserver.pyramid_authorization import has_permission

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseOutline
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.dataserver.interfaces import ILinkExternalHrefOnly

from nti.externalization.singleton import SingletonDecorator
from nti.externalization.interfaces import StandardExternalFields
from nti.externalization.externalization import to_external_object
from nti.externalization.interfaces import IExternalObjectDecorator
from nti.externalization.interfaces import IExternalMappingDecorator

from nti.dataserver.interfaces import IUser

from nti.links.links import Link

from . import VIEW_CONTENTS
from . import VIEW_CATALOG_ENTRY
from . import VIEW_COURSE_ACTIVITY
from . import VIEW_COURSE_RECURSIVE
from . import VIEW_COURSE_CLASSMATES
from . import VIEW_COURSE_RECURSIVE_BUCKET
from . import VIEW_COURSE_ENROLLMENT_ROSTER

from .utils import is_enrolled
from .utils import has_enrollments
from .utils import get_catalog_entry
from .utils import get_enrollment_record
from .utils import get_enrollment_options

from .interfaces import ACT_VIEW_ACTIVITY
from .interfaces import IOpenEnrollmentOption
from .interfaces import ICourseInstanceEnrollment

LINKS = StandardExternalFields.LINKS

COURSE_CONTEXT_ANNOT_KEY = 'nti.app.products.course.context_key'

@interface.implementer(IExternalMappingDecorator)
@component.adapter(ICourseInstance)
class _CourseInstanceLinkDecorator(object):
	"""
	If a course instance can find its catalog entry, return that as a link.
	Also make it return an href, even if it isn't top-level,
	and adds the enrollment stats (XXX That may be really slow.)
	"""

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping(self, context, result):
		# We have no way to know what order these will be
		# called in, so we must preserve anything that exists
		_links = result.setdefault(LINKS, [])
		entry = ICourseCatalogEntry(context, None)
		if entry:
			_links.append(Link(entry, rel=VIEW_CATALOG_ENTRY))

		request = get_current_request()
		if request is not None and has_permission(ACT_VIEW_ACTIVITY, context, request):
			# Give instructors the enrollment roster
			# and activity.
			# NOTE: Assuming the two permissions are concordant; at worst this is a UI
			# issue though, the actual views are protected with individual permissions
			for rel in VIEW_COURSE_ENROLLMENT_ROSTER, VIEW_COURSE_ACTIVITY:
				_links.append(Link(context,
									 rel=rel,
									 elements=(rel,)))

		if 'href' not in result:
			link = Link(context)
			interface.alsoProvides(link, ILinkExternalHrefOnly)
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
@component.adapter(ICourseInstance)
class _CourseInstanceStreamLinkDecorator(object):
	"""
	Place the recursive stream links on the course.
	"""

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping(self, context, result):
		_links = result.setdefault(LINKS, [])

		for name in (VIEW_COURSE_RECURSIVE, VIEW_COURSE_RECURSIVE_BUCKET):
			link = Link(context, rel=name, elements=(name,))
			interface.alsoProvides(link, ILocation)
			link.__name__ = ''
			link.__parent__ = context
			_links.append(link)

@interface.implementer(IExternalMappingDecorator)
@component.adapter(ICourseInstance)
class _CourseInstancePagesLinkDecorator(object):
	"""
	Places a link to the pages view of a course.
	"""

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping(self, context, result):
		_links = result.setdefault(LINKS, [])

		link = Link(context, rel='Pages', elements=('Pages',))
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		_links.append(link)

@interface.implementer(IExternalMappingDecorator)
@component.adapter(ICourseOutline)
class _CourseOutlineContentsLinkDecorator(object):
	"""
	Adds the Contents link to the course outline to fetch its children.
	"""
	# See comments in other places about generalization

	__metaclass__ = SingletonDecorator

	def decorateExternalMapping(self, context, result):
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
		entry = ICourseCatalogEntry(ICourseInstance(context, None), None)
		if hasattr(entry, 'ntiid'):
			result['CatalogEntryNTIID'] = entry.ntiid

		try:
			user = IUser(context)
		except TypeError:
			pass
		else:
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

@component.adapter(IOpenEnrollmentOption)
@interface.implementer(IExternalObjectDecorator)
class _OpenEnrollmentOptionLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		return self._is_authenticated

	@classmethod
	def _get_enrollment_record(cls, context, remoteUser):
		entry = get_catalog_entry(context.CatalogEntryNTIID)
		return get_enrollment_record(entry, remoteUser)

	def _do_decorate_external(self, context, result):
		record = self._get_enrollment_record(context, self.remoteUser)
		result['IsAvailable'] = context.Enabled and record is None
		result['IsEnrolled'] = bool(record is not None and record.Scope == ES_PUBLIC)

@component.adapter(ICourseCatalogEntry)
@interface.implementer(IExternalMappingDecorator)
class _CourseCatalogEntryDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		return self._is_authenticated

	def _do_decorate_external(self, context, result):
		record = get_enrollment_record(context, self.remoteUser)
		if record is not None:
			result['RealEnrollmentStatus'] = record.Scope

		options = get_enrollment_options(context)
		if options:
			result[u'EnrollmentOptions'] = to_external_object(options)

@interface.implementer(IExternalMappingDecorator)
class _BaseeClassmatesLinkDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _do_decorate_external(self, context, result):
		_links = result.setdefault(LINKS, [])
		link = Link(context, rel=VIEW_COURSE_CLASSMATES, elements=(VIEW_COURSE_CLASSMATES,))
		interface.alsoProvides(link, ILocation)
		link.__name__ = ''
		link.__parent__ = context
		_links.append(link)

@interface.implementer(IExternalMappingDecorator)
class _CourseClassmatesLinkDecorator(_BaseeClassmatesLinkDecorator):

	def _predicate(self, context, result):
		result = bool(self._is_authenticated and is_enrolled(context, self.remoteUser))
		return result

@component.adapter(IUser)
class _ClassmatesLinkDecorator(_BaseeClassmatesLinkDecorator):

	def _predicate(self, context, result):
		result = bool(self._is_authenticated and has_enrollments(self.remoteUser))
		return result

from nti.dataserver.interfaces import IContained

from nti.ntiids.ntiids import find_object_with_ntiid

@component.adapter(IContained)
@interface.implementer(IExternalMappingDecorator)
class _ContainedCatalogEntryDecorator(AbstractAuthenticatedRequestAwareDecorator):

	def _predicate(self, context, result):
		return bool(self._is_authenticated)

	def _do_decorate_external(self, context, result):
		containerId = context.containerId
		entry = container = find_object_with_ntiid(containerId) if containerId else None
		for iface in (ICourseInstance, ICourseCatalogEntry):
			entry = iface(container, None)
			if entry is not None:
				entry = ICourseCatalogEntry(entry, None)
				if entry is not None:
					result['CatalogEntryNTIID'] = entry.ntiid
				break
