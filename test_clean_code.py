"""Test what the pipeline returns for CLEAN code (0 vulnerabilities)."""
import json
from sentinel_core.agents.graph import run_pipeline
from sentinel_core.parsing import CodeParser
from sentinel_core.gnn import CPGBuilder

code = 'print("hello world")'
parser = CodeParser()
parsed = parser.parse_source(code)
builder = CPGBuilder()
nx_graph = builder.to_networkx(builder.build(parsed))

state = run_pipeline(source_code=code, language='python', cpg_graph=nx_graph)

print("=== FINAL STATE FOR CLEAN CODE ===")
print(f"vulnerabilities: {state.get('vulnerabilities')}")
print(f"reasoning: {state.get('reasoning')}")
print(f"proposed_patches: {state.get('proposed_patches')}")
print(f"confidence_score: {state.get('confidence_score')}")
print(f"confidence_breakdown: {state.get('confidence_breakdown')}")
print(f"sandbox_verification: {state.get('sandbox_verification')}")
print(f"patch_report: {state.get('patch_report')}")
print(f"verification_results: {state.get('verification_results')}")
print(f"llm_model: {state.get('llm_model')}")
