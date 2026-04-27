"""Test SSE stream for CLEAN code (0 vulnerabilities)."""
import urllib.request
import json

body = json.dumps({
    "source_code": "print('hello world')",
    "file_name": "test.py",
    "language": "python",
}).encode()

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/analyze/stream",
    data=body,
    headers={"Content-Type": "application/json"},
)

with urllib.request.urlopen(req, timeout=30) as resp:
    raw = resp.read().decode()
    current_event = None
    for line in raw.split("\n"):
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: ") and current_event:
            data = json.loads(line[6:])
            print(f"\n[{current_event}]")
            if current_event == "vulnerabilities":
                print(f"  count={data.get('count')}, vulns={data.get('vulnerabilities')}")
            elif current_event == "reasoning":
                print(f"  reasoning={data.get('reasoning')}")
            elif current_event == "patch":
                print(f"  patches={data.get('patches')}")
            elif current_event == "verification":
                print(f"  confidence_score={data.get('confidence_score')}")
                print(f"  breakdown={data.get('confidence_breakdown')}")
                sb = data.get("sandbox", {})
                print(f"  sandbox.original_runs={sb.get('original_runs')}")
                print(f"  sandbox.patched_runs={sb.get('patched_runs')}")
                print(f"  sandbox.behaviour_match={sb.get('behaviour_match')}")
                print(f"  sandbox.test_passed={sb.get('test_passed')}")
                print(f"  sandbox.details={sb.get('details')}")
            elif current_event == "done":
                print(f"  {data}")
            current_event = None
