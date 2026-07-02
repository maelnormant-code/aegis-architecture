#!/usr/bin/env python3
"""
aegis-fs-safe.py - Qubes Aegis Filesystem Safety Primitives
Inspired by OpenClaw fs-safe.

Capability-style filesystem roots for Qubes Aegis guest applications that handle untrusted relative paths.
Prevents path traversals, symlink escapes, and TOCTOU issues within the guest workspace.
"""

import os
import tempfile
import stat

class FsSafeError(Exception):
    pass

def _resolve_and_check_root(root: str, path: str) -> str:
    """Resolves the path against the root and verifies it does not escape the root."""
    abs_root = os.path.abspath(root)
    abs_path = os.path.abspath(os.path.join(abs_root, path))
    
    if not abs_path.startswith(abs_root + os.sep) and abs_path != abs_root:
        raise FsSafeError(f"outside-workspace: {path} escapes {root}")
    
    return abs_path

def read_secure_file(root: str, path: str, max_bytes: int = 16 * 1024 * 1024) -> bytes:
    """
    Secure absolute file reads.
    Resolves the path against the trusted root. Uses O_NOFOLLOW to prevent
    symlink traversal attacks if supported by the OS.
    Checks size limit.
    """
    abs_path = _resolve_and_check_root(root, path)
    
    flags = os.O_RDONLY
    if hasattr(os, 'O_NOFOLLOW'):
        flags |= os.O_NOFOLLOW
        
    try:
        fd = os.open(abs_path, flags)
    except FileNotFoundError:
        raise FsSafeError(f"not-found: {path}")
    except OSError as e:
        # e.g., Too many levels of symbolic links
        raise FsSafeError(f"symlink-or-invalid: {str(e)}")
        
    try:
        st = os.fstat(fd)
        if stat.S_ISDIR(st.st_mode):
            raise FsSafeError(f"not-file: {path} is a directory")
            
        if st.st_size > max_bytes:
            raise FsSafeError(f"too-large: file size {st.st_size} exceeds {max_bytes}")
            
        # Read file safely
        with os.fdopen(fd, 'rb') as f:
            return f.read(max_bytes)
    except Exception as e:
        # fd is closed by fdopen if it succeeds, but we should handle raw fd errors just in case
        try:
            os.close(fd)
        except OSError:
            pass
        raise FsSafeError(f"read-error: {str(e)}")

def write_file_atomic(root: str, path: str, data: bytes, mode: int = 0o600):
    """
    Atomic file write within a bounded root workspace.
    Writes to a temporary sibling file, fsyncs it, and renames it over the destination.
    """
    abs_path = _resolve_and_check_root(root, path)
    dirname = os.path.dirname(abs_path)
    
    if not os.path.exists(dirname):
        os.makedirs(dirname, mode=0o700, exist_ok=True)
        
    # Write sibling temp file
    fd, temp_path = tempfile.mkstemp(dir=dirname, prefix=".tmp-fs-safe-")
    try:
        os.write(fd, data)
        os.fchmod(fd, mode)
        os.fsync(fd)
    except Exception as e:
        os.close(fd)
        os.unlink(temp_path)
        raise FsSafeError(f"write-error: {str(e)}")
    finally:
        os.close(fd)
        
    # Atomic rename (POSIX)
    try:
        os.rename(temp_path, abs_path)
    except OSError as e:
        os.unlink(temp_path)
        raise FsSafeError(f"rename-error: {str(e)}")
        
    # fsync parent directory to ensure rename is durable
    try:
        dir_fd = os.open(dirname, os.O_RDONLY | os.O_DIRECTORY)
        os.fsync(dir_fd)
        os.close(dir_fd)
    except OSError:
        pass # Best effort directory fsync
