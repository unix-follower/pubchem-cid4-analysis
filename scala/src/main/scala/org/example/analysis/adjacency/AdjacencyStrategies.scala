package org.example.analysis.adjacency

import com.google.common.graph.ValueGraphBuilder
import org.apache.tinkerpop.gremlin.structure.T
import org.apache.tinkerpop.gremlin.tinkergraph.structure.TinkerGraph
import org.jgrapht.graph.DefaultWeightedEdge
import org.jgrapht.graph.SimpleWeightedGraph
import scalax.collection.edges.UnDiEdge
import scalax.collection.immutable.Graph

import scala.jdk.CollectionConverters.*

trait AdjacencyMatrixStrategy:
  def method: AdjacencyMethod

  def build(input: NormalizedAdjacencyInput): AdjacencyMatrix

object AdjacencyMatrixStrategy:
  private val implementations = Vector[AdjacencyMatrixStrategy](
    ArraysAdjacencyMatrixStrategy,
    GuavaAdjacencyMatrixStrategy,
    TinkerPopAdjacencyMatrixStrategy,
    JGraphTAdjacencyMatrixStrategy,
    ScalaGraphAdjacencyMatrixStrategy
  ).map(strategy => strategy.method -> strategy).toMap

  def resolve(method: String): AdjacencyMatrixStrategy =
    AdjacencyMethod.parse(method) match
      case Right(value)       => implementations(value)
      case Left(errorMessage) => throw IllegalArgumentException(errorMessage)

object ArraysAdjacencyMatrixStrategy extends AdjacencyMatrixStrategy:
  override val method: AdjacencyMethod = AdjacencyMethod.Arrays

  override def build(input: NormalizedAdjacencyInput): AdjacencyMatrix =
    val matrix = MatrixOps.empty(input.size)
    input.bonds.foreach { bond =>
      MatrixOps.assignSymmetric(matrix, bond.sourceIndex, bond.targetIndex, bond.weight)
    }
    MatrixOps.freeze(input, matrix, method)

object GuavaAdjacencyMatrixStrategy extends AdjacencyMatrixStrategy:
  override val method: AdjacencyMethod = AdjacencyMethod.Guava

  override def build(input: NormalizedAdjacencyInput): AdjacencyMatrix =
    val graph = ValueGraphBuilder.undirected().allowsSelfLoops(false).build[Int, Int]()
    input.atomIds.indices.foreach(graph.addNode)
    input.bonds.foreach { bond =>
      graph.putEdgeValue(bond.sourceIndex, bond.targetIndex, bond.weight)
    }

    val matrix =
      Array.tabulate(input.size, input.size)((rowIndex, columnIndex) =>
        graph.edgeValueOrDefault(rowIndex, columnIndex, 0)
      )
    MatrixOps.freeze(input, matrix, method)

object TinkerPopAdjacencyMatrixStrategy extends AdjacencyMatrixStrategy:
  override val method: AdjacencyMethod = AdjacencyMethod.TinkerPop

  override def build(input: NormalizedAdjacencyInput): AdjacencyMatrix =
    val graph = TinkerGraph.open()
    try
      val vertices = input.atomIds.indices.map { index =>
        index -> graph.addVertex(T.id, Int.box(index), "atomId", Int.box(input.atomIds(index)))
      }.toMap

      input.bonds.zipWithIndex.foreach { case (bond, edgeIndex) =>
        vertices(bond.sourceIndex).addEdge(
          "bond",
          vertices(bond.targetIndex),
          T.id,
          s"bond-$edgeIndex",
          "weight",
          Int.box(bond.weight)
        )
      }

      val matrix = MatrixOps.empty(input.size)
      graph.edges().asScala.foreach { edge =>
        val sourceIndex = edge.outVertex().id().asInstanceOf[Integer].intValue()
        val targetIndex = edge.inVertex().id().asInstanceOf[Integer].intValue()
        val weight = edge.property[Integer]("weight").value().intValue()
        MatrixOps.assignSymmetric(matrix, sourceIndex, targetIndex, weight)
      }

      MatrixOps.freeze(input, matrix, method)
    finally
      graph.close()

object JGraphTAdjacencyMatrixStrategy extends AdjacencyMatrixStrategy:
  override val method: AdjacencyMethod = AdjacencyMethod.JGraphT

  override def build(input: NormalizedAdjacencyInput): AdjacencyMatrix =
    val graph = new SimpleWeightedGraph[Int, DefaultWeightedEdge](classOf[DefaultWeightedEdge])
    input.atomIds.indices.foreach(graph.addVertex)

    input.bonds.foreach { bond =>
      val edge = Option(graph.addEdge(bond.sourceIndex, bond.targetIndex)).getOrElse(
        graph.getEdge(bond.sourceIndex, bond.targetIndex)
      )
      graph.setEdgeWeight(edge, bond.weight.toDouble)
    }

    val matrix = MatrixOps.empty(input.size)
    graph.edgeSet().asScala.foreach { edge =>
      val sourceIndex = graph.getEdgeSource(edge)
      val targetIndex = graph.getEdgeTarget(edge)
      val weight = graph.getEdgeWeight(edge).toInt
      MatrixOps.assignSymmetric(matrix, sourceIndex, targetIndex, weight)
    }

    MatrixOps.freeze(input, matrix, method)

object ScalaGraphAdjacencyMatrixStrategy extends AdjacencyMatrixStrategy:
  override val method: AdjacencyMethod = AdjacencyMethod.ScalaGraph

  override def build(input: NormalizedAdjacencyInput): AdjacencyMatrix =
    Graph.from(
      input.atomIds.indices,
      input.bonds.map(bond => UnDiEdge(bond.sourceIndex, bond.targetIndex))
    )

    val matrix = MatrixOps.empty(input.size)
    input.bonds.foreach { bond =>
      MatrixOps.assignSymmetric(matrix, bond.sourceIndex, bond.targetIndex, bond.weight)
    }

    MatrixOps.freeze(input, matrix, method)
