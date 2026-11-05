import argparse
import json
from pathlib import Path
import sys
from .pipeline import run, save_json
from .provider import Gemini


def main():
    parser = argparse.ArgumentParser(description="Builtii drawing-only takeoff and independent audit")
    commands = parser.add_subparsers(dest="command", required=True)
    takeoff = commands.add_parser("extract", help="AI1 + AI2 extraction; no BOQ input")
    takeoff.add_argument("pdf", type=Path)
    takeoff.add_argument("--output", type=Path, default=Path("data/runs"))
    takeoff.add_argument("--force", action="store_true", help="Refresh both extractors; incurs new API calls")
    evaluate = commands.add_parser("evaluate", help="Offline held-out BOQ evaluation")
    evaluate.add_argument("--report", type=Path, required=True)
    evaluate.add_argument("--reference", type=Path, required=True, help="Human-reviewed CSV")
    evaluate.add_argument("--mapping", type=Path, required=True, help="Explicit observation mappings bound to run_id")
    evaluate.add_argument("--output", type=Path, required=True)
    serve = commands.add_parser("serve", help="Start local upload and review workbench")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args()
    try:
        if args.command == "extract":
            folder, report = run(args.pdf, args.output, Gemini(),
                                 lambda done, total, message: print(message, flush=True), args.force)
            print(f"Report: {folder/'report.html'}")
            print(json.dumps(report["summary"]))
            return 0 if report["processing_complete"] else 2
        if args.command == "evaluate":
            from .evaluation import evaluate as compare
            result = compare(args.report, args.reference, args.mapping)
            save_json(args.output, result)
            print(json.dumps(result["metrics"]))
            return 0
        import uvicorn
        from .web import create_app
        uvicorn.run(create_app(args.data_dir), host="127.0.0.1", port=args.port)
        return 0
    except (ValueError, OSError, RuntimeError) as exc:
        print(f"Builtii: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
