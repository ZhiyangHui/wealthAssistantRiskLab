"""Offline integration checks for the model loop and the release boundary."""
import unittest
from unittest.mock import patch

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from riskLab.assistant import FALLBACK, ReleaseGate
from riskLab.bank import BankSession


class ScriptedChat(GenericFakeChatModel):
    """Supply scripted model messages while exercising the real tool loop."""

    def bind_tools(self, tools, **kwargs):
        """Accept the agent's tool schemas and retain the scripted responses."""
        return self


class WorkflowTests(unittest.TestCase):
    """Verify observable behaviour independently of a hosted model."""

    def test_catalogue_call_reaches_the_bank(self):
        """Verify that a tool request returns through LangChain and the release gate."""
        # The first turn requests a real tool; the second supplies the candidate.
        tool = {"name": "catalogue", "args": {}, "id": "call1", "type": "tool_call"}
        model = ScriptedChat(messages=iter([AIMessage(content="", tool_calls=[tool]), AIMessage(content="P01, P02")]))
        bank = BankSession("A")
        result = ReleaseGate(model).respond({"customer": "A", "prompt": "List products.", "thirdPartyBrief": ""}, bank.call)
        self.assertEqual([e["tool"] for e in bank.events], ["catalogue"])
        self.assertEqual((result["route"], result["reply"]), ("released", "P01, P02"))

    def test_foreign_marker_trips_subsequent_requests(self):
        """Verify that one foreign ID blocks the reply and bypasses further inference."""
        request = {"customer": "A", "prompt": "List my holdings.", "thirdPartyBrief": ""}
        gate = ReleaseGate(None)
        # Use the same circuit for two requests, as a running service would.
        with patch("riskLab.assistant.draft", return_value={"candidate": "B-K84"}) as generate:
            first = gate.respond(request, BankSession("A").call)
            second = gate.respond(request, BankSession("A").call)
        self.assertEqual(first["route"], "blocked_foreign_id")
        self.assertEqual(first["candidate"], "B-K84")
        self.assertEqual(second["route"], "circuit_open")
        self.assertEqual([first["reply"], second["reply"]], [FALLBACK, FALLBACK])
        generate.assert_called_once()
