from __future__ import annotations

import base64
import datetime as dt
import importlib
from pathlib import Path
from typing import Any


def certificate_dependencies_available() -> bool:
    return importlib.util.find_spec("cryptography") is not None


def build_certificate_examples(output_directory: Path, password: str) -> dict[str, Any]:
    if not certificate_dependencies_available():
        return {
            "status": "skipped",
            "reason": "Install the optional crypto extra to enable X.509 and PKCS#12 examples.",
        }

    from cryptography import x509  # type: ignore[import-not-found]
    from cryptography.hazmat.primitives import hashes, serialization  # type: ignore[import-not-found]
    from cryptography.hazmat.primitives.asymmetric import rsa  # type: ignore[import-not-found]
    from cryptography.hazmat.primitives.serialization import pkcs12  # type: ignore[import-not-found]
    from cryptography.x509.oid import NameOID  # type: ignore[import-not-found]

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=3072)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pubchem-cid4-analysis"),
            x509.NameAttribute(NameOID.COMMON_NAME, "cid4.local"),
        ]
    )
    now = dt.datetime.now(dt.UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(private_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(days=1))
        .not_valid_after(now + dt.timedelta(days=365))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("cid4.local"), x509.DNSName("localhost")]),
            critical=False,
        )
        .sign(private_key, hashes.SHA256())
    )

    key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode("utf-8")),
    )
    cert_pem = certificate.public_bytes(serialization.Encoding.PEM)
    pkcs12_bundle = pkcs12.serialize_key_and_certificates(
        name=b"cid4-demo",
        key=private_key,
        cert=certificate,
        cas=None,
        encryption_algorithm=serialization.BestAvailableEncryption(password.encode("utf-8")),
    )

    key_path = output_directory / "cid4_crypto.demo.key.pem"
    cert_path = output_directory / "cid4_crypto.demo.cert.pem"
    p12_path = output_directory / "cid4_crypto.demo.keystore.p12"
    key_path.write_bytes(key_pem)
    cert_path.write_bytes(cert_pem)
    p12_path.write_bytes(pkcs12_bundle)

    loaded_key, loaded_cert, loaded_chain = pkcs12.load_key_and_certificates(
        pkcs12_bundle,
        password.encode("utf-8"),
    )

    return {
        "status": "ok",
        "subject_rfc4514": certificate.subject.rfc4514_string(),
        "issuer_rfc4514": certificate.issuer.rfc4514_string(),
        "serial_number": str(certificate.serial_number),
        "signature_hash_algorithm": certificate.signature_hash_algorithm.name,
        "pem_paths": {
            "private_key": str(key_path),
            "certificate": str(cert_path),
        },
        "pkcs12": {
            "path": str(p12_path),
            "size_bytes": len(pkcs12_bundle),
            "loaded_cert_subject": loaded_cert.subject.rfc4514_string() if loaded_cert is not None else None,
            "loaded_chain_length": 0 if loaded_chain is None else len(loaded_chain),
            "password_hint": "Use the demo password recorded in the runner summary for local-only examples.",
        },
        "keytool_examples": [
            f"keytool -list -v -storetype PKCS12 -keystore {p12_path.name}",
            f"keytool -importkeystore -srckeystore {p12_path.name} -srcstoretype PKCS12 "
            f"-destkeystore cid4-demo.jks -deststoretype JKS",
            f"keytool -importcert -alias cid4-demo-ca -file {cert_path.name} "
            f"-keystore cid4-demo-truststore.p12 -storetype PKCS12",
        ],
        "openssl_examples": [
            f"openssl pkcs12 -info -in {p12_path.name} -nokeys",
            f"openssl x509 -in {cert_path.name} -text -noout",
        ],
        "pkcs12_b64_prefix": base64.b64encode(pkcs12_bundle[:24]).decode("ascii"),
        "private_key_loaded": loaded_key is not None,
    }
