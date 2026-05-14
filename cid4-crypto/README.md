## Cryptography runner
```bash
uv sync
source .venv/bin/activate
export DATA_DIR="$(pwd)/../data"
uv run python src/main.py
CRYPTO_PASSWORD=test uv run python src/main.py --alg argon2
CRYPTO_PASSWORD=test uv run python src/main.py --alg bcrypt
CRYPTO_PASSWORD=test uv run python src/main.py --alg scrypt
CRYPTO_PASSWORD=test uv run python src/main.py --alg pbkdf2_hmac_sha256
uv run python src/main.py --alg aes_256_gcm --in-file $DATA_DIR/COMPOUND_CID_4.json > out.txt
uv run python src/main.py --alg chacha20_poly1305 --in-file $DATA_DIR/COMPOUND_CID_4.json > out.txt
uv run python src/main.py --alg x25519_hybrid --in-file $DATA_DIR/COMPOUND_CID_4.json > out.txt
uv run python src/main.py --alg ecdsa_p256 --in-file $DATA_DIR/COMPOUND_CID_4.json > out.txt
uv run python src/main.py --alg ed25519 --in-file $DATA_DIR/COMPOUND_CID_4.json > out.txt
uv run python src/main.py --alg rsa --in-file $DATA_DIR/COMPOUND_CID_4.json > out.txt
uv run python src/main.py --alg hash_file --in-file $DATA_DIR/COMPOUND_CID_4.json > out.txt
CRYPTO_PASSWORD=demo-hmac-key uv run python src/main.py --alg hmac_sha256 --in-file $DATA_DIR/COMPOUND_CID_4.json > out.txt
CRYPTO_PASSWORD=test uv run python src/main.py --alg x509
```

Outputs under `data/out/crypto`.

## OpenSSL
```bash
openssl x509 -in data/out/crypto/cid4_crypto.demo.cert.pem -text -noout
openssl pkcs12 -info -in data/out/crypto/cid4_crypto.demo.keystore.p12 -nokeys
openssl x509 -pubkey -noout -in data/out/crypto/cid4_crypto.demo.cert.pem > cid4_crypto.demo.pubkey.pem
openssl dgst -sha256 -verify cid4_crypto.demo.pubkey.pem -signature data/out/crypto/cid4_crypto.manifest.sig data/out/crypto/cid4_crypto.manifest.json
openssl dgst -sha256 -sign cid4_crypto.demo.key.pem -out cid4_crypto.manifest.sig cid4_crypto.json
```

## GPG
```bash
gpg --armor --detach-sign cid4_crypto.json
gpg --encrypt --recipient demo@example.com cid4_crypto.json
```

## Age
```bash
age-keygen -o cid4-demo.agekey
age -r <recipient> -o cid4_crypto.manifest.json.age cid4_crypto.json
```

## Checksums
```bash
sha256sum data/COMPOUND_CID_4.json
md5 data/COMPOUND_CID_4.json
```

## Keytool
```bash
keytool -list -v -storetype PKCS12 -keystore data/out/crypto/cid4_crypto.demo.keystore.p12
keytool -importkeystore -srckeystore data/out/crypto/cid4_crypto.demo.keystore.p12 -srcstoretype PKCS12 -destkeystore cid4-demo.jks -deststoretype JKS
keytool -importcert -alias cid4-demo-ca -file <cert_path> -keystore cid4-demo-truststore.p12 -storetype PKCS12
```
