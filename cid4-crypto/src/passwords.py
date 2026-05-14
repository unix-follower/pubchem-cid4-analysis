from __future__ import annotations

import hashlib
import os
import bcrypt
from argon2 import PasswordHasher
import constants


def make_argon2_hash(password: str) -> str:
    argon2_hasher = PasswordHasher()
    # verify: bool(argon2_hasher.verify(argon2_hash, password))
    return argon2_hasher.hash(password)


def make_bcrypt_hash(password: str) -> str:
    password_bytes = password.encode(constants.UTF_8)
    # verify: bool(bcrypt.checkpw(password_bytes, bcrypt_hash.encode(constants.UTF_8)))
    return bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12)).decode(constants.UTF_8)


def make_scrypt_hash(password: str) -> str:
    password_bytes = password.encode(constants.UTF_8)
    scrypt_salt = os.urandom(16)
    # 64 based salt: salt_b64 = base64.b64encode(scrypt_salt).decode("ascii")
    # verify: hashlib.scrypt(password_bytes, salt=scrypt_salt, n=2**14, r=8, p=1).hex() == scrypt_hash
    return hashlib.scrypt(password_bytes, salt=scrypt_salt, n=2**14, r=8, p=1).hex()


def make_pbkdf2_hmac_sha256_hash(password: str) -> str:
    password_bytes = password.encode(constants.UTF_8)
    pbkdf2_salt = os.urandom(16)
    # 64 based salt: base64.b64encode(pbkdf2_salt).decode("ascii")
    # verify: hashlib.pbkdf2_hmac("sha256", password_bytes, pbkdf2_salt, 600_000).hex() == pbkdf2_hash
    return hashlib.pbkdf2_hmac("sha256", password_bytes, pbkdf2_salt, 600_000).hex()
