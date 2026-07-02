#!/usr/bin/env python3
"""
aegis-mcp-server.py — A fully compliant Model Context Protocol (MCP) server.
Communicates via JSON-RPC 2.0 over stdio.
Exposes tools to the guest agent to query sys-copilot context via qrexec.
"""

import sys
import json
import subprocess
import aegis_mcp_security as security
import aegis_fs_safe as fs_safe

MAX_STDIN_SIZE = 1048576 # 1MB limit

def query_copilot(query: str) -> dict:
    """Calls sys-copilot GetContext RPC via qrexec-client-vm."""
    try:
        process = subprocess.Popen(
            ["qrexec-client-vm", "sys-copilot", "aegis.GetContext"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = process.communicate(input=query.encode('utf-8'), timeout=15)
        if process.returncode != 0:
            return {"status": "error", "message": stderr.decode('utf-8', errors='replace').strip()}
        return json.loads(stdout.decode('utf-8'))
    except subprocess.TimeoutExpired:
        process.kill()
        return {"status": "error", "message": "Query to sys-copilot timed out."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

def send_response(rpc_id, result=None, error=None):
    response = {"jsonrpc": "2.0", "id": rpc_id}
    if error is not None:
        response["error"] = error
    else:
        response["result"] = result
    sys.stdout.write(json.dumps(response) + "\n")
    sys.stdout.flush()

def handle_request(req):
    rpc_id = req.get("id")
    method = req.get("method")
    params = req.get("params", {})

    if method == "initialize":
        # Return MCP server capabilities and info
        result = {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "tools": {},
                "prompts": {}
            },
            "serverInfo": {
                "name": "qubes-aegis-mcp-server",
                "version": "1.0.0"
            }
        }
        send_response(rpc_id, result=result)

    elif method == "prompts/list":
        result = {
            "prompts": [
                {
                    "name": "aegis-wiki-context",
                    "description": "System prompt instructing the client agent to query sys-copilot for wiki context.",
                    "arguments": []
                }
            ]
        }
        send_response(rpc_id, result=result)

    elif method == "prompts/get":
        prompt_name = params.get("name")
        if prompt_name == "aegis-wiki-context":
            result = {
                "description": "System prompt instructing the client agent to query sys-copilot for wiki context.",
                "messages": [
                    {
                        "role": "user",
                        "content": {
                            "type": "text",
                            "text": "You are a Qubes-aware guest AppVM AI assistant. You have access to a tool called `query_copilot` which connects to the sys-copilot context engine (representing the user's personal wiki). Before answering any user queries, you MUST call `query_copilot` to check for relevant context and wiki files. Do not answer from general knowledge alone."
                        }
                    }
                ]
            }
            send_response(rpc_id, result=result)
        else:
            error = {"code": -32601, "message": f"Prompt '{prompt_name}' not found."}
            send_response(rpc_id, error=error)


    elif method == "tools/list":
        # List available tools to the MCP client (like Goose)
        result = {
            "tools": [
                {
                    "name": "query_copilot",
                    "description": "Query the Level 3 Principal Agent (sys-copilot) for system context and cross-VM documentation.",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                                "description": "The search query/topic to look up in the system knowledge base."
                            }
                        },
                        "required": ["query"]
                    }
                }
            ]
        }
        send_response(rpc_id, result=result)

    elif method == "tools/call":
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if tool_name == "query_copilot":
            query = arguments.get("query", "")
            if not query:
                error = {"code": -32602, "message": "Missing 'query' argument."}
                send_response(rpc_id, error=error)
                return
                
            threats = security.scan_text(query)
            if threats:
                error = {"code": -32000, "message": f"Security violation in query: {', '.join(threats)}"}
                send_response(rpc_id, error=error)
                return
                
            res = query_copilot(query)
            
            # MCP tools/call expects result containing a list of content blocks
            if res.get("status") == "ok":
                content_text = res.get("context", "No context returned.")
                threats_resp = security.scan_text(content_text)
                if threats_resp:
                     content_text = "[REDACTED] Response triggered security filter: " + ', '.join(threats_resp)
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": content_text
                        }
                    ],
                    "isError": False
                }
            else:
                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": res.get("message", "Unknown error query context.")
                        }
                    ],
                    "isError": True
                }
            send_response(rpc_id, result=result)
        else:
            error = {"code": -32601, "message": f"Tool '{tool_name}' not found."}
            send_response(rpc_id, error=error)

    elif method == "notifications/initialized":
        # Notifications do not receive a response
        pass

    else:
        # Standard JSON-RPC method not found error
        if rpc_id is not None:
            error = {"code": -32601, "message": f"Method '{method}' not found."}
            send_response(rpc_id, error=error)

def main():
    while True:
        line = sys.stdin.readline(MAX_STDIN_SIZE)
        if not line:
            break
        if not line.endswith('\n'):
            # Line exceeded max size
            send_response(None, error={"code": -32600, "message": "Request exceeds size limit"})
            # consume the rest of the long line so it doesn't break the protocol
            while True:
                extra = sys.stdin.readline(MAX_STDIN_SIZE)
                if not extra or extra.endswith('\n'):
                    break
            continue
            
        try:
            req = json.loads(line)
            handle_request(req)
        except json.JSONDecodeError:
            # Send parse error
            send_response(None, error={"code": -32700, "message": "Parse error"})
        except Exception as e:
            # Internal server error
            send_response(None, error={"code": -32603, "message": str(e)})

if __name__ == "__main__":
    main()
