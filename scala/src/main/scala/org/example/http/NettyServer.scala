package org.example.http

import io.netty.bootstrap.ServerBootstrap
import io.netty.buffer.Unpooled
import io.netty.channel.ChannelFutureListener
import io.netty.channel.ChannelHandlerContext
import io.netty.channel.ChannelInitializer
import io.netty.channel.ChannelOption
import io.netty.channel.SimpleChannelInboundHandler
import io.netty.channel.nio.NioEventLoopGroup
import io.netty.channel.socket.SocketChannel
import io.netty.channel.socket.nio.NioServerSocketChannel
import io.netty.handler.codec.http.DefaultFullHttpResponse
import io.netty.handler.codec.http.FullHttpRequest
import io.netty.handler.codec.http.FullHttpResponse
import io.netty.handler.codec.http.HttpHeaderNames
import io.netty.handler.codec.http.HttpHeaderValues
import io.netty.handler.codec.http.HttpObjectAggregator
import io.netty.handler.codec.http.HttpResponseStatus
import io.netty.handler.codec.http.HttpServerCodec
import io.netty.handler.codec.http.HttpUtil
import io.netty.handler.codec.http.HttpVersion
import io.netty.handler.codec.http.QueryStringDecoder
import io.netty.handler.ssl.SslContext
import io.netty.handler.ssl.SslContextBuilder
import io.netty.handler.ssl.SslProvider
import org.slf4j.LoggerFactory

import java.nio.file.Files
import java.nio.file.Path
import scala.jdk.CollectionConverters.*

object NettyServer:
  private val logger = LoggerFactory.getLogger(this.getClass)

  def startAndAwait(): Unit =
    val dataDir = ApiConfig.resolveDataDir()
    val tlsConfig = ApiConfig.loadTlsConfig(dataDir)
    val sslContext = buildSslContext(tlsConfig)
    val bossGroup = new NioEventLoopGroup(1)
    val workerGroup = new NioEventLoopGroup()

    try
      val bootstrap = new ServerBootstrap()
        .group(bossGroup, workerGroup)
        .channel(classOf[NioServerSocketChannel])
        .option(ChannelOption.SO_BACKLOG, Integer.valueOf(128))
        .childOption(ChannelOption.SO_KEEPALIVE, java.lang.Boolean.TRUE)
        .childHandler(new ChannelInitializer[SocketChannel]:
          override def initChannel(channel: SocketChannel): Unit =
            val pipeline = channel.pipeline()
            pipeline.addLast(sslContext.newHandler(channel.alloc()))
            pipeline.addLast(new HttpServerCodec())
            pipeline.addLast(new HttpObjectAggregator(1024 * 1024))
            pipeline.addLast(new NettyApiHandler(dataDir)))

      logger.info(
        s"Starting CID4 Netty HTTPS API on https://${tlsConfig.host}:${tlsConfig.port} using ${tlsConfig.keystoreType} keystore ${tlsConfig.keystorePath}"
      )
      val channel = bootstrap.bind(tlsConfig.host, tlsConfig.port).sync().channel()
      logger.info("CID4 Netty HTTPS API is ready")
      channel.closeFuture().sync()
    finally
      bossGroup.shutdownGracefully().syncUninterruptibly()
      workerGroup.shutdownGracefully().syncUninterruptibly()

  private def buildSslContext(tlsConfig: TlsConfig): SslContext =
    val keyManagerFactory = ApiConfig.buildKeyManagerFactory(tlsConfig)
    SslContextBuilder
      .forServer(keyManagerFactory)
      .sslProvider(SslProvider.JDK)
      .protocols("TLSv1.2", "TLSv1.3")
      .build()

  private final class NettyApiHandler(dataDir: Path) extends SimpleChannelInboundHandler[FullHttpRequest]:
    override def channelRead0(context: ChannelHandlerContext, request: FullHttpRequest): Unit =
      val decoder = new QueryStringDecoder(request.uri())
      val query = decoder.parameters().asScala.iterator.collect {
        case (key, values) if values != null && !values.isEmpty => key -> values.get(0)
      }.toMap
      val result = ApiRoutes.route(
        method = request.method().name(),
        rawPath = decoder.path(),
        query = query,
        dataDir = dataDir,
        sourceLabel = "scala-netty"
      )
      writeResponse(context, request, result)

    override def exceptionCaught(context: ChannelHandlerContext, cause: Throwable): Unit =
      logger.error("Netty API request failed", cause)
      context.close()

    private def writeResponse(
        context: ChannelHandlerContext,
        request: FullHttpRequest,
        result: ApiRoutes.RouteResult
    ): Unit =
      val status = HttpResponseStatus.valueOf(result.statusCode)
      val body = result match
        case ApiRoutes.JsonResult(_, payload) => JsonSupport.toJsonBytes(payload)
        case ApiRoutes.FileResult(_, path)    => Files.readAllBytes(path)
        case ApiRoutes.EmptyResult(_)         => Array.emptyByteArray

      val response: FullHttpResponse = new DefaultFullHttpResponse(
        HttpVersion.HTTP_1_1,
        status,
        Unpooled.wrappedBuffer(body)
      )

      ApiRoutes.corsHeaders.foreach((name, value) => response.headers().set(name, value))
      response.headers().set(HttpHeaderNames.CONTENT_LENGTH, Integer.valueOf(body.length))
      if result.isInstanceOf[ApiRoutes.EmptyResult] then
        response.headers().set(HttpHeaderNames.CONTENT_TYPE, HttpHeaderValues.TEXT_PLAIN)
      else
        response.headers().set(HttpHeaderNames.CONTENT_TYPE, HttpHeaderValues.APPLICATION_JSON)

      val keepAlive = HttpUtil.isKeepAlive(request)
      if keepAlive then
        response.headers().set(HttpHeaderNames.CONNECTION, HttpHeaderValues.KEEP_ALIVE)
        context.writeAndFlush(response)
      else
        context.writeAndFlush(response).addListener(ChannelFutureListener.CLOSE)
