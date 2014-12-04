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
from functools import partial
from collections import defaultdict

import gevent

import transaction

from zope import component

from zope.component.hooks import getSite
from zope.component.hooks import site as current_site

from zope.traversing.interfaces import IEtcNamespace

from zope.dottedname import resolve as dottedname

from zope.i18n import translate

from zope.lifecycleevent import IObjectAddedEvent
from zope.lifecycleevent import IObjectRemovedEvent

from zope.publisher.interfaces.browser import IBrowserRequest

from zope.security.interfaces import IPrincipal
from zope.security.management import queryInteraction

from pyramid.threadlocal import get_current_request

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.contenttypes.courses.interfaces import ES_PURCHASED
from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE
from nti.contenttypes.courses.interfaces import ES_CREDIT_NONDEGREE

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import IPrincipalEnrollments
from nti.contenttypes.courses.interfaces import ICourseEnrollmentManager
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDataserverTransactionRunner

from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IEmailAddressable

from nti.externalization.externalization import to_external_object

from nti.mailer.interfaces import ITemplatedMailer

from nti.site.hostpolicy import run_job_in_all_host_sites

## Email

def _send_enrollment_confirmation(event, user, profile, email, course):
	# Note that the `course` is an nti.contenttypes.courses.ICourseInstance

	# Can only do this in the context of a user actually
	# doing something; we need the request for locale information
	# as well as URL information.
	request = getattr(event, 'request', get_current_request())
	if not request or not email:
		logger.warn("Not sending an enrollment email to %s because of no email or request",
					user )
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
		course_start_date = formatter.format( catalog_entry.StartDate )

	html_sig = catalog_entry.InstructorsSignature.replace('\n', "<br />")

	support_email = getattr( policy, 'SUPPORT_EMAIL', 'support@nextthought.com' )
	course_end_date = catalog_entry.EndDate
	course_preview = catalog_entry.Preview
	course_archived = course_end_date and course_end_date < datetime.datetime.utcnow()

	for_credit_url = getattr( policy, 'FOR_CREDIT_URL', '' )
	site_alias = getattr( policy, 'COM_ALIAS', '' )

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

	package = getattr( policy, 'PACKAGE', 'nti.app.products.courseware' )

	template = 'enrollment_confirmation_email'
	template = _get_template( catalog_entry, template, package )

	component.getUtility(ITemplatedMailer).queue_simple_html_text_email(
		template,
		subject=translate(_("Welcome to ${title}",
							mapping={'title': catalog_entry.Title})),
		recipients=[profile],
		template_args=args,
		request=request,
		package=package,)

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
	if record.Scope in (ES_CREDIT_DEGREE, ES_CREDIT_NONDEGREE, ES_PURCHASED):
		return

	creator = event.object.Principal
	profile = IUserProfile(creator)
	email = getattr(profile, 'email', None)

	# Exactly one course at a time
	course = record.CourseInstance
	_send_enrollment_confirmation(event, creator, profile, email, course)

def _get_template(catalog_entry, base_template, package):
	"""Look for course-specific templates, if available."""
	package = dottedname.resolve(package)
	provider = catalog_entry.ProviderUniqueID.replace(' ', '').lower()
	template = provider + "_" + base_template
	path = os.path.join(os.path.dirname(package.__file__), 'templates')
	if not os.path.exists(os.path.join(path, template + ".pt")):
		template = base_template
	return template

## Users

def _delete_user_enrollment_data(username, enrollments=None):
	logger.info("Removing enrollment data for user %s", username)

	result = defaultdict(list)
	principal = IPrincipal(username)
	sites = component.getUtility(IEtcNamespace, name='hostsites')
	enrollments = {} if  enrollments is None else enrollments
	for name, entries in enrollments.items():
		if not entries:
			continue
		try:
			site = sites[name]
			with current_site(site):
				catalog = component.getUtility(ICourseCatalog)
				for ntiid in entries:
					try:
						entry = catalog.getCatalogEntry(ntiid)
						course = ICourseInstance(entry, None)
						enrollments = ICourseEnrollmentManager(course, None)
						if enrollments is not None:
							enrollments.drop(principal)
							result[name].append(ntiid)
					except KeyError:
						pass
		except KeyError:
			pass
	return result

def _get_enrollment_data(user):
	result = defaultdict(list)
	def _collector():
		name = getSite().__name__
		for enrollments in component.subscribers( (user,), IPrincipalEnrollments):
			for enrollment in enrollments.iter_enrollments():
				course = ICourseInstance(enrollment, None)
				entry = ICourseCatalogEntry(course, None)
				if entry is not None:
					result[name].append(entry.ntiid)
	run_job_in_all_host_sites(_collector)
	return result

@component.adapter(IUser, IObjectRemovedEvent)
def _on_user_removed(user, event):
	username = user.username

	## get enrollments per site
	enrollments = _get_enrollment_data(user)

	## remove all enrollments in an after commit hook
	## in case some other event listeners require the enrollment data
	def _process_event():
		transaction_runner = component.getUtility(IDataserverTransactionRunner)
		func = partial(_delete_user_enrollment_data,
					   username=username,
					   enrollments=enrollments)
		transaction_runner(func)
		return True

	transaction.get().addAfterCommitHook(
					lambda success: success and gevent.spawn(_process_event))
