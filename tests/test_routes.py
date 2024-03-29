"""
TestRecommendation API Service Test Suite
"""

import os
import logging
from unittest import TestCase
from wsgi import app
from service.common import status
from service.models import db, Recommendation
from .factories import RecommendationFactory

DATABASE_URI = os.getenv(
    "DATABASE_URI", "postgresql+psycopg://postgres:postgres@localhost:5432/testdb"
)
BASE_URL = "/recommendations"


######################################################################
#  T E S T   R E C O M M E N D A T I O N   S E R V I C E
######################################################################
class TestRecommendationService(TestCase):
    """Recommendation Server Tests"""

    # pylint: disable=duplicate-code
    @classmethod
    def setUpClass(cls):
        """Run once before all tests"""
        app.config["TESTING"] = True
        app.config["DEBUG"] = False
        # Set up the test database
        app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
        app.logger.setLevel(logging.CRITICAL)
        app.app_context().push()

    @classmethod
    def tearDownClass(cls):
        """Run once after all tests"""
        db.session.close()

    def setUp(self):
        """Runs before each test"""
        self.client = app.test_client()
        db.session.query(Recommendation).delete()  # clean up the last tests
        db.session.commit()

    def tearDown(self):
        db.session.remove()

    def _create_recommendations(self, count):
        """Factory method to create recommendations in bulk"""
        recommendations = []
        for _ in range(count):
            test_recommendation = RecommendationFactory()
            response = self.client.post(BASE_URL, json=test_recommendation.serialize())
            self.assertEqual(
                response.status_code,
                status.HTTP_201_CREATED,
                "Could not create test recommendation",
            )
            new_recommendation = response.get_json()
            test_recommendation.id = new_recommendation["id"]
            recommendations.append(test_recommendation)
        return recommendations

    ######################################################################
    #  T E S T   C A S E S
    ######################################################################
    # pylint: disable=too-many-public-methods

    def test_index(self):
        """It should return information about endpoints"""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("name", resp.json)
        self.assertIn("version", resp.json)
        self.assertIn("paths", resp.json)
        self.assertEqual(
            len(list(resp.json["paths"])),
            len(
                list(
                    filter(
                        lambda rule: rule.endpoint != "static", app.url_map.iter_rules()
                    )
                )
            ),
        )

    def test_get_recommendation(self):
        """It should Get a single Recommendation"""
        # get the id of a recommendation
        test_recommendation = self._create_recommendations(1)[0]
        response = self.client.get(f"{BASE_URL}/{test_recommendation.id}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(data["product_a_sku"], test_recommendation.product_a_sku)
        self.assertEqual(data["product_b_sku"], test_recommendation.product_b_sku)
        self.assertEqual(
            data["recommendation_type"], test_recommendation.recommendation_type.name
        )

    def test_get_recommendation_list(self):
        """It should Get a list of Recommendations"""
        self._create_recommendations(5)
        response = self.client.get(BASE_URL)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.get_json()
        self.assertEqual(len(data), 5)

    def test_delete_recommendation(self):
        """It should Delete a Recommendation"""
        test_recommendation = self._create_recommendations(1)[0]
        response = self.client.delete(f"{BASE_URL}/{test_recommendation.id}")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(len(response.data), 0)
        # make sure they are deleted
        response = self.client.get(f"{BASE_URL}/{test_recommendation.id}")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_recommendation(self):
        """It should Create a new Recommendation"""
        test_recommendation_data = RecommendationFactory()
        logging.debug(
            "Test Recommendation data: %s", test_recommendation_data.serialize()
        )
        response = self.client.post(BASE_URL, json=test_recommendation_data.serialize())
        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED,
            "Could not create test recommendation",
        )

        # Make sure location header is set
        location = response.headers.get("Location", None)
        self.assertIsNotNone(location)

        # Check the data is correct
        new_recommendation = response.get_json()
        self.assertEqual(
            new_recommendation["product_a_sku"], test_recommendation_data.product_a_sku
        )
        self.assertEqual(
            new_recommendation["product_b_sku"], test_recommendation_data.product_b_sku
        )
        self.assertEqual(
            new_recommendation["recommendation_type"],
            test_recommendation_data.recommendation_type.name,
        )

        # Check that the location header was correct
        response = self.client.get(location)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        new_recommendation_data = response.get_json()
        self.assertEqual(
            new_recommendation_data["product_a_sku"],
            test_recommendation_data.product_a_sku,
        )
        self.assertEqual(
            new_recommendation_data["product_b_sku"],
            test_recommendation_data.product_b_sku,
        )
        self.assertEqual(
            new_recommendation_data["recommendation_type"],
            test_recommendation_data.recommendation_type.name,
        )

    def test_update_recommendation(self):
        """It should Update an existing Recommendation"""
        # create a recommendation to update
        test_recommendation = RecommendationFactory()
        response = self.client.post(BASE_URL, json=test_recommendation.serialize())
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # update the recommendation
        new_recommendation = response.get_json()
        logging.debug(new_recommendation)
        new_recommendation["product_a_sku"] = "unknown"
        response = self.client.put(
            f"{BASE_URL}/{new_recommendation['id']}", json=new_recommendation
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        updated_recommendation = response.get_json()
        self.assertEqual(updated_recommendation["product_a_sku"], "unknown")

    def test_data_validation_error(self):
        """Test if submitting invalid data returns a data validation error"""
        invalid_data = {"product_a_sku": "123", "type": "InvalidType"}
        response = self.client.post("/recommendations", json=invalid_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.get_json())
        self.assertEqual(response.get_json()["error"], "Bad Request")

    def test_not_found(self):
        """Test if requesting a non-existent Recommendation returns a 404 Not Found"""
        response = self.client.get("/recommendations/9999")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn("error", response.get_json())
        self.assertEqual(response.get_json()["error"], "Not Found")

    def test_method_not_allowed(self):
        """Test if using an unsupported HTTP method returns a 405 Method Not Allowed"""
        response = self.client.put("/recommendations")
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertIn("error", response.get_json())
        self.assertEqual(response.get_json()["error"], "Method not Allowed")

    def test_unsupported_media_type(self):
        """Test if submitting with an unsupported media type returns a 415 Unsupported Media Type"""
        response = self.client.post(
            "/recommendations", data="plain text", content_type="text/plain"
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        self.assertIn("error", response.get_json())
        self.assertEqual(response.get_json()["error"], "Unsupported media type")

    def test_create_recommendation_duplicate(self):
        """It should not create a duplicate Recommendation"""
        recommendation_data = RecommendationFactory().serialize()
        # Create the first recommendation, which should succeed
        response = self.client.post(BASE_URL, json=recommendation_data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Attempt to create a duplicate recommendation, which should fail
        response = self.client.post(BASE_URL, json=recommendation_data)
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)
