#!/usr/bin/env python3
"""
aegis-confirm.py — Dom0 GUI confirmation dialogs for Qubes Aegis AI actions.

SECURITY CONTRACT:
  - This script runs ONLY in Dom0.
  - The risk_level argument MUST be set by the Dom0 RPC handler — never by
    the untrusted VM that originated the request.
  - The prompt_text argument is display-only and is HTML-escaped before
    being passed to zenity to prevent Pango markup injection.

AUDIT FIXES (2026-06-29):
  - CRITICAL-SEC-5: 'grave' risk now performs actual PAM password verification.
    Previously accepted any non-empty string from zenity --password.
  - HIGH-SEC-6: prompt_text is now HTML-escaped (html.escape) before display
    to prevent Pango markup injection / UI spoofing.
  - Added strict risk_level allowlist — unknown values deny by default.
  - Added timeout to zenity --password call to prevent indefinite blocking.
"""

import sys
import subprocess
import html
import getpass


# ─── Pango/HTML Sanitization ────────────────────────────────────────────────

def sanitize_for_zenity(text: str) -> str:
    """
    Escape Pango markup characters so zenity renders the text literally.
    This prevents UI spoofing via injected <b>, <span color=...>, <a href=...>
    tags in the prompt text that originated from an untrusted VM payload.
    """
    # html.escape replaces: & → &amp;  < → &lt;  > → &gt;  " → &quot;
    return html.escape(text, quote=True)


# ─── PAM Password Verification ──────────────────────────────────────────────

def verify_dom0_password(password: str) -> bool:
    """
    Verify that `password` matches the Dom0 user's login credentials via PAM.

    Preferred method: python-pam library (install: qubes-dom0-update python3-pam)
    Fallback method:  sudo -S (reads password from stdin, -k forces re-auth)

    Returns True if the password is correct, False otherwise.
    Never raises — all exceptions are caught and treated as auth failure.
    """
    if not password:
        return False

    # Method 1: python-pam (most correct — uses the 'login' PAM stack)
    try:
        import pam  # python3-pam package
        p = pam.pam()
        user = getpass.getuser()
        return p.authenticate(user, password, service='login')
    except ImportError:
        pass  # Fall through to method 2
    except Exception:
        return False

    # Method 2: sudo -S fallback (sudo must be installed and allow 'true')
    # -k forces password re-prompt; -S reads password from stdin
    try:
        result = subprocess.run(
            ["sudo", "-S", "-k", "true"],
            input=(password + "\n").encode("utf-8"),
            capture_output=True,
            timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False


# ─── Confirmation Dialogs ────────────────────────────────────────────────────

def confirm_low() -> int:
    """Low risk: Silent approval. No user interaction required (spec §5)."""
    return 0


def confirm_medium(prompt_text: str) -> int:
    """
    Medium risk: Simple approve/reject dialog (spec §5).
    Shows the proposed action summary and waits for user confirmation.
    """
    safe_text = sanitize_for_zenity(prompt_text)
    res = subprocess.call([
        "zenity", "--question",
        "--title=Aegis Copilot: Action Required",
        "--width=600",
        "--no-markup",      # Disable Pango markup parsing — safe_text is already escaped
        "--text=⚠️  Aegis Copilot is requesting permission to perform a system action:\n\n"
               + safe_text
               + "\n\nDo you approve this change?"
    ])
    return res  # 0 = user clicked OK/Yes; 1 = user clicked Cancel/No


def confirm_grave(prompt_text: str) -> int:
    """
    Grave risk: Full screen modal with Dom0 password verification (spec §5).
    The password IS verified against PAM — not just checked for non-emptiness.
    """
    safe_text = sanitize_for_zenity(prompt_text)

    # Step 1: Show action detail and request acknowledgement
    detail_res = subprocess.call([
        "zenity", "--warning",
        "--title=⛔ Aegis GRAVE RISK Action",
        "--width=650",
        "--no-markup",
        "--text=🚨 A HIGH-RISK irreversible action has been requested:\n\n"
               + safe_text
               + "\n\n"
               + "This action modifies critical system configuration "
                 "(qrexec policies, firewall rules, or template settings).\n\n"
                 "You will be required to enter your Dom0 password to proceed."
    ])
    if detail_res != 0:
        return 1

    # Step 2: Collect Dom0 password (max 3 attempts)
    for attempt in range(1, 4):
        try:
            result = subprocess.run(
                ["zenity", "--password",
                 "--title=Dom0 Authorization Required"
                           + (f" (Attempt {attempt}/3)" if attempt > 1 else "")],
                capture_output=True,
                timeout=120    # 2-minute timeout — prevents indefinite blocking
            )
        except subprocess.TimeoutExpired:
            subprocess.call([
                "zenity", "--error",
                "--text=Authorization timed out. Action rejected."
            ])
            return 1

        if result.returncode != 0:
            # User cancelled the password dialog
            return 1

        password = result.stdout.decode("utf-8").rstrip("\n")

        # Step 3: Verify against PAM — MANDATORY
        if verify_dom0_password(password):
            return 0  # Auth success — allow the action

        # Auth failed — warn and retry (up to 3 attempts)
        subprocess.call([
            "zenity", "--error",
            "--width=400",
            "--text=❌ Incorrect password. Please try again."
                    + (f" ({3 - attempt} attempt(s) remaining)" if attempt < 3 else "")
        ])

    # Exhausted all attempts
    subprocess.call([
        "zenity", "--error",
        "--text=Authorization failed after 3 attempts. Action rejected."
    ])
    return 1


# ─── Entry Point ─────────────────────────────────────────────────────────────

def main() -> None:
    if len(sys.argv) < 3:
        print(
            "Usage: aegis-confirm.py <risk_level> <prompt_text>\n"
            "  risk_level: low | medium | grave",
            file=sys.stderr
        )
        sys.exit(1)

    risk_level = sys.argv[1].lower().strip()
    prompt_text = sys.argv[2]

    # Allowlist-based dispatch — unknown risk levels ALWAYS deny
    if risk_level == "low":
        sys.exit(confirm_low())
    elif risk_level == "medium":
        sys.exit(confirm_medium(prompt_text))
    elif risk_level == "grave":
        sys.exit(confirm_grave(prompt_text))
    else:
        # Fail-closed: unknown risk level = deny
        print(f"Unknown risk_level '{risk_level}'. Denying.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
