"""Test-set lockbox (design §3.3h): holdout data encrypted at rest.

Design: **the key file IS the Fernet key.** No key material exists anywhere
except that one file, which lives OUTSIDE the repo and which my development
tooling was configured never to read. Consequences:

1. Accidental peeking is impossible: development code cannot decrypt the
   holdout slice because no key exists on any path it reads.
2. Authorization is cryptographic, not procedural: editing final_eval.py to
   skip a key check gains nothing, because without the key there is no
   decryption.
3. Audit: every access attempt (build, open, refused read) lands in
   research/lockbox_access.log.

Code that builds a lockbox cannot make it fully tamper-proof (code could in
principle reconstruct the key path at runtime and read it); the read guard
makes that loud and the log makes it auditable, so a peek is deliberate,
never accidental. That is the §3.3h design goal.
"""
import datetime
import os

from cryptography.fernet import Fernet, InvalidToken

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCKBOX_DIR = os.path.join(REPO, "data", "lockbox")
TOKEN_PATH = "/workspace/OPERATOR_TOKEN.txt"
ACCESS_LOG = os.path.join(REPO, "research", "lockbox_access.log")


def _audit(line: str, access_log: str = ACCESS_LOG, *,
           critical: bool = False) -> None:
    """Append an audit line. critical=True lines are load-bearing one-shot
    markers (BUILT / OPEN ALLOWED / FINAL_EVAL RUN): if they cannot be
    written, the operation must NOT proceed silently — we raise."""
    try:
        with open(access_log, "a") as f:
            f.write(f"{datetime.datetime.now().isoformat()} {line}\n")
    except OSError as e:
        if critical:
            raise RuntimeError(
                f"audit log {access_log} unwritable — refusing to proceed "
                f"without an audit trail: {line!r}") from e


def build_lockbox(holdout_csv_bytes: bytes, *, lockbox_dir: str = LOCKBOX_DIR,
                  token_path: str = TOKEN_PATH,
                  access_log: str = ACCESS_LOG) -> str:
    """Encrypt the holdout slice; write the key to key_path (token_path),
    outside the repo. Never prints or returns the key.

    Idempotence guard: refuses to overwrite an existing lockbox OR key file;
    re-cutting the holdout requires deleting both by hand (prevents silent
    re-cuts of the holdout).
    """
    enc_path = os.path.join(lockbox_dir, "holdout.enc")
    for p in (enc_path, token_path):
        if os.path.exists(p):
            raise FileExistsError(
                f"{p} already exists. Re-cutting the holdout requires the "
                "operator to delete the old lockbox and token themselves.")
    os.makedirs(lockbox_dir, exist_ok=True)
    key = Fernet.generate_key()                     # this IS the unlock key
    fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "wb") as f:
        f.write(key + b"\n")
    with open(enc_path, "wb") as f:
        f.write(Fernet(key).encrypt(holdout_csv_bytes))
    _audit(f"BUILT lockbox: {enc_path} ({len(holdout_csv_bytes)} plaintext bytes); "
           f"token written for operator only", access_log, critical=True)
    return enc_path


def open_lockbox(operator_token: str, *, lockbox_dir: str = LOCKBOX_DIR,
                 access_log: str = ACCESS_LOG) -> bytes:
    """Decrypt the holdout slice. ONLY final_eval.py may call this, once."""
    enc_path = os.path.join(lockbox_dir, "holdout.enc")
    try:
        f = Fernet(operator_token.strip().encode())
        data = f.decrypt(open(enc_path, "rb").read())
    except (InvalidToken, ValueError) as e:
        _audit(f"OPEN REFUSED (bad token): {enc_path}", access_log)
        raise PermissionError(
            "Invalid operator token — final eval not authorized.") from e
    _audit(f"OPEN ALLOWED: {enc_path} decrypted ({len(data)} bytes)", access_log,
           critical=True)
    return data
