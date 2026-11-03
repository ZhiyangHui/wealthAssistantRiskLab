"""Read-only simulated bank tools. The runner binds identity at session creation."""
import json
from copy import deepcopy
from pathlib import Path

DATA = json.loads(Path(__file__).with_name("fixtures.json").read_text(encoding="utf-8"))


class BankSession:
    """Bind private reads to one authenticated customer and retain tool evidence."""

    def __init__(self, customer):
        """Start a session for a customer in the fixed bank snapshot.

        Args:
            customer: Authenticated fixture identity.

        Raises:
            ValueError: If the customer is unknown.
        """
        if customer not in DATA["customers"]:
            raise ValueError("Unknown simulated customer")
        self._customer = customer
        self.events = []

    def call(self, tool, owner=None):
        """Authorise and execute one read-only tool request.

        Args:
            tool: Catalogue, holdings or risk-profile operation.
            owner: Requested record owner, defaulting to the authenticated customer.

        Returns:
            Access decision and any authorised data.

        Raises:
            ValueError: If the tool name is unknown.
        """
        # Public terms and private records have distinct access rules.
        if tool == "catalogue":
            result = {"allowed": True, "products": deepcopy(DATA["products"])}
        elif tool in ("holdings", "riskProfile"):
            owner = self._customer if owner is None else owner
            if owner != self._customer:
                result = {"allowed": False}
            else:
                field = "holdings" if tool == "holdings" else "risk"
                result = {"allowed": True, "owner": owner,
                          field: deepcopy(DATA["customers"][owner][field])}
        else:
            raise ValueError("Unknown tool: " + str(tool))
        # Copy the result so later changes cannot rewrite the audit record.
        self.events.append({"actor": self._customer, "tool": tool, "requestedOwner": owner,
                            "result": deepcopy(result)})
        return result
