from __future__ import annotations

from . import identity_catalog_worker as legacy
from . import identity_catalog_worker_v4 as v4
from . import identity_catalog_worker_v4_1 as v4_1

# V4.2 keeps V4.1's persisted-key/body-prefix fixes and activates the exact-year
# hybrid alias and trim/configuration reconciliation implemented in V4.


def install_v4_2_behavior() -> None:
    v4_1.install_v4_1_behavior()
    legacy.export_json = v4.export_json


def main() -> None:
    install_v4_2_behavior()
    legacy.main()


if __name__ == "__main__":
    main()
