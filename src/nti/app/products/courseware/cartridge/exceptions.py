#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)


class CommonCartridgeExportException(Exception):
    """
    This exception should be raised by an IMS Resource if an error occurs while attempting to convert
    an NTI object into a file store in the Common Cartridge. This exception class will be handled
    by the Common Cartridge and logged appropriately in the export documentation if needed. The formatting
    of this exception message should be intended for external viewing
    """
