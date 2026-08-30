from partgraph.auth import models as legacy_auth_models
from partgraph.auth import service as legacy_auth_service
from partgraph.identity import actors
from partgraph.identity.auth import dependencies as identity_auth_dependencies
from partgraph.identity.auth import models as identity_auth_models
from partgraph.identity.auth import service as identity_auth_service
from partgraph.identity.user_vehicle import models as identity_user_vehicle_models
from partgraph.identity.user_vehicle import service as identity_user_vehicle_service
from partgraph.identity.vehicle import models as identity_vehicle_models
from partgraph.identity.vehicle import service as identity_vehicle_service
from partgraph.user_vehicle import models as legacy_user_vehicle_models
from partgraph.user_vehicle import service as legacy_user_vehicle_service
from partgraph.vehicle import models as legacy_vehicle_models
from partgraph.vehicle import service as legacy_vehicle_service


def test_legacy_identity_paths_resolve_to_identity_owned_orm_classes() -> None:
    assert legacy_auth_models.User is identity_auth_models.User
    assert legacy_auth_models.AuthSession is identity_auth_models.AuthSession
    assert legacy_vehicle_models.VehicleConfiguration is identity_vehicle_models.VehicleConfiguration
    assert legacy_user_vehicle_models.UserVehicle is identity_user_vehicle_models.UserVehicle
    assert legacy_user_vehicle_models.VinDecodeCache is identity_user_vehicle_models.VinDecodeCache

    assert identity_auth_models.User.__module__ == "partgraph.identity.auth.models"
    assert identity_vehicle_models.VehicleConfiguration.__module__ == "partgraph.identity.vehicle.models"
    assert identity_user_vehicle_models.UserVehicle.__module__ == "partgraph.identity.user_vehicle.models"


def test_legacy_identity_paths_do_not_duplicate_sqlalchemy_tables() -> None:
    assert legacy_auth_models.User.__table__ is identity_auth_models.User.__table__
    assert legacy_auth_models.AuthSession.__table__ is identity_auth_models.AuthSession.__table__
    assert (
        legacy_vehicle_models.VehicleConfiguration.__table__
        is identity_vehicle_models.VehicleConfiguration.__table__
    )
    assert legacy_user_vehicle_models.UserVehicle.__table__ is identity_user_vehicle_models.UserVehicle.__table__
    assert (
        legacy_user_vehicle_models.VinDecodeCache.__table__
        is identity_user_vehicle_models.VinDecodeCache.__table__
    )


def test_legacy_identity_services_resolve_to_identity_implementations() -> None:
    assert legacy_auth_service.normalize_email is identity_auth_service.normalize_email
    assert legacy_vehicle_service.resolve_selection is identity_vehicle_service.resolve_selection
    assert (
        legacy_user_vehicle_service.serialize_user_vehicle
        is identity_user_vehicle_service.serialize_user_vehicle
    )


def test_actor_seam_is_current_authenticated_owner_boundary() -> None:
    assert actors.AuthSessionDep is identity_auth_dependencies.AuthSessionDep
    assert actors.CurrentUserDep is identity_auth_dependencies.CurrentUserDep
    assert actors.require_csrf is identity_auth_dependencies.require_csrf
