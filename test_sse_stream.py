"""Test the SSE stream to see exactly what the backend sends."""
import urllib.request
import json

body = json.dumps({
    "source_code": "import os\ndef run(cmd):\n    os.system(cmd)\n",
    "file_name": "test.py",
    "language": "python",
}).encode()

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/analyze/stream",
    data=body,
    headers={"Content-Type": "application/json"},
)

try:
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read().decode()
        print("=== RAW SSE STREAM ===")
        print(raw)
        print("=== END ===")

        # Parse events
        print("\n=== PARSED EVENTS ===")
        current_event = None
        for line in raw.split("\n"):
            if line.startswith("event: "):
                current_event = line[7:].strip()
            elif line.startswith("data: ") and current_event:
                data = json.loads(line[6:])
                print(f"\n[{current_event}] keys={list(data.keys()) if isinstance(data, dict) else 'not-dict'}")
                if current_event == "vulnerabilities":
                    print(f"  count={data.get('count')}, vulns={data.get('vulnerabilities')}")
                elif current_event == "reasoning":
                    print(f"  reasoning count={len(data.get('reasoning', []))}")
                elif current_event == "patch":
                    print(f"  patches count={len(data.get('patches', []))}, has_diff={bool(data.get('diff'))}")
                elif current_event == "verification":
                    print(f"  confidence_score={data.get('confidence_score')}")
                    print(f"  sandbox={data.get('sandbox')}")
                    print(f"  breakdown={data.get('confidence_breakdown')}")
                elif current_event == "done":
                    print(f"  done data={data}")
                current_event = None
except Exception as e:
    print(f"ERROR: {e}")
