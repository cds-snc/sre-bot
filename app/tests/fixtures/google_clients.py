from typing import Any, Callable, Dict, List, Optional


class FakeGoogleService:
    """
    Simulates a Google API service resource for testing.
    Supports method stubbing and paginated responses.
    """

    def __init__(
        self,
        api_responses: Optional[Dict[str, Any]] = None,
        paginated_pages: Optional[List[Dict[str, Any]]] = None,
    ):
        self.api_responses = api_responses or {}
        self.paginated_pages = paginated_pages or []

    def __getattr__(self, name: str) -> Callable:
        def method(*args, **kwargs):
            if name in self.api_responses:
                resp = self.api_responses[name]
                if callable(resp):
                    return resp(*args, **kwargs)
                return resp
            raise AttributeError(f"No stubbed response for method: {name}")

        return method

    def list(self):
        # Simulate paginated list responses
        for page in self.paginated_pages:
            yield page


# Example usage in tests:
# service = FakeGoogleService(api_responses={"get_user": {"id": "u-1"}}, paginated_pages=[{"users": [{"id": "u-1"}]}])
# result = service.get_user()
# for page in service.list():
#     ...
