"""Definitive E2E test: parse + CPG + full pipeline + verify patched_source != source."""
from sentinel_core.parsing.parser import CodeParser
from sentinel_core.gnn.graph_builder import CPGBuilder
from sentinel_core.agents.graph import run_pipeline

# Exact code the user has in the editor
SOURCE = '''\
import subprocess

def process_image(image_name: str):
    command = f"img-tool --input {image_name} --out /tmp/processed.png"
    result = subprocess.check_output(command, shell=True, stderr=subprocess.STDOUT)
    return result
'''

# Build CPG like the API does
parser = CodeParser()
parsed = parser.parse_source(SOURCE)
builder = CPGBuilder()
cpg = builder.build(parsed)
nx_graph = builder.to_networkx(cpg)
print(f"CPG: {cpg.node_count} nodes, {cpg.edge_count} edges")

# Run full pipeline (detection + reasoning + patching + verification)
state = run_pipeline(
    source_code=SOURCE,
    file_path="vulnerable.py",
    language="python",
    cpg_graph=nx_graph,
)

# Check detection
vulns = state.get("vulnerabilities", [])
print(f"\nVulnerabilities: {len(vulns)}")
for v in vulns:
    print(f"  kind={v.get('kind')!r} location={v.get('location')!r}")

# Check patch_report
report = state.get("patch_report", {})
patched_src = report.get("patched_source", "")
print(f"\npatch_report keys: {list(report.keys())}")
print(f"patched_source length: {len(patched_src)}")
print(f"source_code length: {len(SOURCE)}")
print(f"patched_source == SOURCE: {patched_src == SOURCE}")
print(f"shell=True in patched: {'shell=True' in patched_src}")

# This is the critical check — simulates what the frontend does
if patched_src == SOURCE:
    print("\n*** BUG CONFIRMED: patched_source === source_code ***")
    print("*** The frontend will show 'No effective patch changes to apply' ***")
    # Show changes list to debug
    print(f"changes: {report.get('changes', [])}")
    print(f"diff length: {len(report.get('diff', ''))}")
else:
    print("\n*** OK: patched_source differs from source_code ***")
    print("\n=== PATCHED SOURCE ===")
    print(patched_src)
