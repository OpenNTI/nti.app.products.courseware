#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views relating to the course catalog and the courses workspace.

The initial strategy is to use a path adapter named Courses. It will
return something that isn't traversable (in this case, the Courses
workspace). Named views will be registered based on that to implement
the workspace collections.

$Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from zope.traversing.interfaces import IPathAdapter
from nti.dataserver.interfaces import IUser
from pyramid.interfaces import IRequest
from nti.appserver.interfaces import IUserService
from .interfaces import ICoursesWorkspace
from .interfaces import ICourseCatalogEntry

from pyramid.view import view_config
from nti.appserver.dataserver_pyramid_views import GenericGetView

@interface.implementer(IPathAdapter)
@component.adapter(IUser, IRequest)
def CoursesPathAdapter(context, request):
	service = IUserService(context)
	workspace = ICoursesWorkspace(service)

	return workspace


@view_config(context=ICourseCatalogEntry)
class CatalogGenericGetView(GenericGetView):
	pass
