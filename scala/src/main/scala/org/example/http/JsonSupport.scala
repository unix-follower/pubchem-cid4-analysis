package org.example.http

import tools.jackson.databind.json.JsonMapper
import tools.jackson.module.scala.DefaultScalaModule

object JsonSupport:
  val mapper: JsonMapper = JsonMapper.builder()
    .addModule(DefaultScalaModule())
    .build()

  def toJsonBytes(payload: Any): Array[Byte] =
    mapper.writeValueAsBytes(payload)
