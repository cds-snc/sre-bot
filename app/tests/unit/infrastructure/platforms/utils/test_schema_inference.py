"""Tests for schema-driven argument inference."""

import pytest
from pydantic import BaseModel, Field
from typing import List

from infrastructure.platforms.parsing import ArgumentType
from infrastructure.platforms.utils.schema_inference import (
    infer_arguments_from_schema,
    _infer_argument_type,
)


class SimpleModel(BaseModel):
    """Simple test schema."""

    email: str
    name: str


class ModelWithDefaults(BaseModel):
    """Schema with default values."""

    email: str
    role: str = "MEMBER"
    active: bool = True


class ModelWithDescriptions(BaseModel):
    """Schema with field descriptions."""

    email: str = Field(description="User email address")
    group_id: str = Field(description="Group identifier")


class ModelWithTypes(BaseModel):
    """Schema with various types."""

    email: str
    count: int
    enabled: bool


class ModelWithLists(BaseModel):
    """Schema with list types."""

    tags: List[str]
    emails: List[str]


class TestInferArgumentsFromSchema:
    """Test inferring arguments from Pydantic schemas."""

    def test_infer_simple_schema(self):
        """Test inferring arguments from simple schema."""
        args = infer_arguments_from_schema(SimpleModel)

        assert len(args) == 2
        assert args[0].name == "email"
        assert args[0].type == ArgumentType.STRING
        assert args[0].required is True

        assert args[1].name == "name"
        assert args[1].type == ArgumentType.STRING
        assert args[1].required is True

    def test_infer_with_defaults(self):
        """Test inferring arguments with default values."""
        args = infer_arguments_from_schema(ModelWithDefaults)

        assert len(args) == 3

        # email is required
        email_arg = next(a for a in args if a.name == "email")
        assert email_arg.required is True
        assert email_arg.default is None

        # role has default
        role_arg = next(a for a in args if a.name == "role")
        assert role_arg.required is False
        assert role_arg.default == "MEMBER"

        # active has default
        active_arg = next(a for a in args if a.name == "active")
        assert active_arg.required is False
        assert active_arg.default is True

    def test_infer_with_descriptions(self):
        """Test inferring arguments preserves descriptions."""
        args = infer_arguments_from_schema(ModelWithDescriptions)

        email_arg = next(a for a in args if a.name == "email")
        assert email_arg.description == "User email address"

        group_arg = next(a for a in args if a.name == "group_id")
        assert group_arg.description == "Group identifier"

    def test_infer_various_types(self):
        """Test inferring different Python types."""
        args = infer_arguments_from_schema(ModelWithTypes)

        # String type
        email_arg = next(a for a in args if a.name == "email")
        assert email_arg.type == ArgumentType.STRING

        # Integer type
        count_arg = next(a for a in args if a.name == "count")
        assert count_arg.type == ArgumentType.INTEGER

        # Boolean type
        enabled_arg = next(a for a in args if a.name == "enabled")
        assert enabled_arg.type == ArgumentType.BOOLEAN

    def test_infer_list_types(self):
        """Test inferring List types as CSV."""
        args = infer_arguments_from_schema(ModelWithLists)

        tags_arg = next(a for a in args if a.name == "tags")
        assert tags_arg.type == ArgumentType.CSV

        emails_arg = next(a for a in args if a.name == "emails")
        assert emails_arg.type == ArgumentType.CSV

    def test_infer_non_basemodel_raises_error(self):
        """Test error when non-BaseModel passed."""

        class NotAModel:
            pass

        with pytest.raises(TypeError):
            infer_arguments_from_schema(NotAModel)

    def test_infer_preserves_field_order(self):
        """Test that inferred arguments preserve field definition order."""

        class OrderedModel(BaseModel):
            first: str
            second: str
            third: str

        args = infer_arguments_from_schema(OrderedModel)

        assert [a.name for a in args] == ["first", "second", "third"]


class TestInferArgumentType:
    """Test type inference for individual fields."""

    def test_infer_string_type(self):
        """Test str type inference."""
        assert _infer_argument_type(str) == ArgumentType.STRING

    def test_infer_integer_type(self):
        """Test int type inference."""
        assert _infer_argument_type(int) == ArgumentType.INTEGER

    def test_infer_boolean_type(self):
        """Test bool type inference."""
        assert _infer_argument_type(bool) == ArgumentType.BOOLEAN

    def test_infer_list_string_type(self):
        """Test List[str] inference as CSV."""
        assert _infer_argument_type(List[str]) == ArgumentType.CSV

    def test_infer_optional_string_type(self):
        """Test Optional[str] inference."""
        from typing import Optional

        assert _infer_argument_type(Optional[str]) == ArgumentType.STRING

    def test_infer_optional_int_type(self):
        """Test Optional[int] inference."""
        from typing import Optional

        assert _infer_argument_type(Optional[int]) == ArgumentType.INTEGER


class TestRealWorldSchemas:
    """Tests with real-world-like schemas."""

    def test_add_group_member_schema(self):
        """Test schema for adding member to group."""

        class AddGroupMemberRequest(BaseModel):
            email: str = Field(description="Member email address")
            group_id: str = Field(description="Target group ID")
            role: str = Field(default="MEMBER", description="Member role")
            justification: str = Field(description="Reason for access")

        args = infer_arguments_from_schema(AddGroupMemberRequest)

        assert len(args) == 4

        # All should be strings
        for arg in args:
            assert arg.type == ArgumentType.STRING

        # email and group_id required
        assert next(a for a in args if a.name == "email").required is True
        assert next(a for a in args if a.name == "group_id").required is True

        # role has default
        assert next(a for a in args if a.name == "role").default == "MEMBER"

    def test_filter_groups_schema(self):
        """Test schema for filtering groups."""

        class FilterGroupsRequest(BaseModel):
            member_role: List[str] = Field(
                default=["MEMBER"], description="Filter by member roles"
            )
            provider: str = Field(default="aws", description="Cloud provider")
            include_details: bool = Field(default=True)

        args = infer_arguments_from_schema(FilterGroupsRequest)

        # member_role should be CSV
        role_arg = next(a for a in args if a.name == "member_role")
        assert role_arg.type == ArgumentType.CSV

        # provider should be string
        provider_arg = next(a for a in args if a.name == "provider")
        assert provider_arg.type == ArgumentType.STRING

        # include_details should be boolean
        details_arg = next(a for a in args if a.name == "include_details")
        assert details_arg.type == ArgumentType.BOOLEAN
