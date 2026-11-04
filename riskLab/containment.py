"""Latch a local service breaker and retain minimal incident and handoff records."""
import json
from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4


class CircuitBreaker:
    """Stop generation across sessions sharing this sequential service instance.

    Attributes:
        path: Optional private state file used to survive process restarts.
        state: Latched status, one incident record and pending human handoffs.
    """

    def __init__(self, directory=None):
        """Load existing state or initialise an available service.

        Args:
            directory: Dedicated state directory, or None for an in-memory trial.

        Raises:
            ValueError: If saved state cannot safely be interpreted.
            OSError: If the state directory cannot be accessed.
        """
        self.path = Path(directory) / "control.json" if directory is not None else None
        self.state = {"open": False, "incident": None, "handoffs": []}
        if self.path is not None:
            # State belongs to one process owner; this is not a multi-user access system.
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if self.path.exists():
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                incident = saved.get("incident") if isinstance(saved, dict) else None
                if (not isinstance(saved, dict) or type(saved.get("open")) is not bool
                        or not isinstance(saved.get("handoffs"), list)
                        or (saved["open"] and (not isinstance(incident, dict)
                            or not isinstance(incident.get("id"), str)
                            or not isinstance(incident.get("signals"), list)
                            or incident.get("status") != "open"))
                        or (not saved["open"] and (incident is not None or saved["handoffs"]))):
                    raise ValueError("Invalid circuit state; investigate before starting the service")
                self.state = saved

    @property
    def is_open(self):
        """Return whether generation is disabled.

        Returns:
            True after any trip, including a trip restored from disk.
        """
        return self.state["open"]

    def trip(self, rule, observation):
        """Latch the breaker and record a new signal without repeating old signals.

        Args:
            rule: Internal rule name, never a model-supplied instruction.
            observation: Aggregate evidence without prompts or customer records.
        """
        now = datetime.now(timezone.utc).isoformat()
        # No timer or customer message can reopen an incident automatically.
        self.state["open"] = True
        if self.state["incident"] is None:
            self.state["incident"] = {"id": uuid4().hex, "openedAtUtc": now,
                                      "status": "open", "signals": []}
        signals = self.state["incident"]["signals"]
        signal = {"rule": rule, "observation": deepcopy(observation)}
        if not any(s["rule"] == rule and s["observation"] == observation for s in signals):
            signals.append({**signal, "detectedAtUtc": now})
            self._save()

    def apply_telemetry(self, snapshot):
        """Act immediately on definite alerts from the trusted A2 monitor.

        Args:
            snapshot: Monitor snapshot, including sample-qualified alert flags.
        """
        for window in snapshot["windows"]:
            # Null alerts represent missing evidence and must never count as breaches.
            for flag, rule, fields in (
                ("privacyAlert", "delivered_disclosure", ("disclosedReplies", "replies")),
                ("factualAlert", "factual_contradictions", ("contradictions", "factualScored", "contradictionRate")),
                ("tokenDriftAlert", "token_drift", ("tokenSamples", "tokenMedianRatio")),
            ):
                if window.get(flag) is True:
                    observation = {key: window[key] for key in ("windowStartUtc", "target", "task", *fields)}
                    self.trip(rule, observation)

    def enqueue(self, request):
        """Record a pending handoff without copying private conversation text.

        Args:
            request: Trusted session metadata from the application.

        Returns:
            Incident and handoff references for the restricted evidence record.

        Raises:
            ValueError: If there is no active incident.
        """
        if not self.is_open:
            raise ValueError("A handoff requires an active incident")
        # A session reference links back to restricted evidence, not to another customer's data.
        session = str(request.get("sessionId", ""))
        entry = {"id": uuid4().hex, "incidentId": self.state["incident"]["id"],
                 "createdAtUtc": datetime.now(timezone.utc).isoformat(), "status": "pending",
                 "sessionRef": sha256(session.encode()).hexdigest() if session else None}
        self.state["handoffs"].append(entry)
        self._save()
        return {"incidentId": entry["incidentId"], "handoffId": entry["id"]}

    def snapshot(self):
        """Return an independent copy of the incident and queue state.

        Returns:
            JSON-serialisable state without raw customer conversation content.
        """
        return deepcopy(self.state)

    def _save(self):
        """Atomically replace the private state file when persistence is enabled.

        Raises:
            OSError: If incident state cannot be saved.
        """
        if self.path is None:
            return
        # Temporary files are owner-only; replacement avoids a partially written JSON file.
        with NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False, encoding="utf-8") as stream:
            stream.write(json.dumps(self.state, indent=2) + "\n")
        Path(stream.name).replace(self.path)
