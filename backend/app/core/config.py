"""Runtime configuration.

Everything here has a safe default because the defaults are what a reviewer will run. The point
of the file is that the unsafe switches are explicit, greppable, and off.

Design rules encoded here:
  * no credential is read at import time, and none is required to run the system;
  * the LLM boundary is closed by default (``ENABLE_LLM`` is False) so that a run is
    reproducible and a reviewer is never shown model output as if it were policy;
  * the database path, source cache and repository root are single-sourced, so no module
    re-derives a path and drifts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def _flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    repo_root: Path = REPO_ROOT
    backend_root: Path = REPO_ROOT / "backend"
    kb_dir: Path = REPO_ROOT / "knowledge_base"
    scenario_dir: Path = REPO_ROOT / "evaluation" / "scenarios"
    expected_dir: Path = REPO_ROOT / "evaluation" / "expected_actions"
    results_dir: Path = REPO_ROOT / "evaluation" / "results"
    report_path: Path = REPO_ROOT / "evaluation" / "report.md"
    db_path: Path = Path(os.environ.get("RESULTRELAY_DB", REPO_ROOT / "backend" / "resultrelay.db"))
    source_cache: Path = Path(
        os.environ.get("RESULTRELAY_SOURCE_CACHE", Path.home() / ".cache" / "resultrelay" / "sources")
    )

    #: No outbound network call is made by the running application. The simulated transport is
    #: the only "network" the workflow can talk to.
    allow_outbound_network: bool = _flag("RESULTRELAY_ALLOW_NETWORK", False)
    #: The deterministic agent set is the shipped behaviour. Enabling an adviser would make the
    #: system non-reproducible and would put model text next to policy text; it is off.
    #: ``RESULTRELAY_ADVISE`` is the documented switch; ``RESULTRELAY_ENABLE_LLM`` is kept as an
    #: alias because older docs and the guard message name it. Two independent switches let
    #: /api/health report "closed" while the engine produced advisories, which is a lie either way.
    enable_llm: bool = _flag("RESULTRELAY_ADVISE", False) or _flag("RESULTRELAY_ENABLE_LLM", False)
    #: Demo mode trims the UI to the walkthrough path. It changes presentation, never gating.
    demo_mode: bool = _flag("RESULTRELAY_DEMO", False)
    #: Refuse to start if the knowledge base failed verification on the most recent build.
    require_verified_kb: bool = _flag("RESULTRELAY_REQUIRE_VERIFIED_KB", True)

    #: Comma-separated list of allowed browser origins. Empty by default: the UI is same-origin, and
    #: a wildcard would expose every case to any page the operator visits.
    cors_origins: str = os.environ.get("RESULTRELAY_CORS_ORIGINS", "")
    #: Bind address for the development server. Loopback unless explicitly widened; exposing the
    #: unauthenticated API on a routable interface is a deployment decision, not a default.
    host: str = os.environ.get("RESULTRELAY_HOST", "127.0.0.1")
    #: Declared, not enforced: this build has no authentication and must not be hosted with real data.
    authentication_enabled: bool = False

    synthetic_data_only: bool = True
    disclaimer: str = (
        "Demonstration prototype using synthetic data. Not a clinical service, not a medical "
        "device, and not evidence of clinical safety, effectiveness or regulatory compliance."
    )
    extra: dict[str, str] = field(default_factory=dict)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()


def describe() -> dict[str, object]:
    """A redacted view for /api/health and the audit bundle."""
    return {
        "synthetic_data_only": settings.synthetic_data_only,
        "allow_outbound_network": settings.allow_outbound_network,
        "enable_llm": settings.enable_llm,
        "demo_mode": settings.demo_mode,
        "require_verified_kb": settings.require_verified_kb,
        "authentication_enabled": settings.authentication_enabled,
        "cors_origins": settings.cors_origins or "(same-origin only)",
        "db_path": str(settings.db_path),
        "kb_dir": str(settings.kb_dir),
        "source_cache_present": settings.source_cache.exists(),
        "disclaimer": settings.disclaimer,
    }
