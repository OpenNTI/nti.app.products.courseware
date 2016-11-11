================
 Course Catalog
================

Interfaces
==========

Access to courses begins by finding them. Courses are described in a
course catalog:

.. autointerface:: nti.contenttypes.courses.interfaces.ICourseCatalog
	:noindex:

The course catalog is made up of entries:

.. autointerface:: nti.contenttypes.courses.interfaces.ICourseCatalogEntry
	:noindex:
.. autointerface:: nti.contenttypes.courses.interfaces.ICourseCatalogInstructorInfo
	:noindex:

and legacy entries:

.. autointerface:: nti.contenttypes.courses.legacy_catalog.ICourseCatalogLegacyEntry
	:noindex:
.. autointerface:: nti.contenttypes.courses.legacy_catalog.ICourseCreditLegacyInfo
	:noindex:
.. autointerface:: nti.contenttypes.courses.legacy_catalog.ICourseCatalogInstructorLegacyInfo
	:noindex:

Implementation
==============

These are implemented here:

.. automodule:: nti.contenttypes.courses.legacy_catalog

.. autoclass:: nti.contenttypes.courses.legacy_catalog.CourseCatalogLegacyEntry
.. autoclass:: nti.contenttypes.courses.legacy_catalog.CourseCatalogInstructorLegacyInfo
.. autoclass:: nti.contenttypes.courses.legacy_catalog.CourseCreditLegacyInfo

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
