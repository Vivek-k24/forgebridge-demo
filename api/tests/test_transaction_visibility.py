from fastapi.params import Depends as DependsParam

from partgraph.auth.dependencies import AuthSessionDep


def test_authenticated_transaction_dependency_finishes_before_response() -> None:
    """Prevent read-after-write races across consecutive authenticated HTTP requests."""

    dependency = next(
        item for item in AuthSessionDep.__metadata__ if isinstance(item, DependsParam)
    )
    assert dependency.scope == "function"
