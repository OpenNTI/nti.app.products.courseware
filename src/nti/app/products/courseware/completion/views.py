#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from pyramid.view import view_config

from zc.displayname.interfaces import IDisplayNameGenerator

from nti.appserver.policies.interfaces import ISitePolicyUserEventListener

from nti.appserver.policies.site_policies import guess_site_display_name

from nti.dataserver import authorization as nauth

from nti.dataserver.users.interfaces import IFriendlyNamed

from nti.app.base.abstract_views import AbstractAuthenticatedView

from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment

from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

@view_config(route_name='objects.generic.traversal',
	     renderer="templates/completion_certificate.rml",
	     request_method='GET',
	     context=ICourseInstanceEnrollment,
	     name="Certificate",
	     permission=nauth.ACT_READ)
class CompletionCertificateView(AbstractAuthenticatedView):

    @property
    def _name(self):
        user = self.remoteUser
        
        # A certificate is fairly formal so try and use realname first
        name = IFriendlyNamed(self.remoteUser).realname
        if not name:
            # Otherwise just fallback to whatever is our display name generator
            name = component.getMultiAdapter((user, self.request), IDisplayNameGenerator)()
        return name

    @property
    def _brand(self):
        policy = component.getUtility(ISitePolicyUserEventListener)
	display_name = getattr(policy, 'BRAND', '')
	if display_name:
	    display_name = display_name.strip()
	else:
	    display_name = guess_site_display_name(self.request)
        return display_name
    
    def __call__(self):
        response = self.request.response
        #response.content_disposition = 'attachment; filename="completion.pdf"'
        from IPython.core.debugger import Tracer; Tracer()()
        entry = ICourseCatalogEntry(self.context.CourseInstance)
        
        return {
            u'Brand': self._brand,
            u'Name': self._name,
            u'Course': entry.title,
            u'Date': 'February 15, 1986',
            u'Hours': 1,
            u'Title': 'Completion Certificate'
        }
