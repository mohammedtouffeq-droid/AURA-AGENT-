"""Compatibility entry point for Aura's honest submodule registry audit."""
from engine_auditor import (
    EngineSpec,
    EngineStatus,
    audit_engines,
    load_engine_specs,
    main,
    parse_submodule_status,
)


if __name__ == "__main__":
    raise SystemExit(main())
