from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from urllib.parse import urlparse


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._json(200, {"status": "ok"})
            return
        if "/DecodeVinValuesExtended/" not in parsed.path:
            self._json(404, {"error": "not found"})
            return

        self._json(
            200,
            {
                "Count": 1,
                "Message": "Synthetic local PartGraph VIN provider fixture",
                "SearchCriteria": "local-acceptance",
                "Results": [
                    {
                        "ErrorCode": "0",
                        "ModelYear": "2011",
                        "Make": "Honda",
                        "Model": "Acceptance VIN Stub",
                        "Trim": "EX",
                        "BodyClass": "Sedan/Saloon",
                        "DisplacementL": "1.8",
                        "EngineCylinders": "4",
                        "FuelTypePrimary": "Gasoline",
                        "TransmissionStyle": "Automatic",
                        "TransmissionSpeeds": "5",
                        "DriveType": "FWD",
                    }
                ],
            },
        )

    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


if __name__ == "__main__":
    ThreadingHTTPServer(("0.0.0.0", 8081), Handler).serve_forever()
