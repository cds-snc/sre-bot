"""Unit tests for base infrastructure models."""

import pytest

from infrastructure.models import InfrastructureModel


@pytest.mark.unit
class TestInfrastructureModel:
    """Test suite for InfrastructureModel base configuration."""

    def test_infrastructure_model_creation(self):
        """Test InfrastructureModel can be created as a subclass."""

        class TestModel(InfrastructureModel):
            """Test model using InfrastructureModel base."""

            name: str
            value: int

        model = TestModel(name="test", value=42)

        assert model.name == "test"
        assert model.value == 42

    def test_infrastructure_model_populate_by_name(self):
        """Test InfrastructureModel accepts both field name and alias."""

        class TestModel(InfrastructureModel):
            """Test model with aliased fields."""

            user_name: str

        model = TestModel(user_name="john")
        assert model.user_name == "john"

    def test_infrastructure_model_validate_assignment(self):
        """Test InfrastructureModel validates on field assignment."""

        class TestModel(InfrastructureModel):
            """Test model with int field."""

            count: int

        model = TestModel(count=10)

        # Assignment should validate
        model.count = 20
        assert model.count == 20

        # Invalid assignment should raise
        with pytest.raises(Exception):  # Pydantic validation error
            model.count = "not an int"  # type: ignore

    def test_infrastructure_model_str_strip_whitespace(self):
        """Test InfrastructureModel strips whitespace from strings."""

        class TestModel(InfrastructureModel):
            """Test model with string field."""

            text: str

        model = TestModel(text="  hello world  ")

        # Whitespace should be stripped
        assert model.text == "hello world"

    def test_infrastructure_model_serialization(self):
        """Test InfrastructureModel serializes correctly."""

        class TestModel(InfrastructureModel):
            """Test model."""

            name: str
            active: bool

        model = TestModel(name="test", active=True)
        dumped = model.model_dump()

        assert dumped["name"] == "test"
        assert dumped["active"] is True

    def test_infrastructure_model_from_attributes(self):
        """Test InfrastructureModel can be created from objects with attributes."""

        class DataObject:
            """Simple object with attributes."""

            def __init__(self):
                self.name = "test"
                self.value = 42

        class TestModel(InfrastructureModel):
            """Test model."""

            name: str
            value: int

        obj = DataObject()
        model = TestModel.model_validate(obj)

        assert model.name == "test"
        assert model.value == 42

    def test_infrastructure_model_enum_values_preserved(self):
        """Test InfrastructureModel preserves enums as objects."""
        from enum import Enum

        class Status(str, Enum):
            """Test enum."""

            ACTIVE = "active"
            INACTIVE = "inactive"

        class TestModel(InfrastructureModel):
            """Test model with enum field."""

            status: Status

        model = TestModel(status=Status.ACTIVE)

        # Enum should be preserved as enum object, not string value
        assert model.status == Status.ACTIVE
        assert isinstance(model.status, Status)

    def test_infrastructure_model_validation_error(self):
        """Test InfrastructureModel raises validation errors."""
        from pydantic import ValidationError

        class TestModel(InfrastructureModel):
            """Test model with type constraints."""

            count: int
            name: str

        with pytest.raises(ValidationError):
            TestModel(count="not_int", name="test")  # type: ignore

    def test_infrastructure_model_optional_fields(self):
        """Test InfrastructureModel handles optional fields."""
        from typing import Optional

        class TestModel(InfrastructureModel):
            """Test model with optional field."""

            name: str
            description: Optional[str] = None

        model = TestModel(name="test")

        assert model.name == "test"
        assert model.description is None

    def test_infrastructure_model_default_values(self):
        """Test InfrastructureModel supports default values."""

        class TestModel(InfrastructureModel):
            """Test model with defaults."""

            name: str
            status: str = "active"
            count: int = 0

        model = TestModel(name="test")

        assert model.name == "test"
        assert model.status == "active"
        assert model.count == 0

    def test_infrastructure_model_nested_models(self):
        """Test InfrastructureModel supports nested models."""

        class Address(InfrastructureModel):
            """Nested address model."""

            street: str
            city: str

        class Person(InfrastructureModel):
            """Person model with nested address."""

            name: str
            address: Address

        person = Person(
            name="John",
            address=Address(street="123 Main St", city="Springfield"),
        )

        assert person.name == "John"
        assert person.address.city == "Springfield"

    def test_infrastructure_model_json_schema(self):
        """Test InfrastructureModel generates JSON schema."""

        class TestModel(InfrastructureModel):
            """Test model."""

            name: str
            age: int

        schema = TestModel.model_json_schema()

        assert "properties" in schema
        assert "name" in schema["properties"]
        assert "age" in schema["properties"]

    def test_infrastructure_model_copy(self):
        """Test InfrastructureModel supports model_copy()."""

        class TestModel(InfrastructureModel):
            """Test model."""

            name: str
            value: int

        original = TestModel(name="test", value=42)
        copy = original.model_copy()

        assert copy.name == original.name
        assert copy.value == original.value
        # Should be different instances
        assert copy is not original

    def test_infrastructure_model_copy_update(self):
        """Test InfrastructureModel supports model_copy with updates."""

        class TestModel(InfrastructureModel):
            """Test model."""

            name: str
            value: int

        original = TestModel(name="test", value=42)
        updated = original.model_copy(update={"value": 100})

        assert updated.name == "test"
        assert updated.value == 100
        assert original.value == 42  # Original unchanged
