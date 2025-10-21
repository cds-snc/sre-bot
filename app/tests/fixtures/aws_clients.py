from typing import Any, Iterable, List


class FakePaginator:
    def __init__(self, pages: Iterable[dict]):
        self._pages = list(pages)

    def paginate(self, **kwargs):
        for p in self._pages:
            yield p


class FakeClient:
    def __init__(
        self,
        paginated_pages: List[dict] | None = None,
        api_responses: dict | None = None,
        can_paginate: Any = None,
    ):
        self._paginated_pages = paginated_pages or []
        self._api_responses = api_responses or {}
        # If caller didn't specify can_paginate, infer from presence of pages
        if can_paginate is None:
            self._can_paginate = bool(self._paginated_pages)
        else:
            self._can_paginate = can_paginate

    def get_paginator(self, *args, **kwargs):
        # Return a paginator that yields provided pages; if none provided,
        # mimic boto3 by raising AttributeError
        if not self._paginated_pages:
            raise AttributeError("No paginator available")
        return FakePaginator(self._paginated_pages)

    def __getattr__(self, name: str):
        # Provide a callable for API methods that returns configured responses
        if name in self._api_responses:
            resp = self._api_responses[name]

            if callable(resp):

                def _call(*_args: Any, **_kwargs: Any):
                    return resp(**_kwargs)

                return _call

            def _call_const(*_args: Any, **_kwargs: Any):
                return resp

            return _call_const

        # If we have paginated pages configured, some code paths construct
        # the api_method via getattr before checking pagination. Return a
        # harmless callable that returns an empty dict so those code paths
        # don't raise AttributeError during tests.
        if self._paginated_pages:

            def _noop(*_args: Any, **_kwargs: Any):
                return {}

            return _noop

        raise AttributeError(name)

    def can_paginate(self, method_name: str) -> bool:
        # Indicate whether paginator is available; honor configured flag
        if callable(self._can_paginate):
            try:
                return bool(self._can_paginate(method_name))
            except Exception:
                return False
        return bool(self._can_paginate)
