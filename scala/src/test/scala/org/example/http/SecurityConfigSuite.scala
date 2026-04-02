package org.example.http

import munit.FunSuite

import java.nio.file.Files

class SecurityConfigSuite extends FunSuite:
  test("security config rejects multiple auth modes") {
    val configPath = Files.createTempFile("cid4-security", ".properties")
    Files.writeString(
      configPath,
      """security.auth.oauth2.enabled=true
        |security.auth.oauth2.issuer=https://kc.example.test/realms/cid4
        |security.auth.basic.enabled=true
        |security.auth.basic.username=demo
        |security.auth.basic.password=demo
        |""".stripMargin
    )

    intercept[IllegalStateException] {
      ApiConfig.loadSecurityConfig(configPath)
    }
  }

  test("security config loads basic mode from properties file") {
    val configPath = Files.createTempFile("cid4-security", ".properties")
    Files.writeString(
      configPath,
      """security.cors.enabled=true
        |security.cors.allowedOrigins=https://ui.example.test
        |security.xssHeaders.enabled=true
        |security.auth.basic.enabled=true
        |security.auth.basic.realm=Demo Realm
        |security.auth.basic.username=demo
        |security.auth.basic.password=secret
        |""".stripMargin
    )

    val config = ApiConfig.loadSecurityConfig(configPath)

    assertEquals(config.features.corsEnabled, true)
    assertEquals(config.features.xssHeadersEnabled, true)
    assertEquals(config.cors.allowedOrigins, Set("https://ui.example.test"))
    assertEquals(config.auth.mode, AuthMode.Basic)
    assertEquals(config.auth.basic.map(_.realm), Some("Demo Realm"))
  }

  test("ssrf validator rejects loopback hosts when allowlist protection is enabled") {
    val config = SecurityConfig(
      propertiesPath = Files.createTempFile("cid4-security", ".properties"),
      features = SecurityFeatures(false, false, false, true),
      cors = CorsPolicy(Set.empty, Seq("GET", "OPTIONS"), Seq("Authorization", "Content-Type")),
      auth = AuthSettings(AuthMode.Disabled, None, None, None),
      ssrf = SsrfPolicy(Set("http", "https"), Set.empty, Set.empty, allowPrivateNetworks = false)
    )

    intercept[IllegalArgumentException] {
      OutboundUrlValidator.validate("Elasticsearch", "http://127.0.0.1:9200", config)
    }
  }

  test("ssrf validator accepts allowlisted hosts") {
    val config = SecurityConfig(
      propertiesPath = Files.createTempFile("cid4-security", ".properties"),
      features = SecurityFeatures(false, false, false, true),
      cors = CorsPolicy(Set.empty, Seq("GET", "OPTIONS"), Seq("Authorization", "Content-Type")),
      auth = AuthSettings(AuthMode.Disabled, None, None, None),
      ssrf = SsrfPolicy(Set("http", "https"), Set("127.0.0.1"), Set(9200), allowPrivateNetworks = false)
    )

    val uri = OutboundUrlValidator.validate("Elasticsearch", "http://127.0.0.1:9200", config)

    assertEquals(uri.getHost, "127.0.0.1")
    assertEquals(uri.getPort, 9200)
  }
