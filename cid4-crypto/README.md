## Cryptography runner
```sh
uv sync
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
uv run python src/main.py
```

If the crypto dependencies are not installed, the runner still completes and writes explicit `skipped` sections for the unavailable examples instead of failing.

The runner covers these programming-language examples:
- file hashing with SHA-256, SHA-512, BLAKE2b, and MD5 compatibility digests
- HMAC-SHA256 over generated manifest files
- password hashing with Argon2id, bcrypt, scrypt, and PBKDF2-HMAC-SHA256
- symmetric authenticated encryption with AES-256-GCM and ChaCha20-Poly1305
- asymmetric signatures with RSA-PSS, ECDSA P-256, and Ed25519
- asymmetric encryption and key exchange with RSA-OAEP and X25519 hybrid encryption
- X.509 certificate generation and PKCS#12 bundle export for JVM interoperability

Expected outputs under `data/out/crypto`:
- `cid4_crypto.manifest.json`
- `cid4_crypto.summary.json`
- `cid4_crypto.demo.key.pem`
- `cid4_crypto.demo.cert.pem`
- `cid4_crypto.demo.keystore.p12`

Environment variables:
- `CID4_CRYPTO_DEMO_PASSWORD` - optional password used for encrypted private-key and PKCS#12 demo artifacts. If unset, the runner generates a one-time random password and records that it was generated in the summary.

Examples:

```sh
sha256sum data/COMPOUND_CID_4.json
md5 data/COMPOUND_CID_4.json

openssl x509 -in data/out/crypto/cid4_crypto.demo.cert.pem -text -noout
openssl pkcs12 -info -in data/out/crypto/cid4_crypto.demo.keystore.p12 -nokeys
openssl x509 -pubkey -noout -in data/out/crypto/cid4_crypto.demo.cert.pem > cid4_crypto.demo.pubkey.pem
openssl dgst -sha256 -verify cid4_crypto.demo.pubkey.pem -signature data/out/crypto/cid4_crypto.manifest.sig data/out/crypto/cid4_crypto.manifest.json

gpg --armor --detach-sign data/out/crypto/cid4_crypto.manifest.json
age-keygen -o cid4-demo.agekey
age -r <recipient> -o cid4_crypto.manifest.json.age data/out/crypto/cid4_crypto.manifest.json

keytool -list -v -storetype PKCS12 -keystore data/out/crypto/cid4_crypto.demo.keystore.p12
keytool -importkeystore -srckeystore data/out/crypto/cid4_crypto.demo.keystore.p12 -srcstoretype PKCS12 -destkeystore cid4-demo.jks -deststoretype JKS
```

Algorithm guidance:
- Prefer Argon2id for new password hashing.
- Prefer AES-GCM or ChaCha20-Poly1305 for symmetric encryption.
- Prefer Ed25519 and X25519 for new signature or key-exchange examples where interoperability allows it.
- Keep RSA, ECDSA, PKCS#12, and `keytool` because they are still common in enterprise and JVM environments.
- Treat MD5 as compatibility-only. It is included for legacy checksum examples, not for security.
