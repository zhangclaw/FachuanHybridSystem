"""Unit tests for client duplicate check functionality."""

from __future__ import annotations

import pytest

from apps.client.models import Client
from apps.client.services.client_query_facade import ClientQueryFacade


@pytest.mark.django_db
class TestCheckDuplicateByName:
    def test_no_match_returns_empty(self):
        facade = ClientQueryFacade()
        result = facade.check_duplicate_by_name("不存在的人")
        assert result == []

    def test_exact_match_returns_candidate(self):
        Client.objects.create(
            name="周利明",
            client_type=Client.NATURAL,
            id_number="362322197812248133",
            address="江西省上饶市广丰县",
            phone="13800001111",
        )
        facade = ClientQueryFacade()
        result = facade.check_duplicate_by_name("周利明")
        assert len(result) == 1
        assert result[0]["name"] == "周利明"
        assert result[0]["client_type"] == "natural"
        assert result[0]["id_number"] == "362322197812248133"
        assert result[0]["address"] == "江西省上饶市广丰县"
        assert result[0]["phone"] == "13800001111"

    def test_partial_name_no_match(self):
        """部分匹配不应返回结果（必须精确匹配）"""
        Client.objects.create(name="周利明", client_type=Client.NATURAL)
        facade = ClientQueryFacade()
        result = facade.check_duplicate_by_name("周利")
        assert result == []

    def test_multiple_exact_matches(self):
        Client.objects.create(name="张三", client_type=Client.NATURAL)
        Client.objects.create(name="张三", client_type=Client.NATURAL)
        facade = ClientQueryFacade()
        result = facade.check_duplicate_by_name("张三")
        assert len(result) == 2

    def test_returns_max_10(self):
        for _ in range(15):
            Client.objects.create(name="重复名", client_type=Client.NATURAL)
        facade = ClientQueryFacade()
        result = facade.check_duplicate_by_name("重复名")
        assert len(result) == 10

    def test_legal_entity_candidate(self):
        Client.objects.create(
            name="江西盛业建设工程有限公司",
            client_type=Client.LEGAL,
            id_number="913611220653568177",
            legal_representative="周利杰",
        )
        facade = ClientQueryFacade()
        result = facade.check_duplicate_by_name("江西盛业建设工程有限公司")
        assert len(result) == 1
        assert result[0]["client_type"] == "legal"
        assert result[0]["legal_representative"] == "周利杰"

    def test_null_fields_serialized_as_none(self):
        Client.objects.create(name="李四", client_type=Client.NATURAL)
        facade = ClientQueryFacade()
        result = facade.check_duplicate_by_name("李四")
        assert len(result) == 1
        assert result[0]["id_number"] is None
        assert result[0]["phone"] is None
        assert result[0]["address"] == ""
        assert result[0]["legal_representative"] is None
