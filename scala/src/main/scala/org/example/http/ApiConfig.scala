package org.example.http

import java.io.InputStream
import java.nio.file.Files
import java.nio.file.Path
import java.security.KeyStore
import javax.net.ssl.KeyManagerFactory
import scala.util.Try

final case class TlsConfig(
    host: String,
    port: Int,
    keystorePath: Path,
    keystorePassword: String,
    keystoreType: String
)

object ApiConfig:
  private val RequiredDataFiles = Seq(
    "COMPOUND_CID_4.json",
    "Structure2D_COMPOUND_CID_4.json",
    "Conformer3D_COMPOUND_CID_4(1).json"
  )

  def resolveDataDir(): Path =
    val cwd = Path.of("").toAbsolutePath.normalize()
    val envCandidates = Option(System.getenv("DATA_DIR"))
      .filter(_.nonEmpty)
      .map(path => Path.of(path).toAbsolutePath.normalize())
      .toSeq
    val candidates = envCandidates ++ Seq(
      cwd.resolve("data").normalize(),
      cwd.resolve("../data").normalize(),
      cwd.resolve("../../data").normalize()
    )

    candidates.find(isDataDir).getOrElse {
      throw new IllegalStateException(
        s"Unable to resolve DATA_DIR. Checked: ${candidates.map(_.toString).mkString(", ")}"
      )
    }

  def loadTlsConfig(dataDir: Path): TlsConfig =
    val host = Option(System.getenv("SERVER_HOST")).filter(_.nonEmpty).getOrElse("0.0.0.0")
    val port = parseIntEnv("SERVER_PORT").orElse(parseIntEnv("PORT")).getOrElse(8443)
    val keystoreType = Option(System.getenv("KEYSTORE_TYPE")).filter(_.nonEmpty).getOrElse("PKCS12")

    val config =
      (
        Option(System.getenv("KEYSTORE_PATH")).filter(_.nonEmpty),
        Option(System.getenv("KEYSTORE_PASSWORD")).filter(_.nonEmpty)
      ) match
        case (Some(path), Some(password)) =>
          TlsConfig(host, port, Path.of(path).toAbsolutePath.normalize(), password, keystoreType)
        case (Some(_), None) | (None, Some(_)) =>
          throw new IllegalStateException(
            "Set both KEYSTORE_PATH and KEYSTORE_PASSWORD, or neither to use the crypto summary fallback."
          )
        case _ =>
          loadTlsConfigFromCryptoSummary(dataDir, host, port, keystoreType).getOrElse {
            throw new IllegalStateException(
              s"No TLS keystore configured. Set KEYSTORE_PATH and KEYSTORE_PASSWORD, or generate ${dataDir.resolve("out/crypto/cid4_crypto.summary.json")} first."
            )
          }

    if !Files.isRegularFile(config.keystorePath) then
      throw new IllegalStateException(s"TLS keystore does not exist: ${config.keystorePath}")

    config

  def buildKeyManagerFactory(tlsConfig: TlsConfig): KeyManagerFactory =
    val keyStore = KeyStore.getInstance(tlsConfig.keystoreType)
    val stream: InputStream = Files.newInputStream(tlsConfig.keystorePath)
    try
      keyStore.load(stream, tlsConfig.keystorePassword.toCharArray)
    finally
      stream.close()

    val keyManagerFactory = KeyManagerFactory.getInstance(KeyManagerFactory.getDefaultAlgorithm)
    keyManagerFactory.init(keyStore, tlsConfig.keystorePassword.toCharArray)
    keyManagerFactory

  private def isDataDir(path: Path): Boolean =
    Files.isDirectory(path) && RequiredDataFiles.forall(fileName => Files.isRegularFile(path.resolve(fileName)))

  private def loadTlsConfigFromCryptoSummary(
      dataDir: Path,
      host: String,
      port: Int,
      keystoreType: String
  ): Option[TlsConfig] =
    val summaryPath = dataDir.resolve("out/crypto/cid4_crypto.summary.json").normalize()
    if !Files.isRegularFile(summaryPath) then
      None
    else
      val root = JsonSupport.mapper.readTree(summaryPath.toFile)
      val keystorePath = Option(root.path("x509_and_pkcs12").path("pkcs12").path("path").asText(null))
        .filter(_.nonEmpty)
        .map(path => Path.of(path).toAbsolutePath.normalize())
      val password = Option(root.path("demo_password").asText(null)).filter(_.nonEmpty)
      for
        path <- keystorePath
        secret <- password
      yield TlsConfig(host, port, path, secret, keystoreType)

  private def parseIntEnv(name: String): Option[Int] =
    Option(System.getenv(name))
      .filter(_.nonEmpty)
      .flatMap(value => Try(value.toInt).toOption)
      .filter(_ > 0)
