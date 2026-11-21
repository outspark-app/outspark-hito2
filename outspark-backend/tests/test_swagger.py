"""El contrato Swagger debe describir las respuestas y la identidad de la API real."""

import json
import unittest

from outspark.bootstrap import create_app
from outspark.shared.interfaces.http.documentation import ErrorResponse
from tests import test_framework as framework


class SwaggerTests(unittest.TestCase):
    setUp = framework.FrameworkTests.setUp
    stop_http = framework.FrameworkTests.stop_http

    def test_all_operations_have_stable_ids_models_and_correct_validation_errors(self):
        schema = self.client.get("/openapi.json").json()
        ids = []
        for path, methods in schema["paths"].items():
            for method, operation in methods.items():
                ids.append(operation["operationId"])
                self.assertTrue(operation["summary"])
                self.assertTrue(operation["description"])
                creates_resource = (
                    method == "post" and operation["operationId"] != "compareDiffusionPlans"
                )
                code = "201" if creates_resource else "200"
                self.assertIn(
                    "$ref", operation["responses"][code]["content"]["application/json"]["schema"]
                )
                self.assertNotIn("HTTPValidationError", json.dumps(operation))
                if path != "/api/health":
                    self.assertEqual(operation["security"], [{"DemoUser": []}])
                    self.assertIn("401", operation["responses"])
                else:
                    self.assertEqual(operation["security"], [])
        self.assertEqual(len(ids), 31)
        self.assertEqual(len(set(ids)), 31)
        self.assertNotIn("422", schema["paths"]["/api/me/preferences"]["put"]["responses"])
        self.assertIn(
            "422",
            schema["paths"]["/api/feed/{snapshot_id}/cards/{publication_id}/provenance"]["get"][
                "responses"
            ],
        )
        self.assertEqual(schema["components"]["securitySchemes"]["DemoUser"]["name"], "X-Demo-User")
        self.assertFalse(self.app.swagger_ui_parameters["persistAuthorization"])

    def test_cloud_documentation_exposes_only_gateway_jwt(self):
        schema = create_app(self.services, local_demo=False).openapi()
        self.assertEqual(set(schema["components"]["securitySchemes"]), {"GatewayJWT"})
        self.assertEqual(schema["components"]["securitySchemes"]["GatewayJWT"]["scheme"], "bearer")
        self.assertEqual(schema["paths"]["/api/me"]["get"]["security"], [{"GatewayJWT": []}])
        self.assertNotIn("DemoUser", json.dumps(schema))

    def test_idempotency_header_and_request_examples_are_documented(self):
        schema = self.app.openapi()
        for path in (
            "/api/publications",
            "/api/reposts",
            "/api/publications/{publication_id}/comments",
        ):
            operation = schema["paths"][path]["post"]
            header = next(p for p in operation["parameters"] if p["name"] == "Idempotency-Key")
            self.assertTrue(header["required"])
            self.assertEqual(header["schema"]["maxLength"], 128)
            self.assertIn("200", operation["responses"])
            self.assertIn("201", operation["responses"])
        publish = schema["components"]["schemas"]["PublishResource"]["properties"]
        self.assertEqual(publish["community_id"]["examples"][0], "diseno")
        self.assertEqual(publish["topic_ids"]["maxItems"], 3)
        self.assertTrue(publish["topic_ids"]["uniqueItems"])

    def test_success_models_match_all_product_operations_and_replays(self):
        from outspark.shared.interfaces.http.documentation import ResponseResource

        models = {}
        pending = [ResponseResource]
        while pending:
            model = pending.pop()
            models[model.__name__] = model
            pending.extend(model.__subclasses__())
        schema = self.app.openapi()
        observed = set()

        def call(method, path, actor="ana", data=None, key=None, route=None):
            headers = {
                "X-Demo-User": actor,
                "Origin": str(self.client.base_url).rstrip("/"),
            }
            if key:
                headers["Idempotency-Key"] = key
            response = self.client.request(method, path, headers=headers, json=data)
            self.assertIn(response.status_code, (200, 201), response.text)
            route_path = route or path.split("?")[0]
            ref = schema["paths"][route_path][method.lower()]["responses"][
                str(response.status_code)
            ]["content"]["application/json"]["schema"]["$ref"]
            model = models[ref.split("/")[-1]]
            model.model_validate(response.json())
            observed.add((route_path, method))
            return response.json()

        call("GET", "/api/health")
        call("GET", "/api/me/publications")
        call("GET", "/api/me")
        call(
            "PUT",
            "/api/me/preferences",
            "diego",
            {"topic_ids": ["diseno", "tecnologia"], "version": 1},
        )
        call("GET", "/api/me/contacts", "diego")
        call("GET", "/api/communities")
        call("GET", "/api/topics")
        call("GET", "/api/me/communities")
        call("PUT", "/api/me/communities/diseno", "bruno", route="/api/me/communities/{community}")
        call(
            "DELETE", "/api/me/communities/diseno", "bruno", route="/api/me/communities/{community}"
        )
        payload = {
            "community_id": "diseno",
            "body": "Documentar el recorrido de una idea.",
            "topic_ids": ["diseno"],
        }
        post = call("POST", "/api/publications", data=payload, key="swagger-publish")
        replay = call("POST", "/api/publications", data=payload, key="swagger-publish")
        self.assertTrue(replay["replayed"])
        repost = {"parent_event_id": post["event_id"]}
        bruno = call("POST", "/api/reposts", "bruno", repost, "swagger-repost")
        call("POST", "/api/reposts", "bruno", repost, "swagger-repost")
        call(
            "POST", "/api/reposts", "carla", {"parent_event_id": bruno["event_id"]}, "swagger-carla"
        )
        publication = "/api/publications/" + post["publication_id"]
        call("GET", publication, route="/api/publications/{publication_id}")
        call(
            "POST",
            publication + "/comments",
            "bruno",
            {"body": "Una explicación verificable."},
            "swagger-comment",
            route="/api/publications/{publication_id}/comments",
        )
        call(
            "POST",
            publication + "/comments",
            "bruno",
            {"body": "Una explicación verificable."},
            "swagger-comment",
            route="/api/publications/{publication_id}/comments",
        )
        call("GET", publication + "/comments", route="/api/publications/{publication_id}/comments")
        feed = call("POST", "/api/feed/snapshots", "diego", {"strategy": "chronological"})
        call("POST", "/api/feed/comparisons", "diego")
        snapshot = "/api/feed/" + feed["snapshot_id"]
        call("GET", snapshot, "diego", route="/api/feed/{snapshot_id}")
        result = call(
            "GET",
            snapshot + "/cards/" + post["publication_id"] + "/provenance",
            "diego",
            route="/api/feed/{snapshot_id}/cards/{publication_id}/provenance",
        )
        self.assertEqual(result["tree"]["event_count"], 3)
        call("DELETE", "/api/me/contacts/bruno", "diego", route="/api/me/contacts/{other}")
        retired = call("DELETE", publication, route="/api/publications/{publication_id}")
        self.assertNotIn("body", retired)
        # Reading old snapshots keeps reasons and omits the retired original body.
        saved = call("GET", snapshot, "diego", route="/api/feed/{snapshot_id}")
        self.assertNotIn("body", saved["cards"][0]["publication"])
        self.assertEqual(len(observed), 21)

    def test_error_schema_matches_real_auth_and_validation_responses(self):
        external = self.client.get(
            "/api/me", headers={"X-Demo-User": "ana", "Origin": "https://evil.example"}
        )
        self.assertEqual(external.status_code, 403)
        self.assertEqual(ErrorResponse.model_validate(external.json()).error.code, "local_origin")
        for response in (
            self.client.get("/api/me"),
            self.client.put(
                "/api/me/preferences",
                headers={"X-Demo-User": "ana"},
                json={"topic_ids": [], "version": True},
            ),
        ):
            self.assertIn(response.status_code, (400, 401))
            error = ErrorResponse.model_validate(response.json())
            self.assertTrue(error.error.code)
        schema = self.app.openapi()

        def refs(value):
            if isinstance(value, dict):
                if "$ref" in value:
                    yield value["$ref"]
                for child in value.values():
                    yield from refs(child)
            elif isinstance(value, list):
                for child in value:
                    yield from refs(child)

        for ref in refs(schema):
            self.assertIn(ref.split("/")[-1], schema["components"]["schemas"])
