import io.gatling.core.Predef.*
import io.gatling.http.Predef.*

import scala.concurrent.duration.*

class CrowApiSimulation extends Simulation {
    private val baseUrl = System.getProperty("baseUrl", "https://127.0.0.1:8443")
    private val usersPerSecond = Integer.getInteger("usersPerSecond", 20).toDouble
    private val rampSeconds = Integer.getInteger("rampSeconds", 10)
    private val durationSeconds = Integer.getInteger("durationSeconds", 30)
    private val pauseMillis = Integer.getInteger("pauseMillis", 200)

    private val httpProtocol = http
        .baseUrl(baseUrl)
        .acceptHeader("application/json")
        .userAgentHeader("gatling-crow-load-test")
        .disableWarmUp

    private val mixedTraffic = scenario("CrowApiMixedTraffic")
        .forever {
            exec(
                http("health")
                    .get("/api/health")
                    .check(status.is(200))
            )
            .pause(pauseMillis.millis)
            .exec(
                http("conformer")
                    .get("/api/cid4/conformer/1")
                    .check(status.is(200))
            )
            .pause(pauseMillis.millis)
            .exec(
                http("structure2d")
                    .get("/api/cid4/structure/2d")
                    .check(status.is(200))
            )
            .pause(pauseMillis.millis)
            .exec(
                http("compound")
                    .get("/api/cid4/compound")
                    .check(status.is(200))
            )
            .pause(pauseMillis.millis)
            .exec(
                http("pathway")
                    .get("/api/algorithms/pathway")
                    .check(status.is(200))
            )
            .pause(pauseMillis.millis)
            .exec(
                http("bioactivity")
                    .get("/api/algorithms/bioactivity")
                    .check(status.is(200))
            )
            .pause(pauseMillis.millis)
            .exec(
                http("taxonomy")
                    .get("/api/algorithms/taxonomy")
                    .check(status.is(200))
            )
            .pause(pauseMillis.millis)
        }

    setUp(
        mixedTraffic.inject(
            rampUsersPerSec(1.0).to(usersPerSecond).during(rampSeconds.seconds),
            constantUsersPerSec(usersPerSecond).during(durationSeconds.seconds)
        )
    ).protocols(httpProtocol)
}
