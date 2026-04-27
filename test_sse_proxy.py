"""Test SSE through Next.js proxy on port 3000 vs direct on port 8000."""
import urllib.request
import json
import time

body = json.dumps({
    "source_code": "import os\ndef run(cmd):\n    os.system(cmd)\n",
    "file_name": "test.py",
    "language": "python",
}).encode()

for label, port in [("DIRECT (8000)", 8000), ("PROXY (3000)", 3000)]:
    print(f"\n{'='*60}")
    print(f"  Testing {label}")
    print(f"{'='*60}")
    
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}/api/analyze/stream",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    
    try:
        start = time.time()
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            elapsed = time.time() - start
            
            events = []
            current_event = None
            for line in raw.split("\n"):
                if line.startswith("event: "):
                    current_event = line[7:].strip()
                elif line.startswith("data: ") and current_event:
                    try:
                        data = json.loads(line[6:])
                        events.append((current_event, data))
                    except:
                        pass
                    current_event = None
            
            print(f"  Time: {elapsed:.2f}s")
            print(f"  Events received: {len(events)}")
            for evt_name, evt_data in events:
                keys = list(evt_data.keys()) if isinstance(evt_data, dict) else "?"
                print(f"    [{evt_name}] keys={keys}")
                if evt_name == "vulnerabilities":
                    print(f"      vulns={len(evt_data.get('vulnerabilities', []))}")
                elif evt_name == "verification":
                    sb = evt_data.get("sandbox", {})
                    print(f"      sandbox.original_runs={sb.get('original_runs')}")
                    print(f"      sandbox.test_passed={sb.get('test_passed')}")
    except Exception as e:
        print(f"  ERROR: {e}")
