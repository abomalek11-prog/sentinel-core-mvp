from sentinel_core import CPGBuilder, CodeParser

source = 'import os\nimport pickle\nimport yaml\n\ndef handle_request(user_input):\n    result = eval(user_input)\n    os.system("echo " + user_input)\n    obj = pickle.loads(user_input.encode())\n    cfg = yaml.load(user_input)\n    return result\n'

parser = CodeParser()
parsed = parser.parse_source(source)
builder = CPGBuilder()
cpg = builder.build(parsed)
nx_graph = builder.to_networkx(cpg)

print("=== NODES ===")
for nid, attrs in nx_graph.nodes(data=True):
    print(nid, dict(attrs))

print("=== CPG NODES ===")
for nid, node in cpg.nodes.items():
    print(nid, node.node_type.value, repr(node.name), node.start_line)
