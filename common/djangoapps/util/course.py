"""
Utility methods related to course
"""
import logging
from django.conf import settings

from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.catalog.utils import get_run_marketing_urls

log = logging.getLogger(__name__)


def get_link_for_about_page(course_key, user, course_marketing_url_dict=None):
    """
    Returns the url to the course about page.
    """
    #assert isinstance(course_key, CourseKey)
    if settings.FEATURES.get('ENABLE_MKTG_SITE'):
        print "\n marketing site enabled \n"
        if not course_marketing_url_dict or course_key not in course_marketing_url_dict:
            course_marketing_url_dict = get_run_marketing_urls(user, [course_key])
        if course_key in course_marketing_url_dict and course_marketing_url_dict[course_key]:
            return course_marketing_url_dict[course_key]

    return u"{about_base_url}/courses/{course_key}/about".format(
        about_base_url=settings.LMS_ROOT_URL,
        course_key=course_key
    )
