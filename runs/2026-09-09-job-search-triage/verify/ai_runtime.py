import inspect
import json
import re
import subprocess
import sys

_QUALIFIED = re.compile(r"__n\d+$")


def ai(instruction, payload):
    caller = next(
        (f.function for f in inspect.stack()[1:] if _QUALIFIED.search(f.function)),
        inspect.stack()[1].function,
    )
    prompt = (
        instruction
        + "\n\nPayload (JSON):\n"
        + json.dumps(payload)
        + "\n\nRespond with ONLY the return value, as JSON."
    )
    r = subprocess.run(
        ["claude", "-p", prompt], capture_output=True, text=True, timeout=300
    )
    raw = r.stdout.strip()
    if raw.startswith("```"):
        raw = raw.strip("`\n")
        raw = raw[raw.find("\n") + 1:] if raw.startswith("json") else raw
    value = json.loads(raw)
    print(
        json.dumps(
            {
                "caller": caller,
                "instruction": instruction,
                "payload": payload,
                "return": value,
            }
        ),
        file=sys.stderr,
    )
    return value
