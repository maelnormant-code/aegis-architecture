#!/usr/bin/env python3
import http.server
import json
import urllib.request
import urllib.error
import os
import sys

PORT = 8080
KEY_FILE = "/var/lib/aegis/gemini.key"
MODEL_FILE = "/var/lib/aegis/gemini.model"

class GeminiProxyHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Log to stderr (captured by journald/systemd)
        sys.stderr.write(f"[Gemini Proxy] {format % args}\n")

    def do_GET(self):
        if self.path in ["/", "/health", "/v1/models"]:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "qubes-aegis-gemini-proxy"}).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        if self.path == "/v1/chat/completions":
            self.handle_completions()
        else:
            self.send_error(404, "Not Found")

    def handle_completions(self):
        # 1. Read API key
        api_key = ""
        if os.path.exists(KEY_FILE):
            try:
                with open(KEY_FILE, "r") as f:
                    api_key = f.read().strip()
            except Exception as e:
                self.log_message("Failed to read API key file: %s", str(e))
                
        if not api_key:
            api_key = os.getenv("GEMINI_API_KEY", "")
        
        if not api_key:
            # Fallback to the default key integrated natively
            api_key = "AQ.Ab8RN6KeZ6polAQhM86NOg3AEhl4AUU9jgyo7EROG7VofLMHWw"

        # 2. Read model override
        model_name = "gemini-1.5-flash"
        if os.path.exists(MODEL_FILE):
            try:
                with open(MODEL_FILE, "r") as f:
                    model_name = f.read().strip()
            except Exception as e:
                self.log_message("Failed to read model override file: %s", str(e))

        # 3. Read request body
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            req_data = json.loads(body.decode("utf-8"))
            # Replace local model path/name with Gemini model
            req_data["model"] = model_name
            new_body = json.dumps(req_data).encode("utf-8")
        except Exception as e:
            self.send_error(400, f"Invalid JSON: {str(e)}")
            return

        # 4. Forward to Gemini OpenAI compatibility endpoint
        url = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        req = urllib.request.Request(url, data=new_body, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=60) as response:
                self.send_response(response.status)
                for header, val in response.getheaders():
                    # Forward headers except standard hop-by-hop or content-length (since it might change)
                    if header.lower() not in ["content-length", "connection", "transfer-encoding"]:
                        self.send_header(header, val)
                
                is_stream = req_data.get("stream", False)
                if is_stream:
                    self.send_header("Transfer-Encoding", "chunked")
                
                self.end_headers()

                # Stream response
                while True:
                    chunk = response.read(4096)
                    if not chunk:
                        break
                    if is_stream:
                        # Write in HTTP chunked format
                        self.wfile.write(f"{len(chunk):x}\r\n".encode("utf-8"))
                        self.wfile.write(chunk)
                        self.wfile.write(b"\r\n")
                    else:
                        self.wfile.write(chunk)
                    self.wfile.flush()
                
                if is_stream:
                    # Final zero chunk
                    self.wfile.write(b"0\r\n\r\n")
                    self.wfile.flush()

        except urllib.error.HTTPError as e:
            err_body = e.read()
            self.send_response(e.code)
            # Forward response headers from the error if applicable
            for header, val in e.headers.items():
                if header.lower() not in ["content-length", "connection", "transfer-encoding"]:
                    self.send_header(header, val)
            self.end_headers()
            self.wfile.write(err_body)
        except Exception as e:
            self.send_error(500, f"Error calling Gemini API: {str(e)}")

def main():
    server_address = ("127.0.0.1", PORT)
    httpd = http.server.HTTPServer(server_address, GeminiProxyHandler)
    sys.stderr.write(f"Aegis Gemini Proxy running on 127.0.0.1:{PORT}\n")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    sys.stderr.write("Aegis Gemini Proxy shutting down\n")

if __name__ == "__main__":
    main()
