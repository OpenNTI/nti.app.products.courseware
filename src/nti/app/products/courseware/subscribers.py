#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from . import MessageFactory as _

import os
import isodate
import datetime

from zope import component

from zope.dottedname import resolve as dottedname

from zope.i18n import translate

from zope.lifecycleevent import IObjectAddedEvent

from zope.publisher.interfaces.browser import IBrowserRequest

from zope.security.interfaces import IPrincipal
from zope.security.management import queryInteraction

from pyramid.threadlocal import get_current_request

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.contenttypes.courses.interfaces import ES_PUBLIC
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseSubInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IDenyOpenEnrollment
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.dataserver.users import Entity
from nti.dataserver.interfaces import ICommunity
from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IEmailAddressable

from nti.externalization.externalization import to_external_object

from nti.mailer.interfaces import ITemplatedMailer

from nti.ntiids.ntiids import find_object_with_ntiid

from .utils import get_enrollment_courses
from .utils import get_enrollment_communities

# Email

def _get_template(catalog_entry, base_template, package):
	"""
	Look for course-specific templates, if available.
	"""
	result = None
	package = dottedname.resolve(package)
	for provider in (catalog_entry.ProviderUniqueID, catalog_entry.DisplayName):
		if not provider:
			continue
		provider = provider.replace(' ', '').lower()
		replaced_provider = provider.replace('-', '')
		template = replaced_provider + "_" + base_template
		path = os.path.join(os.path.dirname(package.__file__), 'templates')
		if not os.path.exists(os.path.join(path, template + ".pt")):
			# Full path doesn't exist; drop our specific id part and try that
			# 'EDMA 4970', 'EDMA 4970-995', EDMA 4970/5970-995'
			provider_prefix = provider.split('-')[0]
			provider_prefix = provider_prefix.split('/')[0]
			template = provider_prefix + "_" + base_template
			if os.path.exists(os.path.join(path, template + ".pt")):
				result = template
				break
		else:
			result = template
			break
	return result or base_template

def _send_enrollment_confirmation(event, user, profile, email, course):
	# Note that the `course` is an nti.contenttypes.courses.ICourseInstance

	# Can only do this in the context of a user actually
	# doing something; we need the request for locale information
	# as well as URL information.
	request = getattr(event, 'request', get_current_request())
	if not request or not email:
		logger.warn("Not sending an enrollment email to %s because of no email or request",
					user)
		return

	policy = component.getUtility(ISitePolicyUserEventListener)

	assert getattr(IEmailAddressable(profile, None), 'email', None) == email
	assert getattr(IPrincipal(profile, None), 'id', None) == user.username

	user_ext = to_external_object(user)
	informal_username = user_ext.get('NonI18NFirstName', profile.realname) or user.username

	catalog_entry = ICourseCatalogEntry(course)

	course_start_date = ''

	if catalog_entry.StartDate:
		locale = IBrowserRequest(request).locale
		dates = locale.dates
		formatter = dates.getFormatter('date', length='long')
		course_start_date = formatter.format(catalog_entry.StartDate)

	html_sig = catalog_entry.InstructorsSignature.replace('\n', "<br />")

	support_email = getattr(policy, 'SUPPORT_EMAIL', 'support@nextthought.com')
	course_end_date = catalog_entry.EndDate
	course_preview = catalog_entry.Preview
	course_archived = course_end_date and course_end_date < datetime.datetime.utcnow()

	for_credit_url = getattr(policy, 'FOR_CREDIT_URL', '')
	site_alias = getattr(policy, 'COM_ALIAS', '')

	args = {'profile': profile,
			'context': event,
			'user': user,
			'informal_username': informal_username,
			'course': catalog_entry,
			'support_email': support_email,
			'for_credit_url': for_credit_url,
			'site_alias': site_alias,
			'request': request,
			'brand': policy.BRAND,
			'course_start_date': course_start_date,
			'instructors_html_signature': html_sig,
			'course_preview': course_preview,
			'course_archived': course_archived,
			'today': isodate.date_isoformat(datetime.datetime.now()) }

	package = getattr(policy, 'PACKAGE', 'nti.app.products.courseware')

	template = 'enrollment_confirmation_email'
	template = _get_template(catalog_entry, template, package)

	mailer = component.getUtility(ITemplatedMailer)
	mailer.queue_simple_html_text_email(
					template,
					subject=translate(_("Welcome to ${title}",
										mapping={'title': catalog_entry.Title})),
					recipients=[profile],
					template_args=args,
					request=request,
					package=package,
					text_template_extension='.mak')

@component.adapter(ICourseInstanceEnrollmentRecord, IObjectAddedEvent)
def _enrollment_added(record, event):
	# We only want to do this when the user initiated the event,
	# not when it was done via automatic workflow.
	if queryInteraction() is None:
		# no interaction, no email
		return

	# For now, the easiest way to detect that is to know that
	# automatic workflow is the only way to enroll in ES_CREDIT_DEGREE.
	# We also want a special email for 5-ME, so we avoid those as well.
	if record.Scope != ES_PUBLIC:
		return

	creator = event.object.Principal
	profile = IUserProfile(creator)
	email = getattr(profile, 'email', None)

	# Exactly one course at a time
	course = record.CourseInstance
	_send_enrollment_confirmation(event, creator, profile, email, course)

@component.adapter(ICourseInstanceEnrollmentRecord, IObjectAddedEvent)
def _join_communities_on_enrollment_added(record, event):
	course = record.CourseInstance

	# get communities
	communities = set(get_enrollment_communities(course) or ())
	if not communities and ICourseSubInstance.providedBy(course):
		course = course.__parent__.__parent__
		communities = set(get_enrollment_communities(course) or ())
	if not communities:
		return

	# check for dup enrollment
	principal = IPrincipal(record.Principal, None)
	user = Entity.get_entity(principal.id) if principal else None
	if user is None:
		return

	for name in communities:
		community = Entity.get_entity(name)
		if community is None or not ICommunity.providedBy(community):
			logger.warn("Community %s does not exists", name)
			continue
		user.record_dynamic_membership(community)
		user.follow(community)

@component.adapter(ICourseInstanceEnrollmentRecord, IObjectAddedEvent)
def _auto_enroll_on_enrollment_added(record, event):
	course = record.CourseInstance
	main_entry = ICourseCatalogEntry(course, None)
	if main_entry is None:
		return

	# get parent course
	parent = course
	if ICourseSubInstance.providedBy(course):
		parent = course.__parent__.__parent__

	# get all catalog entries in the hierarchy
	main_entries = map(lambda x: ICourseCatalogEntry(x, None),
				  	   parent.SubInstances.values())
	main_entries.append(main_entry)
	
	# check for dup enrollment
	principal = IPrincipal(record.Principal, None)
	user = Entity.get_entity(principal.id) if principal else None
	if user is None:
		return

	# get course entries
	entries = set(get_enrollment_courses(course) or ())
	if not entries and ICourseSubInstance.providedBy(course):
		course = course.__parent__.__parent__
		entries = set(get_enrollment_courses(course) or ())
	if not entries:
		return

	for name in entries:
		entry = ICourseCatalogEntry(find_object_with_ntiid(name), None)
		if entry is None:
			logger.warn("Course entry %s does not exists", name)
			continue
		# make sure avoid circles
		if entry in main_entries:
			continue
		# check for deny open enrollment
		course = ICourseInstance(entry)
		if IDenyOpenEnrollment.providedBy(course) and record.Scope == ES_PUBLIC:
			continue
		# ready to enroll
		manager = ICourseEnrollmentManager(course)
		enrollment = manager.get_enrollment_for_principal(user)
		if enrollment is None:
			manager.enroll(user, scope=record.Scope)
