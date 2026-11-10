import argparse
import json


def main():
    parser = argparse.ArgumentParser(prog="cadbridge")
    parser.add_argument("command", choices=["serve", "doctor", "catalog", "demo"], nargs="?", default="serve")
    parser.add_argument("--output", default="")
    args = parser.parse_args()
    if args.command == "serve":
        from .server import main as serve

        serve()
        return
    from .core import Bridge

    bridge = Bridge()
    try:
        result = bridge.call("connect", cad_type="zwcad")
        if result["ok"] and args.command == "catalog":
            result = bridge.call("catalog")
        elif result["ok"] and args.command == "demo":
            from .demo import create_demo

            result = create_demo(bridge, args.output)
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
        if not result["ok"]:
            raise SystemExit(1)
    finally:
        bridge.close()


if __name__ == "__main__":
    main()
