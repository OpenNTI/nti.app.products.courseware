================
 Course Catalog
================

Interfaces
==========

Access to courses begins by finding them. Courses are described in a
course catalog:

.. autointerface:: nti.app.products.courseware.interfaces.ICourseCatalog
	:noindex:

The course catalog is made up of entries:

.. autointerface:: nti.app.products.courseware.interfaces.ICourseCatalogEntry
	:noindex:
.. autointerface:: nti.app.products.courseware.interfaces.ICourseCatalogInstructorInfo
	:noindex:

and legacy entries:

.. autointerface:: nti.app.products.courseware.interfaces.ICourseCatalogLegacyEntry
	:noindex:
.. autointerface:: nti.app.products.courseware.interfaces.ICourseCreditLegacyInfo
	:noindex:
.. autointerface:: nti.app.products.courseware.interfaces.ICourseCatalogInstructorLegacyInfo
	:noindex:

Implementation
==============

These are implemented here:

.. automodule:: nti.app.products.courseware.catalog

.. autoclass:: nti.app.products.courseware.legacy.CourseCatalogLegacyEntry
.. autoclass:: nti.app.products.courseware.legacy.CourseCatalogInstructorLegacyInfo
.. autoclass:: nti.app.products.courseware.legacy.CourseCreditLegacyInfo

ReST
====

Accessing the course catalog is done through the users ``Courses`` workspace
and its ``AllCourses`` collection.

.. autofunction:: nti.app.products.courseware.workspaces.CoursesWorkspace
.. autoclass:: nti.app.products.courseware.workspaces._CoursesWorkspace
	:members: __name__, collections, __getitem__
	:special-members:

.. autoclass:: nti.app.products.courseware.workspaces.AllCoursesCollection
	:members: __name__, __getitem__
	:special-members:
