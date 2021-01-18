#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=inherit-non-class,expression-not-assigned

from zope.container.constraints import contains

from zope.container.interfaces import IContainer

from nti.app.products.acclaim.interfaces import IAcclaimBadge


class ICourseAcclaimBadgeContainer(IContainer):
    """
    A storage container for :class:`IAcclaimBadge` objects, accessible on the course context.
    """
    contains(IAcclaimBadge)

    def get_or_create_badge(badge):
        """
        Normalize the given :class:`IAcclaimBadge` in our container.
        """
