"""API smoke tests for case party endpoints.

Verifies the _get_case_party_service() factory properly injects
client_service and contract_service dependencies.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from django.test import Client

from apps.testing.factories import CaseFactory, ClientFactory, LawyerFactory


def create_authenticated_client(user: Any) -> Client:
    client = Client()
    client.force_login(user)
    return client


def _post_json(client: Client, path: str, data: dict[str, Any]) -> Any:
    return client.post(
        path,
        data=json.dumps(data),
        content_type="application/json",
        HTTP_HOST="localhost",
    )


@pytest.fixture
def admin_user() -> Any:
    return LawyerFactory(is_admin=True, is_staff=True, is_superuser=True)


@pytest.fixture
def api_client(admin_user: Any) -> Client:
    return create_authenticated_client(admin_user)


@pytest.fixture
def case_no_contract() -> Any:
    """Case without contract binding — avoids PARTY_NOT_IN_CONTRACT_SCOPE."""
    from apps.cases.models import Case
    from apps.core.models.enums import SimpleCaseType

    return Case.objects.create(
        name="test-case-no-contract",
        case_type=SimpleCaseType.CIVIL,
        contract=None,
    )


@pytest.fixture
def party_client() -> Any:
    return ClientFactory(is_our_client=True)


@pytest.mark.django_db
class TestCasePartyFactoryInjection:
    """Verify the factory function injects dependencies correctly."""

    def test_factory_returns_service_with_dependencies(self) -> None:
        from apps.cases.api.caseparty_api import _get_case_party_service

        service = _get_case_party_service()
        assert service._client_service is not None, "client_service should be injected"
        assert service._contract_service is not None, "contract_service should be injected"

    def test_mutation_facade_accessible(self) -> None:
        from apps.cases.api.caseparty_api import _get_case_party_service

        service = _get_case_party_service()
        # Should NOT raise RuntimeError("CasePartyService.client_service 未注入")
        facade = service.mutation_facade
        assert facade is not None


@pytest.mark.django_db
class TestCasePartyCreateApi:
    """API-level smoke test for POST /api/v1/cases/parties."""

    def test_create_party_returns_200(
        self, api_client: Client, case_no_contract: Any, party_client: Any
    ) -> None:
        response = _post_json(
            api_client,
            "/api/v1/cases/parties",
            {
                "case_id": case_no_contract.id,
                "client_id": party_client.id,
                "legal_status": "plaintiff",
            },
        )
        assert response.status_code == 200, (
            f"Expected 200, got {response.status_code}: "
            f"{response.content.decode('utf-8', errors='ignore')}"
        )
        body = response.json()
        assert body["client"] == party_client.id
        assert body["case"] == case_no_contract.id

    def test_create_party_without_legal_status(
        self, api_client: Client, case_no_contract: Any, party_client: Any
    ) -> None:
        response = _post_json(
            api_client,
            "/api/v1/cases/parties",
            {
                "case_id": case_no_contract.id,
                "client_id": party_client.id,
            },
        )
        assert response.status_code == 200

    def test_create_party_invalid_case_returns_error(
        self, api_client: Client, party_client: Any
    ) -> None:
        response = _post_json(
            api_client,
            "/api/v1/cases/parties",
            {
                "case_id": 999999,
                "client_id": party_client.id,
            },
        )
        assert response.status_code in (400, 404)
