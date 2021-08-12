#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id: zcml.py 124707 2017-12-08 21:48:18Z carlos.sanchez $
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=inherit-non-class

import functools

from pyramid.interfaces import IRequest

from zope import interface

from zope.component.zcml import utility

from zope.schema import TextLine

from nti.app.products.courseware.completion.interfaces import ICertificateRenderer

from nti.app.products.courseware.completion.model import CertificateRenderer

logger = __import__('logging').getLogger(__name__)


class IRegisterCertificateRenderer(interface.Interface):

    name = TextLine(title=u'The registration name',
                    required=True)

    macro_name = TextLine(title=u'The cert macro name',
                             required=True,
                             default=u'certificate')


def registerCertificateRenderer(_context,
                                name,
                                macro_name=None):
    factory = functools.partial(CertificateRenderer,
                                macro_name=macro_name)
    utility(_context, provides=ICertificateRenderer, factory=factory, name=name)

