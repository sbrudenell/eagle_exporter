import argparse
import http.server

import prometheus_client

import eagle_exporter


def main():
    parser = argparse.ArgumentParser("Eagle Parser")

    parser.add_argument("--port", type=int, default=9597)
    parser.add_argument("--bind_address", default="0.0.0.0")
    parser.add_argument("--model", choices=("eagle200",), required=True)
    parser.add_argument("--address")
    parser.add_argument("--cloud_id")
    parser.add_argument("--install_code", required=True)

    args = parser.parse_args()

    if not args.address and not args.cloud_id:
        parser.error("--address or --cloud_id must be specified")

    if args.model == "eagle200":
        api = eagle_exporter.Eagle200API(
                address=args.address, cloud_id=args.cloud_id,
                install_code=args.install_code)
        collector = eagle_exporter.Eagle200Collector(api)

    prometheus_client.REGISTRY.register(collector)

    handler = prometheus_client.MetricsHandler.factory(
            prometheus_client.REGISTRY)
    server = http.server.HTTPServer(
            (args.bind_address, args.port), handler)
    server.serve_forever()
