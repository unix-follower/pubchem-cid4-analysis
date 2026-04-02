package org.example.http

import org.apache.catalina.connector.Connector
import org.apache.catalina.startup.Tomcat
import org.apache.tomcat.util.net.SSLHostConfig
import org.apache.tomcat.util.net.SSLHostConfigCertificate
import org.slf4j.LoggerFactory

import java.nio.file.Files

object ApiServer:
  private val logger = LoggerFactory.getLogger(this.getClass)

  def startAndAwait(): Unit =
    val dataDir = ApiConfig.resolveDataDir()
    val tlsConfig = ApiConfig.loadTlsConfig(dataDir)
    val securityConfig = ApiConfig.loadSecurityConfig()
    val baseDir = Files.createTempDirectory("cid4-tomcat")
    val webRoot = Files.createDirectories(baseDir.resolve("webroot"))

    val tomcat = new Tomcat()
    tomcat.setBaseDir(baseDir.toString)
    tomcat.setHostname(tlsConfig.host)
    tomcat.setConnector(buildHttpsConnector(tlsConfig))

    val context = tomcat.addContext("", webRoot.toString)
    Tomcat.addServlet(context, "cid4-api", new ApiServlet(dataDir, new HttpSecurity(securityConfig)))
    context.addServletMappingDecoded("/api/*", "cid4-api")

    logger.info(
      s"Starting CID4 HTTPS API on https://${tlsConfig.host}:${tlsConfig.port} using ${tlsConfig.keystoreType} keystore ${tlsConfig.keystorePath} with auth mode ${securityConfig.auth.mode} and security config ${securityConfig.propertiesPath}"
    )
    if securityConfig.features.csrfEnabled then
      logger.warn(
        "CSRF verification guidance is enabled in config, but the current Tomcat API only serves GET and OPTIONS and does not enforce a CSRF token flow."
      )
    tomcat.start()
    logger.info("CID4 HTTPS API is ready")
    tomcat.getServer.await()

  private def buildHttpsConnector(tlsConfig: TlsConfig): Connector =
    val connector = new Connector("org.apache.coyote.http11.Http11NioProtocol")
    connector.setPort(tlsConfig.port)
    connector.setScheme("https")
    connector.setSecure(true)
    connector.setProperty("address", tlsConfig.host)
    connector.setProperty("SSLEnabled", "true")
    connector.setProperty("sslProtocol", "TLS")
    connector.setProperty("clientAuth", "false")
    connector.setProperty("keystoreFile", tlsConfig.keystorePath.toString)
    connector.setProperty("keystorePass", tlsConfig.keystorePassword)
    connector.setProperty("keystoreType", tlsConfig.keystoreType)
    connector.setProperty("certificateKeystoreFile", tlsConfig.keystorePath.toString)
    connector.setProperty("certificateKeystorePassword", tlsConfig.keystorePassword)
    connector.setProperty("certificateKeystoreType", tlsConfig.keystoreType)

    val sslHostConfig = new SSLHostConfig()
    sslHostConfig.setHostName("_default_")
    sslHostConfig.setSslProtocol("TLS")

    val certificate = new SSLHostConfigCertificate(
      sslHostConfig,
      SSLHostConfigCertificate.Type.UNDEFINED
    )
    certificate.setCertificateKeystoreFile(tlsConfig.keystorePath.toString)
    certificate.setCertificateKeystorePassword(tlsConfig.keystorePassword)
    certificate.setCertificateKeystoreType(tlsConfig.keystoreType)
    sslHostConfig.addCertificate(certificate)

    connector.addSslHostConfig(sslHostConfig)
    connector
