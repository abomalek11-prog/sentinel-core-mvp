from sentinel_core.agents.graph import run_pipeline
from sentinel_core.parsing import CodeParser
from sentinel_core.gnn import CPGBuilder

code = 'eval("x")'
parser = CodeParser()
parsed = parser.parse_source(code)
builder = CPGBuilder()
nx_graph = builder.to_networkx(builder.build(parsed))

state = run_pipeline(source_code=code, language='python', cpg_graph=nx_graph)
print('SANDBOX:', state.get('sandbox_verification'))
