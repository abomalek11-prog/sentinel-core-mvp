"""Debug: check every key in the pipeline state for clean code."""
import json
from sentinel_core.agents.graph import run_pipeline
from sentinel_core.parsing import CodeParser
from sentinel_core.gnn import CPGBuilder

code = "print('hello')"
parser = CodeParser()
parsed = parser.parse_source(code)
builder = CPGBuilder()
nx_graph = builder.to_networkx(builder.build(parsed))

state = run_pipeline(source_code=code, language='python', cpg_graph=nx_graph)

print("=== ALL STATE KEYS ===")
for k, v in state.items():
    if k in ('cpg', 'parsed_file'):
        print(f"  {k}: <skipped>")
    else:
        print(f"  {k}: {v!r}")

print(f"\n=== TYPE OF STATE: {type(state).__name__} ===")
print(f"=== confidence_score in state: {'confidence_score' in state} ===")
print(f"=== confidence_breakdown in state: {'confidence_breakdown' in state} ===")
print(f"=== sandbox_verification in state: {'sandbox_verification' in state} ===")
