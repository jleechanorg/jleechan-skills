#!/usr/bin/env python3
"""Stdlib JSONL bridge for an external agent runner; never calls a model/network.
Keep this process and its files inaccessible to the agent under test.
"""
import json
import pathlib
import sys

import autonomy_replay as oracle


def scenario(name):
    case = oracle.C[name]
    return {
        "scenario": name,
        "prompt": case[0],
        "initial_facts": case[1].split(),
        "tools": [{"name": tool, "parameters": {
            "type": "object", "properties": {}, "additionalProperties": False,
        }} for tool in case[2].split()],
        "final_schema": {"status": "completed|blocked|awaiting_approval|waiting|running",
                         "blocker": "null or exact tool-provided {action,target,reason,unblock}"},
    }


class Session:
    """One scenario, one caller-owned trace, no concurrent writers or resumption."""

    def __init__(self, name, path):
        if name not in oracle.C:
            raise ValueError("unknown scenario: " + name)
        self.name = name
        self.trace = []
        self.terminal = False
        self.file = pathlib.Path(path).open("x", encoding="utf-8")
        self._save()

    def _save(self):
        self.file.seek(0)
        json.dump(self.trace, self.file, indent=2)
        self.file.write("\n")
        self.file.truncate()
        self.file.flush()

    def accept(self, request):
        if self.terminal:
            raise ValueError("session already terminal")
        if not isinstance(request, dict):
            self.trace.append({"invalid_request": request})
            self.terminal = True
        elif set(request) == {"tool", "arguments"}:
            if request["arguments"] != {} or not isinstance(request["tool"], str):
                self.trace.append({"invalid_call": request})
                self.terminal = True
            else:
                facts, _ = oracle.replay(self.name, self.trace, terminal=False)
                try:
                    result = oracle.apply(oracle.C[self.name], facts, request["tool"])
                except ValueError as error:
                    result = {"error": str(error)}
                    self.terminal = True
                self.trace.append({"tool": request["tool"], "result": result})
        elif set(request) == {"final"}:
            self.trace.append({"final": request["final"]})
            self.terminal = True
        else:
            self.trace.append({"invalid_request": request})
            self.terminal = True
        self._save()
        return {"event": self.trace[-1], "terminal": self.terminal}

    def verdict(self):
        return oracle.evaluate(self.name, self.trace)

    def close(self):
        self.file.close()


def main(args):
    if len(args) != 2:
        raise ValueError("usage: autonomy_agent_adapter.py CASE NEW_TRACE.json")
    name, path = args
    session = Session(name, path)
    try:
        print(json.dumps({"case": scenario(name)}), flush=True)
        for line in sys.stdin:
            try:
                request = json.loads(line)
            except json.JSONDecodeError:
                request = {"invalid_json": line.rstrip("\n")}
            response = session.accept(request)
            print(json.dumps(response), flush=True)
            if session.terminal:
                break
        verdict = session.verdict()
        print(json.dumps({"evaluation": verdict}), flush=True)
        return 0 if verdict["pass"] else 1
    finally:
        session.close()


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except (ValueError, OSError) as error:
        print(json.dumps({"adapter_error": str(error)}), file=sys.stderr)
        sys.exit(2)
