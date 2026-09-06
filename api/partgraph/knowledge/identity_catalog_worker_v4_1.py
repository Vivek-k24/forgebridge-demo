from __future__ import annotations

from . import identity_catalog_worker as legacy
from . import identity_catalog_worker_v3 as v3
from . import identity_catalog_worker_v4 as v4

# Patch V4's body-prefix splitter so aliases whose display name has a different
# word count from the source spelling ("Sport Utility" -> "SUV") remove the
# correct number of source words. All other V4 behavior remains unchanged.


def _split_body_prefix(label: str) -> tuple[str | None, str]:
    key = legacy.normalized_key(label)
    for body_key, body in sorted(
        v4._BODY_PREFIX_KEYS_V4.items(),
        key=lambda item: len(item[0]),
        reverse=True,
    ):
        if key == body_key:
            return body, ""
        prefix = f"{body_key} "
        if key.startswith(prefix):
            words = label.split()
            source_words = len(body_key.split())
            return body, " ".join(words[source_words:]).strip()
    return None, label


def install_v4_1_behavior() -> None:
    v4.install_v4_behavior()
    v3._split_body_prefix = _split_body_prefix

    # V4/V3 functions resolve the splitter dynamically from the V3 module.
    legacy.collect_make_year = v3._collect_make_year
    legacy.export_json = v4.export_json


def main() -> None:
    install_v4_1_behavior()
    legacy.main()


if __name__ == "__main__":
    main()
