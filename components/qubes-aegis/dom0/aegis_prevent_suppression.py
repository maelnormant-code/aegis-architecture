import dnf
import subprocess
import json

class AegisPreventSuppressionPlugin(dnf.Plugin):
    name = 'aegis_prevent_suppression'
    
    def __init__(self, base, cli):
        super().__init__(base, cli)
        self.base = base
        
    def pre_confirm(self):
        aegis_pkgs = {'qubes-aegis-dom0', 'qubes-aegis-guest', 'qubes-aegis-sys-copilot', 'qubes-aegis-sys-ai', 'qubes-aegis-sys-knowledge'}
        ts = self.base.transaction
        to_remove = []
        to_check = []
        
        for item in ts:
            if item.action in (dnf.transaction.REMOVE, dnf.transaction.DOWNGRADE):
                if item.name in aegis_pkgs:
                    to_remove.append(item.name)
            elif item.action in (dnf.transaction.INSTALL, dnf.transaction.UPGRADE):
                to_check.append(f"{item.name}-{item.version}-{item.release}")
                
        # 1. Block removal or downgrade of core Aegis packages without password authorization
        if to_remove:
            msg = f"WARNING: You are attempting to remove or downgrade core Aegis components: {', '.join(to_remove)}.\\nThis will disable the Aegis secure AI system."
            cmd = ["/usr/libexec/qubes-aegis/aegis-confirm.py", "grave", msg]
            res = subprocess.run(cmd)
            if res.returncode != 0:
                raise dnf.exceptions.Error("Aegis protection: Transaction cancelled by user or password verification failed.")
                
        # 2. Check proposed installations/updates against the sys-copilot safety database
        if to_check:
            try:
                proc = subprocess.Popen(
                    ["qrexec-client-vm", "sys-copilot", "aegis.VerifyPackages"],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                payload = json.dumps(to_check)
                stdout, stderr = proc.communicate(input=payload.encode('utf-8'), timeout=15)
                if proc.returncode == 0:
                    warnings = json.loads(stdout.decode('utf-8'))
                    if warnings:
                        warn_msg = "WARNING: Contraindicated packages detected in this transaction!\\n\\n"
                        for w in warnings:
                            warn_msg += f"- {w['package']}: {w['reason']}\\n"
                        warn_msg += "\\nDo you want to override this warning and proceed?"
                        cmd = ["/usr/libexec/qubes-aegis/aegis-confirm.py", "grave", warn_msg]
                        res = subprocess.run(cmd)
                        if res.returncode != 0:
                            raise dnf.exceptions.Error("Aegis protection: Transaction rejected due to contraindicated packages.")
            except Exception as e:
                msg = f"WARNING: Could not connect to sys-copilot for package verification: {str(e)}.\\nDo you want to proceed anyway?"
                cmd = ["/usr/libexec/qubes-aegis/aegis-confirm.py", "medium", msg]
                res = subprocess.run(cmd)
                if res.returncode != 0:
                    raise dnf.exceptions.Error("Aegis protection: Transaction cancelled because verification could not be executed.")
