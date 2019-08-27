#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import itertools

from zope import component
from zope import interface

from zope.container.contained import Contained

from nti.app.products.courseware.interfaces import ICourseSharingScopeUtility

from nti.containers.containers import EventlessLastModifiedBTreeContainer

from nti.wref.interfaces import IWeakRef

logger = __import__('logging').getLogger(__name__)


@interface.implementer(ICourseSharingScopeUtility)
class CourseSharingScopeUtility(EventlessLastModifiedBTreeContainer, Contained):

    def iter_scopes(self, scope_name=None, parent_scopes=True):
        """
        Iterate over the sharing scopes within this utility, optionally
        filtering by scope name.
        If `parent_scopes` is False, we do not query the parent site
        utility.
        """
        for scope_ref in self.values():
            scope = scope_ref()
            if scope is not None:
                if not scope_name:
                    yield scope
                elif scope.__name__ == scope_name:
                    yield scope
        if parent_scopes:
            parent_utility = component.queryNextUtility(self, ICourseSharingScopeUtility)
            if parent_utility is not None:
                for scope in parent_utility.iter_scopes(scope_name, parent_scopes):
                    yield scope

    def iter_ntiids(self, parent_ntiids=True):
        """
        Iterate over the scope NTIIDs.
        """
        result = iter(self)
        if parent_ntiids:
            parent_utility = component.queryNextUtility(self, ICourseSharingScopeUtility)
            if parent_utility is not None:
                result = itertools.chain(result, parent_utility.iter_ntiids(parent_ntiids))
        return result

    def add_scope(self, scope):
        """
        Add a scope to the utility.
        """
        ref = IWeakRef(scope)
        self[scope.NTIID] = ref

    def remove_scope(self, scope):
        """
        Remove a scope from the utility.
        """
        try:
            del self[scope.NTIID]
            return True
        except KeyError:
            return False
