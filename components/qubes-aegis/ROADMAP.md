# Qubes Aegis - Smart Suite Roadmap

## Overarching Goal
**Achieve a ready-to-build directory structure for the first live test of the Qubes Aegis ISO.**

---

## Phase 1: Codebase Stabilization & Validation
*Status: COMPLETED*
*Objective: Ensure all scripts and configurations are syntactically correct and fully functional.*

1. ~~**Syntax & Bug Resolution**:~~
   - ~~Run `py_compile` and `mypy` on all python scripts in `sys-copilot`, `sys-knowledge`, and `dom0`.~~ *(Done: All scripts compile successfully)*
   - ~~Fix remaining string escaping issues in `heimdall_tools.py` related to `introspect_self` and `deploy_darknet_scout`.~~ *(Done: Replaced via patch script and verified)*
2. ~~**Tool Registry Verification**:~~
   - ~~Ensure the `ToolRegistry` dynamically loads all schemas (e.g., proactive thinkers, darknet scouts) without JSON/dict errors.~~ *(Done)*
3. **RPC Policy Audit**:
   - Review `/components/qubes-aegis/dom0/30-aegis.policy` for least-privilege enforcement. *(Ongoing)*

---

## Phase 2: Build System Integration
*Objective: Ensure the project can be seamlessly packaged into Qubes RPMs via qubes-builder.*

1. **Makefile.builder Finalization**:
   - Ensure `Makefile.builder` includes all necessary sub-components (`dom0`, `sys-copilot`, `sys-knowledge`).
2. **Spec File Validation**:
   - Test `rpmbuild` locally for `qubes-aegis-dom0.spec`, `qubes-aegis-sys-copilot.spec`, and `qubes-aegis-sys-knowledge.spec`.
   - Verify dependencies (`dependencies-fedora.txt`, `dependencies-debian.txt`) are accurately reflected in the spec files.
3. **Systemd Services**:
   - Verify paths and permissions in `aegis-heimdall.service` and `aegis-knowledge-server.service`.

---

## Phase 3: Integration & Knowledge Bootstrapping
*Objective: Pre-populate the agent's knowledge base and ensure sub-systems communicate properly.*

1. **Self-Introspection to Knowledge Base**:
   - Utilize the `introspect_self` tool to automatically generate documentation for `sys-knowledge`.
   - Add nodes and links describing Aegis's own capabilities, limitations, and darknet routing protocols to the RAG database.
2. **Inter-VM Communication Tests**:
   - Verify qrexec calls from `sys-copilot` to `dom0` (e.g., `ApplyAISystemState`).
   - Verify qrexec calls from `sys-copilot` to `sys-knowledge` (`KnowledgeQuery`).

---

## Phase 4: ISO Preparation & Live Testing
*Objective: Produce a bootable Qubes OS ISO with Aegis pre-installed.*

1. **Qubes ISO Builder Integration**:
   - Clone `qubes-build-v2` (or `qubes-builder`).
   - Add `qubes-aegis` as a component to the `builder.conf`.
   - Configure the build process to include the compiled RPMs in the `dom0` and template repositories of the ISO.
2. **Live Test Matrix**:
   - **Test 1**: Verify `sys-copilot` initializes on boot.
   - **Test 2**: Issue a natural language command to create a VM (verifies Dom0 Salt execution).
   - **Test 3**: Deploy a `darknet_scout` over Tor/I2P and verify network isolation.
   - **Test 4**: Check ACS (Automated Context System) memory retention after reboot.

---

## Post-ISO Release
- Refine LLM prompts based on live test behavior.
- Expand knowledge base with official Qubes OS documentation.
- Harden anti-censorship protocols for environments hostile to AI-scrapers.
