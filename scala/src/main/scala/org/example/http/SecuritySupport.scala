package org.example.http

import com.nimbusds.jose.JWSAlgorithm
import com.nimbusds.jose.crypto.ECDSAVerifier
import com.nimbusds.jose.crypto.RSASSAVerifier
import com.nimbusds.jose.jwk.ECKey
import com.nimbusds.jose.jwk.JWKSet
import com.nimbusds.jose.jwk.RSAKey
import com.nimbusds.jwt.SignedJWT
import jakarta.servlet.http.HttpServletRequest
import jakarta.servlet.http.HttpServletResponse
import org.slf4j.LoggerFactory

import java.net.InetAddress
import java.net.URI
import java.net.http.HttpClient
import java.net.http.HttpRequest
import java.net.http.HttpResponse
import java.nio.charset.StandardCharsets
import java.security.MessageDigest
import java.time.Duration
import java.time.Instant
import java.util.Base64
import java.util.Date
import scala.jdk.CollectionConverters.*
import scala.util.Try

enum AuthMode:
  case Disabled, OAuth2, Basic, Digest

final case class SecurityFeatures(
    corsEnabled: Boolean,
    xssHeadersEnabled: Boolean,
    csrfEnabled: Boolean,
    ssrfEnabled: Boolean
)

final case class CorsPolicy(
    allowedOrigins: Set[String],
    allowedMethods: Seq[String],
    allowedHeaders: Seq[String]
)

final case class OAuth2Settings(
    issuer: String,
    audience: Option[String],
    jwksUri: Option[String],
    realm: String
)

final case class BasicAuthSettings(realm: String, username: String, password: String)

final case class DigestAuthSettings(
    realm: String,
    username: String,
    password: String,
    nonceTtlSeconds: Int
)

final case class AuthSettings(
    mode: AuthMode,
    oauth2: Option[OAuth2Settings],
    basic: Option[BasicAuthSettings],
    digest: Option[DigestAuthSettings]
)

final case class SsrfPolicy(
    allowedSchemes: Set[String],
    allowedHosts: Set[String],
    allowedPorts: Set[Int],
    allowPrivateNetworks: Boolean
)

final case class SecurityConfig(
    propertiesPath: java.nio.file.Path,
    features: SecurityFeatures,
    cors: CorsPolicy,
    auth: AuthSettings,
    ssrf: SsrfPolicy
)

final case class AuthenticatedPrincipal(subject: String, mode: AuthMode)

final case class AuthFailure(
    statusCode: Int,
    payload: Map[String, String],
    challengeHeader: Option[String] = None
)

final class HttpSecurity(config: SecurityConfig):
  private val logger = LoggerFactory.getLogger(getClass)
  private lazy val oidcVerifier = config.auth.oauth2.map(OidcTokenVerifier(_))

  def applyResponseHeaders(request: HttpServletRequest, response: HttpServletResponse): Unit =
    applyCorsHeaders(request, response)
    applyXssHeaders(response)

  def authorize(request: HttpServletRequest): Either[AuthFailure, AuthenticatedPrincipal] =
    if request.getMethod == "OPTIONS" || ApiRoutes.isPublicPath(Option(request.getPathInfo).getOrElse("/")) then
      Right(AuthenticatedPrincipal("public", AuthMode.Disabled))
    else
      config.auth.mode match
        case AuthMode.Disabled => Right(AuthenticatedPrincipal("anonymous", AuthMode.Disabled))
        case AuthMode.OAuth2   => authorizeBearer(request)
        case AuthMode.Basic    => authorizeBasic(request)
        case AuthMode.Digest   => authorizeDigest(request)

  def challenge(response: HttpServletResponse, failure: AuthFailure): Unit =
    failure.challengeHeader.foreach(value => response.setHeader("WWW-Authenticate", value))

  private def applyCorsHeaders(request: HttpServletRequest, response: HttpServletResponse): Unit =
    if !config.features.corsEnabled then return

    Option(request.getHeader("Origin")).filter(_.nonEmpty).map(_.trim).foreach { origin =>
      val normalizedOrigin = origin.stripSuffix("/")
      response.addHeader("Vary", "Origin")
      if config.cors.allowedOrigins.contains(normalizedOrigin) then
        response.setHeader("Access-Control-Allow-Origin", normalizedOrigin)
        response.setHeader("Access-Control-Allow-Methods", config.cors.allowedMethods.mkString(", "))
        response.setHeader("Access-Control-Allow-Headers", config.cors.allowedHeaders.mkString(", "))
        if config.auth.mode != AuthMode.Disabled then
          response.setHeader("Access-Control-Allow-Credentials", "true")
    }

  private def applyXssHeaders(response: HttpServletResponse): Unit =
    if !config.features.xssHeadersEnabled then return

    response.setHeader(
      "Content-Security-Policy",
      "default-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    )
    response.setHeader("X-Content-Type-Options", "nosniff")
    response.setHeader("X-Frame-Options", "DENY")
    response.setHeader("Referrer-Policy", "no-referrer")

  private def authorizeBearer(request: HttpServletRequest): Either[AuthFailure, AuthenticatedPrincipal] =
    val challenge = Some(s"Bearer realm=\"${config.auth.oauth2.map(_.realm).getOrElse("CID4 API")}\"")
    extractBearerToken(request) match
      case None =>
        Left(AuthFailure(401, Map("message" -> "Bearer token required"), challenge))
      case Some(token) =>
        oidcVerifier.get.verify(token) match
          case Right(subject) => Right(AuthenticatedPrincipal(subject, AuthMode.OAuth2))
          case Left(error) =>
            Left(
              AuthFailure(
                401,
                Map("message" -> s"Invalid bearer token: $error"),
                Some(
                  s"Bearer realm=\"${config.auth.oauth2.map(_.realm).getOrElse("CID4 API")}\", error=\"invalid_token\""
                )
              )
            )

  private def authorizeBasic(request: HttpServletRequest): Either[AuthFailure, AuthenticatedPrincipal] =
    val settings = config.auth.basic.get
    val challenge = Some(s"Basic realm=\"${settings.realm}\"")
    Option(request.getHeader("Authorization")).filter(_.startsWith("Basic ")) match
      case None => Left(AuthFailure(401, Map("message" -> "Basic credentials required"), challenge))
      case Some(header) =>
        decodeBasicCredentials(header.stripPrefix("Basic ").trim) match
          case Some((username, password))
              if secureEquals(username, settings.username) && secureEquals(password, settings.password) =>
            Right(AuthenticatedPrincipal(username, AuthMode.Basic))
          case _ => Left(AuthFailure(401, Map("message" -> "Invalid basic credentials"), challenge))

  private def authorizeDigest(request: HttpServletRequest): Either[AuthFailure, AuthenticatedPrincipal] =
    val settings = config.auth.digest.get
    val challenge = Some(
      s"Digest realm=\"${settings.realm}\", qop=\"auth\", nonce=\"${newDigestNonce(settings)}\", algorithm=MD5"
    )
    Option(request.getHeader("Authorization")).filter(_.startsWith("Digest ")) match
      case None => Left(AuthFailure(401, Map("message" -> "Digest credentials required"), challenge))
      case Some(header) =>
        parseDigestHeader(header.stripPrefix("Digest ").trim) match
          case None => Left(AuthFailure(401, Map("message" -> "Malformed digest authorization header"), challenge))
          case Some(fields) =>
            validateDigest(fields, request.getMethod, settings) match
              case Right(subject) => Right(AuthenticatedPrincipal(subject, AuthMode.Digest))
              case Left(message)  => Left(AuthFailure(401, Map("message" -> message), challenge))

  private def extractBearerToken(request: HttpServletRequest): Option[String] =
    Option(request.getHeader("Authorization"))
      .filter(_.startsWith("Bearer "))
      .map(_.stripPrefix("Bearer ").trim)
      .filter(_.nonEmpty)

  private def decodeBasicCredentials(encoded: String): Option[(String, String)] =
    Try(Base64.getDecoder.decode(encoded)).toOption.flatMap { decodedBytes =>
      val decoded = String(decodedBytes, StandardCharsets.UTF_8)
      decoded.split(":", 2) match
        case Array(username, password) => Some(username -> password)
        case _                         => None
    }

  private def parseDigestHeader(header: String): Option[Map[String, String]] =
    val fields = header.split(",").iterator.flatMap { segment =>
      segment.split("=", 2) match
        case Array(key, value) =>
          val normalizedValue = value.trim.stripPrefix("\"").stripSuffix("\"")
          Some(key.trim -> normalizedValue)
        case _ => None
    }.toMap
    if fields.nonEmpty then Some(fields) else None

  private def validateDigest(
      fields: Map[String, String],
      method: String,
      settings: DigestAuthSettings
  ): Either[String, String] =
    val requiredKeys = Seq("username", "realm", "nonce", "uri", "response", "qop", "nc", "cnonce")
    if requiredKeys.exists(key => fields.get(key).forall(_.isBlank)) then
      Left("Missing digest authorization fields")
    else if !secureEquals(fields("username"), settings.username) || !secureEquals(fields("realm"), settings.realm) then
      Left("Digest credentials do not match the configured realm")
    else if !isValidDigestNonce(fields("nonce"), settings) then
      Left("Digest nonce is invalid or expired")
    else
      val ha1 = md5Hex(s"${settings.username}:${settings.realm}:${settings.password}")
      val ha2 = md5Hex(s"${method}:${fields("uri")}")
      val expected = md5Hex(
        s"$ha1:${fields("nonce")}:${fields("nc")}:${fields("cnonce")}:${fields("qop")}:$ha2"
      )
      if secureEquals(expected, fields("response")) then Right(settings.username)
      else Left("Digest response hash did not match")

  private def newDigestNonce(settings: DigestAuthSettings): String =
    val timestamp = Instant.now().getEpochSecond.toString
    val signature = sha256Hex(s"$timestamp:${settings.realm}:${settings.username}:${settings.password}")
    Base64.getUrlEncoder.withoutPadding().encodeToString(s"$timestamp:$signature".getBytes(StandardCharsets.UTF_8))

  private def isValidDigestNonce(nonce: String, settings: DigestAuthSettings): Boolean =
    Try(Base64.getUrlDecoder.decode(nonce)).toOption.flatMap { decodedBytes =>
      val decoded = String(decodedBytes, StandardCharsets.UTF_8)
      decoded.split(":", 2) match
        case Array(timestampText, signature) =>
          Try(timestampText.toLong).toOption.map { timestamp =>
            val ageSeconds = Instant.now().getEpochSecond - timestamp
            val expected = sha256Hex(s"$timestampText:${settings.realm}:${settings.username}:${settings.password}")
            ageSeconds >= 0 && ageSeconds <= settings.nonceTtlSeconds && secureEquals(expected, signature)
          }
        case _ => None
    }.getOrElse(false)

  private def secureEquals(left: String, right: String): Boolean =
    MessageDigest.isEqual(left.getBytes(StandardCharsets.UTF_8), right.getBytes(StandardCharsets.UTF_8))

  private def md5Hex(value: String): String = digestHex("MD5", value)

  private def sha256Hex(value: String): String = digestHex("SHA-256", value)

  private def digestHex(algorithm: String, value: String): String =
    MessageDigest.getInstance(algorithm).digest(value.getBytes(StandardCharsets.UTF_8)).map("%02x".format(_)).mkString

private final class OidcTokenVerifier(settings: OAuth2Settings):
  private val logger = LoggerFactory.getLogger(getClass)
  private val httpClient = HttpClient.newBuilder()
    .followRedirects(HttpClient.Redirect.NEVER)
    .connectTimeout(Duration.ofSeconds(5))
    .build()
  private lazy val discoveredJwksUri = settings.jwksUri.getOrElse(fetchDiscoveryJwksUri())
  @volatile private var cachedJwkSet: JWKSet = fetchJwkSet(discoveredJwksUri)

  def verify(token: String): Either[String, String] =
    try
      val jwt = SignedJWT.parse(token)
      val claims = jwt.getJWTClaimsSet
      val now = Date.from(Instant.now())

      if claims.getExpirationTime == null || claims.getExpirationTime.before(now) then
        Left("token is expired")
      else if claims.getNotBeforeTime != null && claims.getNotBeforeTime.after(now) then
        Left("token is not yet valid")
      else if claims.getIssuer != settings.issuer then
        Left(s"unexpected issuer ${claims.getIssuer}")
      else if settings.audience.exists(aud => !Option(claims.getAudience).map(_.asScala.contains(aud)).getOrElse(false))
      then
        Left("required audience is missing")
      else
        verifySignature(jwt).map(_ => Option(claims.getSubject).getOrElse("oidc-user"))
    catch
      case error: Exception =>
        logger.debug("OAuth2 token verification failed", error)
        Left(error.getMessage)

  private def verifySignature(jwt: SignedJWT): Either[String, Unit] =
    val keyId = Option(jwt.getHeader.getKeyID)
    val jwk = selectJwk(keyId).orElse {
      cachedJwkSet = fetchJwkSet(discoveredJwksUri)
      selectJwk(keyId)
    }

    jwk match
      case Some(rsaKey: RSAKey)
          if jwt.getHeader.getAlgorithm == JWSAlgorithm.RS256 || jwt.getHeader.getAlgorithm == JWSAlgorithm.RS384 || jwt.getHeader.getAlgorithm == JWSAlgorithm.RS512 =>
        if jwt.verify(new RSASSAVerifier(rsaKey.toRSAPublicKey)) then Right(())
        else Left("RSA signature verification failed")
      case Some(ecKey: ECKey) if jwt.getHeader.getAlgorithm.getName.startsWith("ES") =>
        if jwt.verify(new ECDSAVerifier(ecKey.toECPublicKey)) then Right(())
        else Left("EC signature verification failed")
      case Some(other) => Left(s"Unsupported JWK type ${other.getKeyType.getValue}")
      case None        => Left("No matching JWK found for token")

  private def selectJwk(keyId: Option[String]): Option[com.nimbusds.jose.jwk.JWK] =
    val keys = cachedJwkSet.getKeys.asScala.toSeq
    keyId match
      case Some(value) => keys.find(key => Option(key.getKeyID).contains(value)).orElse(keys.headOption)
      case None        => keys.headOption

  private def fetchDiscoveryJwksUri(): String =
    val metadataUri = URI.create(s"${settings.issuer.stripSuffix("/")}/.well-known/openid-configuration")
    val request = HttpRequest.newBuilder(metadataUri).GET().timeout(Duration.ofSeconds(5)).build()
    val response = httpClient.send(request, HttpResponse.BodyHandlers.ofString())
    if response.statusCode < 200 || response.statusCode >= 300 then
      throw new IllegalStateException(
        s"Failed to load OIDC discovery metadata. HTTP ${response.statusCode}: ${response.body}"
      )

    val root = JsonSupport.mapper.readTree(response.body)
    Option(root.path("jwks_uri").asText(null)).filter(_.nonEmpty).getOrElse {
      throw new IllegalStateException(s"OIDC discovery metadata at $metadataUri did not include jwks_uri")
    }

  private def fetchJwkSet(uri: String): JWKSet =
    val request = HttpRequest.newBuilder(URI.create(uri)).GET().timeout(Duration.ofSeconds(5)).build()
    val response = httpClient.send(request, HttpResponse.BodyHandlers.ofString())
    if response.statusCode < 200 || response.statusCode >= 300 then
      throw new IllegalStateException(s"Failed to load JWKS. HTTP ${response.statusCode}: ${response.body}")
    JWKSet.parse(response.body)

object OutboundUrlValidator:
  def validate(label: String, rawUrl: String, securityConfig: SecurityConfig): URI =
    val uri = URI.create(rawUrl.trim)
    if !securityConfig.features.ssrfEnabled then return uri

    val scheme = Option(uri.getScheme).map(_.toLowerCase).getOrElse {
      throw new IllegalArgumentException(s"$label URL must include an http or https scheme")
    }
    val host = Option(uri.getHost).map(_.toLowerCase).getOrElse {
      throw new IllegalArgumentException(s"$label URL must include a host")
    }
    val port =
      if uri.getPort >= 0 then uri.getPort
      else if scheme == "https" then 443
      else if scheme == "http" then 80
      else -1

    if uri.getUserInfo != null then
      throw new IllegalArgumentException(s"$label URL must not include user info")
    if uri.getFragment != null then
      throw new IllegalArgumentException(s"$label URL must not include a fragment")
    if !securityConfig.ssrf.allowedSchemes.contains(scheme) then
      throw new IllegalArgumentException(s"$label URL scheme '$scheme' is not allowed")
    if securityConfig.ssrf.allowedHosts.nonEmpty && !securityConfig.ssrf.allowedHosts.contains(host) then
      throw new IllegalArgumentException(s"$label host '$host' is not in the SSRF allowlist")
    if securityConfig.ssrf.allowedPorts.nonEmpty && !securityConfig.ssrf.allowedPorts.contains(port) then
      throw new IllegalArgumentException(s"$label port '$port' is not in the SSRF allowlist")
    if !securityConfig.ssrf.allowPrivateNetworks && !securityConfig.ssrf.allowedHosts.contains(host) then
      val addresses = InetAddress.getAllByName(host)
      if addresses.exists(isPrivateOrLocalAddress) then
        throw new IllegalArgumentException(s"$label host '$host' resolves to a private or local address")

    uri

  private def isPrivateOrLocalAddress(address: InetAddress): Boolean =
    address.isAnyLocalAddress ||
      address.isLoopbackAddress ||
      address.isLinkLocalAddress ||
      address.isSiteLocalAddress ||
      address.isMulticastAddress
