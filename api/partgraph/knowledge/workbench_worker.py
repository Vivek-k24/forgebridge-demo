"""Compatibility entry point for the PartGraph local catalog worker.

The active implementation is workbench_worker_v2. Keeping this module as a
thin forwarder prevents old local commands or references from accidentally
running the retired whole-configuration matcher.
"""

from .workbench_worker_v2 import main


if __name__ == "__main__":
    main()
