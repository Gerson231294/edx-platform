"""Mixins to help test catalog integration."""
import json
import urllib
import httpretty
from openedx.core.djangoapps.catalog.models import CatalogIntegration


class CatalogIntegrationMixin(object):
    """Utility for working with the catalog service during testing."""

    DEFAULTS = {
        'enabled': True,
        'internal_api_url': 'https://catalog-internal.example.com/api/v1/',
        'cache_ttl': 0,
    }

    def create_catalog_integration(self, **kwargs):
        """Creates a new CatalogIntegration with DEFAULTS, updated with any provided overrides."""
        fields = dict(self.DEFAULTS, **kwargs)
        CatalogIntegration(**fields).save()

        return CatalogIntegration.current()

    def register_catalog_course_run_response(self, course_keys, catalog_course_run_data):
        """
        Register a mock response for GET on the catalog course run endpoint.
        """
        httpretty.register_uri(
            httpretty.GET,
            "http://catalog.example.com:443/api/v1/course_runs/?keys={}&exclude_utm=1".format(
                urllib.quote_plus(",".join(course_keys))
            ),
            body=json.dumps({
                "results": catalog_course_run_data,
                "next": ""
            }),
            content_type='application/json',
            status=200
        )

    def minimum_catalog_course_run_object(self, course_key, has_marketing_url=True):
        """
        Returns catalog course run object with minimum fields.
        """
        return {
            "key": course_key,
            "marketing_url": ("https://marketing-url/course/course-title-{}".format(course_key)
                              if has_marketing_url else None),
            "test_key": "test_value",
        }
