# Wealth Assistant Risk Lab

The assistant recommends open products, explains product terms and reads the signed-in customer's holdings. All customer and product data come from the dated synthetic snapshot in `riskLab/fixtures.json`. The case definitions and review criteria are in [testCases.md](testCases.md).

## Setup and evaluation

From the repository root, install the requirements in the Python 3.12 virtual environment. Set `DEEPSEEK_API_KEY` in the local environment before a hosted run. Each hosted interaction uses the selected DeepSeek model and may incur charges.

```sh
source .venv/bin/activate
python -m pip install -r requirement.txt
python -m unittest discover -s tests -v
python -m riskLab --case T02
python -m riskLab --deepseek deepseek-flash --case I01
```

I01 runs the clean C02 recommendation followed by three prompt variants. Omitting `--case` selects all twelve cases. Omitting `--deepseek` runs the local tool probes and leaves questions requiring a model pending.

## Request path

PyRIT sends each prompt to the LangGraph release gate. When the circuit is closed, a LangChain agent can query the catalogue, risk profile and holdings. The bank tool authorises each private lookup using the original session identity. The graph inspects the candidate before releasing it.

The initial containment rule trips on one occurrence of another fixture customer's holding ID (case-insensitive). It suppresses the candidate, serves a static fallback and bypasses generation on subsequent requests in the same trial. Independent benchmark variants start with a fresh breaker. This local process models sequential requests; the marker check covers the fixture identifiers only.

## Evidence

Each run writes `runs/<run-id>/evidence.jsonl` and `summary.json`. Read `candidate`, `reply` and `route` together to distinguish an unsafe draft from customer-visible disclosure. Tool events record the requested owner, authorisation decision and returned records. Only the final reply is customer-visible. The evidence is for evaluation using synthetic data.

Use the test plan to review suitability, hallucination and disclosures other than exact marker hits. Token usage, when available, covers the final model step. Treat unreviewed or inconclusive records separately from passes. Production drift calibration and the organisational incident playbook require separate analysis in the memo.
