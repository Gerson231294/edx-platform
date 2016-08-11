"""
Utility methods related to course
"""
import logging
from django.conf import settings

from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.catalog.utils import get_run_marketing_url

log = logging.getLogger(__name__)


def get_link_for_about_page(course_key, user):
    """
    Returns the url to the course about page.
    """
    assert isinstance(course_key, CourseKey)

    if settings.FEATURES.get('ENABLE_MKTG_SITE'):
        about_base = get_run_marketing_url(course_key, user)
        if about_base:
            return about_base

    return u"{about_base_url}/courses/{course_key}/about".format(
        about_base_url=settings.LMS_ROOT_URL,
        course_key=course_key.to_deprecated_string()
    )
