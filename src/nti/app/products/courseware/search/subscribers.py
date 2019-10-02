#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.intid.interfaces import IIntIds

from nti.contentsearch.interfaces import ISearchPackageResolver

from nti.contenttypes.courses.index import IX_SITE
from nti.contenttypes.courses.index import IX_USERNAME

from nti.contenttypes.courses.common import get_course_packages

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry

from nti.contenttypes.courses.utils import get_enrollment_catalog

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.site import get_component_hierarchy_names

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ISearchPackageResolver)
class _CourseSearchPacakgeResolver(object):

    __slots__ = ()

    def __init__(self, *args):
        pass

    def resolve(self, user, ntiid=None):
        result = set()
        if ntiid:
            # If course ntiid, return the packages under it
            obj = find_object_with_ntiid(ntiid)
            if     ICourseInstance.providedBy(obj) \
                or ICourseCatalogEntry.providedBy(obj):
                course = ICourseInstance(obj)
                result.update(x.ntiid for x in get_course_packages(course))
        else:
            # Otherwise return all enrollment courses and packages
            catalog = get_enrollment_catalog()
            intids = component.getUtility(IIntIds)
            site_names = get_component_hierarchy_names()
            query = {
                IX_SITE: {'any_of': site_names},
                IX_USERNAME: {'any_of': (user.username,)}
            }
            for uid in catalog.apply(query) or ():
                context = intids.queryObject(uid)
                context = ICourseInstance(context, None)
                if context is not None:
                    result.update(x.ntiid for x in get_course_packages(context))
                    entry = ICourseCatalogEntry(context, None)
                    # include catalog entry
                    result.add(getattr(entry, 'ntiid', None))
            result.discard(None)
        return result
