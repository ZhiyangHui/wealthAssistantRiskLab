"""Send a test prompt through PyRIT to the complete bank workflow."""
from pyrit.executor.attack import PromptSendingAttack
from pyrit.models import construct_response_from_request
from pyrit.prompt_target import PromptTarget


class WealthTarget(PromptTarget):
    """Bind one authenticated request to a PyRIT text target."""

    def __init__(self, *, workflow, request, call):
        """Capture the current trial and the runner's trusted session.

        Args:
            workflow: Release gate shared within this trial.
            request: Original case context including the external brief.
            call: Session-bound bank tool callback.
        """
        super().__init__()
        self.workflow = workflow
        self.request = request
        self.call = call
        self.evidence = {}

    async def _send_prompt_to_target_async(self, *, normalized_conversation):
        """Submit the PyRIT-normalised prompt and return the released message.

        Args:
            normalized_conversation: Messages prepared by PyRIT.

        Returns:
            One customer-visible PyRIT message.
        """
        # Only prompt text comes from PyRIT; identity and brief retain their original sources.
        piece = normalized_conversation[-1].get_piece()
        request = {**self.request, "prompt": piece.converted_value}
        self.evidence = self.workflow.respond(request, self.call)
        return [construct_response_from_request(request=piece, response_text_pieces=[self.evidence["reply"]])]


async def send(workflow, request, call):
    """Run a single-turn attack and retain both internal and released output.

    Args:
        workflow: Active trial's release gate.
        request: Test case input and session metadata.
        call: Session-bound bank callback.

    Returns:
        Evidence fields for the JSONL writer.
    """
    # The evaluator's attack prompt traverses the same gate as a customer message.
    target = WealthTarget(workflow=workflow, request=request, call=call)
    attack = PromptSendingAttack(objective_target=target)
    result = await attack.execute_async(objective=request["prompt"])
    if result.last_response is None:
        raise RuntimeError("PyRIT returned no reply")
    return {**target.evidence, "reply": result.last_response.converted_value}
