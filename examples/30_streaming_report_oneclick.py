import argparse
import subprocess
import sys
import time
import webbrowser
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def run_step(script_path: Path) -> None:
    """Run one Python example script in project root."""
    project_root = script_path.parent.parent
    subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(project_root),
        check=True,
    )


def serve_report(
    report_html: Path,
    port: int,
    open_browser: bool,
    serve_seconds: int,
) -> None:
    """Serve report directory on localhost for quick preview."""
    report_dir = report_html.parent
    report_name = report_html.name
    handler = partial(SimpleHTTPRequestHandler, directory=str(report_dir))
    server = ThreadingHTTPServer(("127.0.0.1", port), handler)
    server.timeout = 0.2
    url = f"http://127.0.0.1:{port}/{report_name}"

    if open_browser:
        webbrowser.open(url)
        print("browser_opened=true")
    else:
        print("browser_opened=false")

    print(f"serve_url={url}")
    print(f"serve_seconds={serve_seconds}")
    try:
        if serve_seconds > 0:
            end_at = time.time() + float(serve_seconds)
            while time.time() < end_at:
                server.handle_request()
        else:
            server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("serve_stopped=true")


def main() -> None:
    """Generate stream CSV, build HTML report, and optionally open it."""
    parser = argparse.ArgumentParser(
        description="One-click pipeline for streaming alert CSV and HTML report."
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not open the generated HTML report in a browser.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Start local HTTP preview after report generation.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="HTTP port for --serve mode.",
    )
    parser.add_argument(
        "--serve-seconds",
        type=int,
        default=0,
        help="Auto-stop server after N seconds; 0 means run until interrupted.",
    )
    args = parser.parse_args()

    examples_dir = Path(__file__).resolve().parent
    gen_script = examples_dir / "28_streaming_alerts_and_persist.py"
    report_script = examples_dir / "29_streaming_event_report.py"
    report_html = examples_dir / "output" / "stream_event_report.html"

    run_step(gen_script)
    run_step(report_script)

    if args.serve:
        if not report_html.exists():
            raise FileNotFoundError(f"Report not found: {report_html}")
        serve_report(
            report_html=report_html,
            port=args.port,
            open_browser=not args.no_open,
            serve_seconds=args.serve_seconds,
        )
    elif not args.no_open and report_html.exists():
        webbrowser.open(report_html.as_uri())
        print("browser_opened=true")
    else:
        print("browser_opened=false")

    print(f"report_html={report_html}")
    print("done_streaming_report_oneclick")


if __name__ == "__main__":
    main()
