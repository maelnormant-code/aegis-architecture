import socket
import os
import json
import re

LLM_SOCK = "/run/aegis/llm.sock"

def call_llm(prompt):
    """Call the LLM running in sys-ai via the local proxy socket."""
    if not os.path.exists(LLM_SOCK):
        return "Error: LLM socket proxy not available."

    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.connect(LLM_SOCK)
        req = {
            "model": "aegis-model",
            "messages": [
                {"role": "system", "content": "You are Aegis Copilot."},
                {"role": "user", "content": prompt}
            ]
        }
        body = json.dumps(req)
        http_req = (
            f"POST /v1/chat/completions HTTP/1.1\r\n"
            f"Host: localhost\r\n"
            f"Content-Type: application/json\r\n"
            f"Content-Length: {len(body)}\r\n"
            f"\r\n"
            f"{body}"
        )
        s.sendall(http_req.encode('utf-8'))
        
        response_data = b""
        s.settimeout(60)
        while True:
            try:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                if b"0\r\n\r\n" in chunk: # end of chunked transfer
                    break
            except socket.timeout:
                break
        
        headers_end = response_data.find(b"\r\n\r\n")
        if headers_end != -1:
            header_data = response_data[:headers_end]
            body_data = response_data[headers_end+4:]
            
            if b"Transfer-Encoding: chunked" in header_data or b"transfer-encoding: chunked" in header_data:
                clean_body = b""
                idx = 0
                while idx < len(body_data):
                    chunk_end = body_data.find(b"\r\n", idx)
                    if chunk_end == -1: break
                    chunk_size_str = body_data[idx:chunk_end]
                    try:
                        chunk_size = int(chunk_size_str, 16)
                    except ValueError:
                        break
                    if chunk_size == 0: break
                    clean_body += body_data[chunk_end+2 : chunk_end+2+chunk_size]
                    idx = chunk_end + 2 + chunk_size + 2
                body_data = clean_body
            
            try:
                resp_json = json.loads(body_data.decode('utf-8'))
                if "choices" in resp_json and len(resp_json["choices"]) > 0:
                    return resp_json["choices"][0]["message"].get("content", "")
                else:
                    return "Error: Could not parse content from LLM response."
            except Exception as e:
                return f"Error parsing response: {str(e)}"
        else:
            return "Error: Invalid HTTP response."
    except Exception as e:
        return f"Error connecting to LLM: {str(e)}"
    finally:
        s.close()
