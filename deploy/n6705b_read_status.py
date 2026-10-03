#!/usr/bin/env python3
"""Read the identity and SCPI error queue of the configured N6705B.

This helper intentionally contains no SCPI write commands.  It is used by
XiaoQ's mobile/voice path for safe status requests before a user explicitly
asks for a channel configuration change.
"""

from __future__ import annotations

import json
import sys


RESOURCE = "USB0::0x0957::0x0F07::MY53003524::0::INSTR"


def main() -> int:
    try:
        import pyvisa

        manager = pyvisa.ResourceManager("@py")
        instrument = manager.open_resource(RESOURCE)
        instrument.timeout = 5000
        try:
            identity = instrument.query("*IDN?").strip()
            if "N6705B" not in identity.upper():
                raise RuntimeError(f"configured resource is not an N6705B: {identity}")
            error = instrument.query("SYST:ERR?").strip()
        finally:
            instrument.close()
            manager.close()
        print(json.dumps({"resource": RESOURCE, "identity": identity, "error": error}))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
