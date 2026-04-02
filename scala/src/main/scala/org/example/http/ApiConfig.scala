package org.example.http

import java.io.InputStream
import java.io.Reader
import java.nio.file.Files
import java.nio.file.Path
import java.security.KeyStore
import java.util.Properties
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
  private val DefaultSecurityConfigPath = Path.of("conf", "security.properties").toAbsolutePath.normalize()
  private val DefaultHostEnvNames = Seq("SERVER_HOST")
  private val DefaultPortEnvNames = Seq("SERVER_PORT", "PORT")
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
    loadTlsConfig(dataDir, DefaultHostEnvNames, DefaultPortEnvNames)

  def loadTlsConfig(
      dataDir: Path,
      hostEnvNames: Seq[String],
      portEnvNames: Seq[String]
  ): TlsConfig =
    val host = firstEnvValue(hostEnvNames).getOrElse("0.0.0.0")
    val port = firstParsedIntEnv(portEnvNames).getOrElse(8443)
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

  def loadSecurityConfig(): SecurityConfig =
    loadSecurityConfig(resolveSecurityConfigPath())

  def loadSecurityConfig(configPath: Path): SecurityConfig =
    val properties = new Properties()
    if Files.isRegularFile(configPath) then
      val reader: Reader = Files.newBufferedReader(configPath)
      try properties.load(reader)
      finally reader.close()

    val features = SecurityFeatures(
      corsEnabled = propertyBoolean(properties, "security.cors.enabled", default = false),
      xssHeadersEnabled = propertyBoolean(properties, "security.xssHeaders.enabled", default = false),
      csrfEnabled = propertyBoolean(properties, "security.csrf.enabled", default = false),
      ssrfEnabled = propertyBoolean(properties, "security.ssrf.enabled", default = false)
    )

    val cors = CorsPolicy(
      allowedOrigins = propertyCsv(properties, "security.cors.allowedOrigins").map(_.stripSuffix("/")).toSet,
      allowedMethods = propertyCsv(properties, "security.cors.allowedMethods", Seq("GET", "OPTIONS")),
      allowedHeaders = propertyCsv(properties, "security.cors.allowedHeaders", Seq("Authorization", "Content-Type"))
    )

    val oauth2Enabled = propertyBoolean(properties, "security.auth.oauth2.enabled", default = false)
    val basicEnabled = propertyBoolean(properties, "security.auth.basic.enabled", default = false)
    val digestEnabled = propertyBoolean(properties, "security.auth.digest.enabled", default = false)
    val enabledModes = Seq(oauth2Enabled, basicEnabled, digestEnabled).count(identity)
    if enabledModes > 1 then
      throw new IllegalStateException(
        s"Security config $configPath enables multiple auth modes. Enable at most one of OAuth2, Basic, or Digest."
      )

    val oauth2 =
      if oauth2Enabled then
        val issuer = propertyValue(properties, "security.auth.oauth2.issuer").getOrElse {
          throw new IllegalStateException("OAuth2 is enabled but security.auth.oauth2.issuer is missing")
        }
        Some(
          OAuth2Settings(
            issuer = issuer,
            audience = propertyValue(properties, "security.auth.oauth2.audience"),
            jwksUri = propertyValue(properties, "security.auth.oauth2.jwksUri"),
            realm = propertyValue(properties, "security.auth.oauth2.realm").getOrElse("CID4 API")
          )
        )
      else None

    val basic =
      if basicEnabled then
        Some(
          BasicAuthSettings(
            realm = propertyValue(properties, "security.auth.basic.realm").getOrElse("CID4 Basic Realm"),
            username = propertyValue(properties, "security.auth.basic.username")
              .orElse(envValue("BASIC_AUTH_USERNAME"))
              .getOrElse(throw new IllegalStateException("Basic auth is enabled but no username is configured")),
            password = propertyValue(properties, "security.auth.basic.password")
              .orElse(envValue("BASIC_AUTH_PASSWORD"))
              .getOrElse(throw new IllegalStateException("Basic auth is enabled but no password is configured"))
          )
        )
      else None

    val digest =
      if digestEnabled then
        Some(
          DigestAuthSettings(
            realm = propertyValue(properties, "security.auth.digest.realm").getOrElse("CID4 Digest Realm"),
            username = propertyValue(properties, "security.auth.digest.username")
              .orElse(envValue("DIGEST_AUTH_USERNAME"))
              .getOrElse(throw new IllegalStateException("Digest auth is enabled but no username is configured")),
            password = propertyValue(properties, "security.auth.digest.password")
              .orElse(envValue("DIGEST_AUTH_PASSWORD"))
              .getOrElse(throw new IllegalStateException("Digest auth is enabled but no password is configured")),
            nonceTtlSeconds = propertyInt(properties, "security.auth.digest.nonceTtlSeconds", 300)
          )
        )
      else None

    val authMode =
      if oauth2Enabled then AuthMode.OAuth2
      else if basicEnabled then AuthMode.Basic
      else if digestEnabled then AuthMode.Digest
      else AuthMode.Disabled

    val ssrf = SsrfPolicy(
      allowedSchemes =
        propertyCsv(properties, "security.ssrf.allowedSchemes", Seq("http", "https")).map(_.toLowerCase).toSet,
      allowedHosts = propertyCsv(properties, "security.ssrf.allowedHosts").map(_.toLowerCase).toSet,
      allowedPorts =
        propertyCsv(properties, "security.ssrf.allowedPorts").flatMap(value => Try(value.toInt).toOption).toSet,
      allowPrivateNetworks = propertyBoolean(properties, "security.ssrf.allowPrivateNetworks", default = false)
    )

    SecurityConfig(
      propertiesPath = configPath,
      features = features,
      cors = cors,
      auth = AuthSettings(authMode, oauth2, basic, digest),
      ssrf = ssrf
    )

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

  private def firstEnvValue(names: Seq[String]): Option[String] =
    names.iterator
      .flatMap(name => Option(System.getenv(name)).filter(_.nonEmpty))
      .toSeq
      .headOption

  private def firstParsedIntEnv(names: Seq[String]): Option[Int] =
    names.iterator.flatMap(parseIntEnv).toSeq.headOption

  private def resolveSecurityConfigPath(): Path =
    envValue("SECURITY_CONFIG_PATH")
      .map(path => Path.of(path).toAbsolutePath.normalize())
      .getOrElse(DefaultSecurityConfigPath)

  private def envValue(name: String): Option[String] =
    Option(System.getenv(name)).map(_.trim).filter(_.nonEmpty)

  private def propertyValue(properties: Properties, key: String): Option[String] =
    Option(properties.getProperty(key)).map(_.trim).filter(_.nonEmpty)

  private def propertyBoolean(properties: Properties, key: String, default: Boolean): Boolean =
    propertyValue(properties, key).map(_.toBooleanOption.getOrElse(default)).getOrElse(default)

  private def propertyInt(properties: Properties, key: String, default: Int): Int =
    propertyValue(properties, key).flatMap(value => Try(value.toInt).toOption).getOrElse(default)

  private def propertyCsv(properties: Properties, key: String, default: Seq[String] = Seq.empty): Seq[String] =
    propertyValue(properties, key)
      .map(_.split(',').toSeq.map(_.trim).filter(_.nonEmpty))
      .getOrElse(default)
