import base64
import pickle
import pytest
from pickle import UnpicklingError
from unittest.mock import patch, MagicMock
from integrations.google_workspace.google_service import get_google_service


@patch("integrations.google_workspace.google_service.pickle")
@patch("integrations.google_workspace.google_service.build")
def test_get_google_service_returns_build_object(build_mock, pickle_mock):
    """
    Test case to verify that the function returns a build object.
    """
    pickle_mock.loads.return_value = MagicMock()
    get_google_service("drive", "v3")
    build_mock.assert_called_once_with(
        "drive", "v3", credentials=pickle_mock.loads.return_value
    )


@patch("integrations.google_workspace.google_service.PICKLE_STRING", False)
def test_get_google_service_raises_exception_if_pickle_string_not_set():
    """
    Test case to verify that the function raises an exception if:
     - PICKLE_STRING is not set.
    """
    with pytest.raises(ValueError) as e:
        get_google_service("drive", "v3")
    assert "Pickle string not set" in str(e.value)



# from pickle import UnpicklingError
@patch("integrations.google_workspace.google_service.build")
@patch("integrations.google_workspace.google_service.pickle")
@patch(
    "integrations.google_workspace.google_service.PICKLE_STRING",
    base64.b64encode(pickle.dumps("invalid")).decode(),
)
def test_get_google_service_raises_exception_if_pickle_string_is_invalid(pickle_mock, build_mock):
    """
    Test case to verify that the function raises an exception if:
     - PICKLE_STRING is invalid.
    """
    pickle_mock.loads.side_effect = UnpicklingError("Invalid pickle string")

    # Call the method under test that uses pickle.loads
    with pytest.raises(UnpicklingError) as e:
        get_google_service("drive", "v3")
    assert "Invalid pickle string" in str(e.value)
