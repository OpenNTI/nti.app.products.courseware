#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from . import MessageFactory as _

import isodate
import datetime

from zope import component
from zope.i18n import translate
from zope.security.interfaces import IPrincipal
from zope.lifecycleevent import IObjectAddedEvent
from zope.security.management import queryInteraction
from zope.publisher.interfaces.browser import IBrowserRequest

from pyramid.threadlocal import get_current_request

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.contenttypes.courses.interfaces import ES_CREDIT_DEGREE
from nti.contenttypes.courses.interfaces import ES_CREDIT_NONDEGREE
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceEnrollmentRecord

from nti.dataserver.users.interfaces import IUserProfile
from nti.dataserver.users.interfaces import IEmailAddressable

from nti.externalization.externalization import to_external_object

from nti.mailer.interfaces import ITemplatedMailer

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

	args = {'profile': profile,
			'context': event,
			'user': user,
			'informal_username': informal_username,
			'course': catalog_entry,
			'support_email': support_email,
			'show_for_credit_option': True,
			'course_start_date': course_start_date,
			'instructors_html_signature': html_sig,
			'today': isodate.date_isoformat(datetime.datetime.now()) }


	course_end_date = catalog_entry.EndDate

	if course_end_date and course_end_date < datetime.datetime.utcnow():
		template = 'archived_enrollment_confirmation_email'
	elif not catalog_entry.Preview:
		template = 'inprogress_enrollment_confirmation_email'
	else:
		template = 'enrollment_confirmation_email'
		####
		## HACK
		## The best way to do this would be with
		## content providers and/or configured objects
		## in the database and/or ZCA. However, this is faster
		## Also OU specific, need to fix this.
		####
		template_map = {
			"Gateway to College Learning": 'hack_gateway_'
		}
		prefix = template_map.get( catalog_entry.Title, '' )
		template = prefix + template

	package = getattr( policy, 'PACKAGE', 'nti.app.products.courseware' )

	component.getUtility(ITemplatedMailer).queue_simple_html_text_email(
		template,
		subject=translate(_("Welcome to ${title}",
							mapping={'title': catalog_entry.Title})),
		recipients=[profile],
		template_args=args,
		request=request,
		package=package,)

@component.adapter(ICourseInstanceEnrollmentRecord,IObjectAddedEvent)
def _enrollment_added(record, event):
	# We only want to do this when the user initiated the event,
	# not when it was done via automatic workflow.
	if queryInteraction() is None:
		# no interaction, no email
		return

	# For now, the easiest way to detect that is to know that
	# automatic workflow is the only way to enroll in ES_CREDIT_DEGREE.
	# We also want a special email for 5-ME, so we avoid those as well.
	if 	record.Scope in (ES_CREDIT_DEGREE, ES_CREDIT_NONDEGREE):
		return

	creator = event.object.Principal
	profile = IUserProfile(creator)
	email = getattr(profile, 'email', None)

	# Exactly one course at a time
	course = record.CourseInstance
	_send_enrollment_confirmation(event, creator, profile, email, course)
