import re

with open('/components/qubes-aegis/sys-copilot/heimdall/heimdall_tools.py', 'r') as f:
    content = f.read()

# Update tools dict
content = re.sub(r'("check_pending_thinker_ideas": check_pending_thinker_ideas\n\s*)}',
                 r'\1,\n            "deploy_darknet_scout": deploy_darknet_scout,\n            "introspect_self": introspect_self\n        }', content)

new_schemas = '''
            },
            {
                "name": "deploy_darknet_scout",
                "description": "Deploys an anti-censorship autonomous subagent that routes exclusively through darknets (Tor/sys-whonix, I2P) to bypass clearweb policing.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "network": {"type": "string", "description": "e.g., 'tor' or 'i2p'"},
                        "objective": {"type": "string"},
                        "cron_schedule": {"type": "string"}
                    },
                    "required": ["name", "network", "objective", "cron_schedule"]
                }
            },
            {
                "name": "introspect_self",
                "description": "Reads Heimdall's own source code and architecture to provide deep self-understanding of capabilities and limitations.",
                "parameters": {
                    "type": "object",
                    "properties": {}
                }
            }
'''

content = re.sub(r'("name": "check_pending_thinker_ideas",[\s\S]*?"properties": \{\}\n\s*\}\n\s*)\}\n\s*\]', 
                 r'\1' + new_schemas + r'\n        }\n        ]', content)

with open('/components/qubes-aegis/sys-copilot/heimdall/heimdall_tools.py', 'w') as f:
    f.write(content)

