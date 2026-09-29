-- Cortex Agent: RISK_FRAUD_COPILOT
-- Risk, fraud, and regulatory intelligence copilot. Wires the 4 semantic views
-- as Cortex Analyst tools plus the POLICY_SEARCH Cortex Search service, and
-- drives answers through a Signal -> Evidence -> Finding workflow.
--
-- Prereqs: the 4 semantic views (semantics/*.sv.yaml) and semantics/policy_search.sql
-- must be deployed first.
--
-- Note: use the plain $$ dollar-quote delimiter for FROM SPECIFICATION. The
-- labelled $spec$ form fails to parse. Agents cannot be invoked from SQL
-- (no INVOKE_AGENT function); test in Snowsight > AI & ML > Agents or via the
-- Cortex Agent REST API.

CREATE OR REPLACE AGENT RISK_DB.SEMANTICS.RISK_FRAUD_COPILOT
WITH PROFILE='{"display_name": "Risk & Fraud Copilot"}'
COMMENT='Risk, fraud, and regulatory intelligence copilot combining 4 semantic views with policy document search. Answers investigation questions with the Signal -> Evidence -> Finding workflow.'
FROM SPECIFICATION $$
{
  "models": { "orchestration": "auto" },
  "instructions": {
    "response": "You are a Risk, Fraud, and Regulatory Intelligence Copilot for a bank's compliance team. Answer using a Signal -> Evidence -> Finding structure. First state the SIGNAL (what pattern or anomaly was detected). Then present the EVIDENCE (specific figures, customers, transactions, or exposures from the data). Then give the FINDING (a clear conclusion and recommended action). When a question touches compliance rules, thresholds, or required actions, cite the governing policy from the policy_search tool by name. Always be precise with numbers and never invent customers, amounts, or policy text.",
    "orchestration": "Use the analyst tools for anything quantitative or structured: transactions, alerts, customers, accounts, loans, deposits, Basel/IFRS9/liquidity figures. Route AML, sanctions, PEP, and transaction-pattern questions to risk_fraud_signals. Route Basel capital, IFRS9 staging, and liquidity questions to regulatory_reporting. Route account-360, balances, and transaction-trend questions to transaction_account_360. Route case/investigation questions that combine customer, account, and loan facts to investigation_facts. Use the policy_search tool whenever the user asks what a policy says, what a threshold or rule is, or what action is required - and to cite the governing policy alongside a data finding. For combined questions, first retrieve the data evidence from the appropriate analyst tool, then retrieve the relevant policy text, then synthesize.",
    "sample_questions": [
      {"question": "Show me all structuring alerts and which customers are involved"},
      {"question": "What does our AML policy say about the sanctions screening threshold?"},
      {"question": "Generate an investigation summary for the customer with the highest flagged transaction amount"},
      {"question": "What is our IFRS9 stage distribution and total expected credit loss?"},
      {"question": "Which customers have both PEP flags and high-value AML alerts, and what does policy require?"}
    ]
  },
  "tools": [
    {"tool_spec": {"type": "cortex_analyst_text_to_sql", "name": "risk_fraud_signals", "description": "AML monitoring, sanctions screening, PEP exposure, and fraud pattern detection over transactions joined to customers, accounts, sanctions and PEP lists."}},
    {"tool_spec": {"type": "cortex_analyst_text_to_sql", "name": "regulatory_reporting", "description": "Basel capital adequacy (RWA, PD, LGD, EAD), IFRS9 expected credit loss staging, and liquidity coverage (LCR/NSFR) reporting over loans, loan performance and deposits."}},
    {"tool_spec": {"type": "cortex_analyst_text_to_sql", "name": "transaction_account_360", "description": "360-degree view of transaction activity, account balances, customer segmentation and deposit positions over time."}},
    {"tool_spec": {"type": "cortex_analyst_text_to_sql", "name": "investigation_facts", "description": "Case-management investigation facts combining transaction alerts, customer profiles, account details, sanctions/PEP screening and loan performance."}},
    {"tool_spec": {"type": "cortex_search", "name": "policy_search", "description": "Full-text search over the bank's risk and compliance policy documents (AML, transaction monitoring, fraud, Basel credit, Basel liquidity, capital adequacy). Use to cite thresholds, required actions, and violation definitions."}}
  ],
  "tool_resources": {
    "risk_fraud_signals": {"semantic_view": "RISK_DB.SEMANTICS.RISK_FRAUD_SIGNALS"},
    "regulatory_reporting": {"semantic_view": "RISK_DB.SEMANTICS.REGULATORY_REPORTING"},
    "transaction_account_360": {"semantic_view": "RISK_DB.SEMANTICS.TRANSACTION_ACCOUNT_360"},
    "investigation_facts": {"semantic_view": "RISK_DB.SEMANTICS.INVESTIGATION_FACTS"},
    "policy_search": {"name": "RISK_DB.SEMANTICS.POLICY_SEARCH", "id_column": "POLICY_ID", "title_column": "POLICY_NAME", "max_results": 4}
  }
}
$$;
