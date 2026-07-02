import re

with open('/components/qubes-aegis/sys-copilot/heimdall/heimdall_tools.py', 'r') as f:
    content = f.read()

# Update tools dict
content = re.sub(r'("request_documentation": request_documentation\n\s*)}',
                 r'\1,\n            "deploy_autonomous_subagent_researcher": deploy_autonomous_subagent_researcher,\n            "deploy_personal_interest_researcher": deploy_personal_interest_researcher,\n            "deploy_proactive_log_monitor": deploy_proactive_log_monitor,\n            "deploy_proactive_architect": deploy_proactive_architect,\n            "manage_pci_device": manage_pci_device,\n            "save_hardware_profile": save_hardware_profile\n        }', content)

new_schemas = '''
            },
            {
                "name": "deploy_autonomous_subagent_researcher",
                "description": "Deploys a scheduled autonomous subagent researcher that filters sensationalism, adapts to urgency, evaluates claims objectively based on SQLite memory, and tracks domain reputation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name of the researcher topic."},
                        "objective": {"type": "string"},
                        "cron_schedule": {"type": "string"}
                    },
                    "required": ["name", "objective", "cron_schedule"]
                }
            },
            {
                "name": "deploy_personal_interest_researcher",
                "description": "Deploys an autonomous subagent for researching personal interests, using a highly private Tor (sys-whonix) connection to prevent profiling.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "interests": {"type": "array", "items": {"type": "string"}},
                        "cron_schedule": {"type": "string"}
                    },
                    "required": ["name", "interests", "cron_schedule"]
                }
            },
            {
                "name": "deploy_proactive_log_monitor",
                "description": "Deploys a proactive subagent to periodically scan Qubes audit logs and syslog for security threats or anomalies.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cron_schedule": {"type": "string"}
                    },
                    "required": ["cron_schedule"]
                }
            },
            {
                "name": "deploy_proactive_architect",
                "description": "Deploys a proactive subagent to review a project's codebase and independently propose architectural or philosophy-specific improvements to Heimdall memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "project_path": {"type": "string", "description": "Absolute path to the project"},
                        "cron_schedule": {"type": "string"}
                    },
                    "required": ["project_path", "cron_schedule"]
                }
            },
            {
                "name": "manage_pci_device",
                "description": "Attaches or detaches a PCI device to a VM dynamically based on logical context inferred by the AI.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vm_name": {"type": "string"},
                        "action": {"type": "string", "enum": ["attach", "detach"]},
                        "pci_id": {"type": "string", "description": "PCI ID like 00:1c.4"}
                    },
                    "required": ["vm_name", "action", "pci_id"]
                }
            },
            {
                "name": "save_hardware_profile",
                "description": "Saves a hardware profile containing context and PCI topology based on abstract user interactions.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "profile_name": {"type": "string"},
                        "description": {"type": "string"},
                        "pci_devices": {"type": "array", "items": {"type": "string"}}
                    },
                    "required": ["profile_name", "description", "pci_devices"]
                }
'''

content = re.sub(r'("required": \["topic", "description"\]\n\s*\}\n\s*)\}\n\s*\]', r'\1' + new_schemas + r'\n        }\n        ]', content)

with open('/components/qubes-aegis/sys-copilot/heimdall/heimdall_tools.py', 'w') as f:
    f.write(content)

