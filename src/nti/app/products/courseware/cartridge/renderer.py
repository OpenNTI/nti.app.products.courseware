#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

import six

from pyramid.path import caller_package

from pyramid.renderers import get_renderer as pyramid_get_renderer

from zope import interface

from zope.dottedname import resolve as dottedname

from zope.publisher.interfaces.browser import IBrowserRequest

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IBrowserRequest)
class Request(object):
    context = None
    response = None
    annotations = {}

    def get(self, unused_key, default=None):
        return default


def get_renderer_spec_and_package(base_template, extension,
                                  package=None, level=3):
    if isinstance(package, six.string_types):
        package = dottedname.resolve(package)

    # Did they give us a package, either in the name or as an argument?
    # If not, we need to get the right package
    if ':' not in base_template and package is None:
        # 2 would be our caller, aka this module.
        package = caller_package(level)
    # Do we need to look in a subdirectory?
    if ':' not in base_template and '/' not in base_template:
        base_template = 'templates/' + base_template

    if extension == '.mak' and ':' not in base_template:
        base_template = package.__name__ + ':' + base_template

    return base_template + extension, package


def get_renderer(base_template, extension,
                 package=None, level=3):
    """
    Given a template name, find a renderer for it.
    For template name, we accept either a relative or absolute
    asset spec. If the spec is relative, it can be 'naked', in which
    case it is assummed to be in the templates sub directory.

    This *must* only be called from this module due to assumptions
    about the call tree.
    """

    template, package = get_renderer_spec_and_package(base_template, extension,
                                                      package=package, level=level + 1)

    return pyramid_get_renderer(template, package)


def execute(renderer, values, request=None, view=None):
    request = Request() if request is None else request
    system_values = {"request": request, 'view': view}
    return renderer(values, system_values)
