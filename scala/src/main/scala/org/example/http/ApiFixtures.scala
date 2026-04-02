package org.example.http

final case class MockHealthResponse(message: String, source: String, timestamp: String)
final case class BioactivityRecord(aid: Int, assay: String, activityValue: Double)
final case class BioactivityResponse(records: Seq[BioactivityRecord])
final case class TaxonomyRecord(taxonomyId: Int, sourceOrganism: String)
final case class TaxonomyResponse(organisms: Seq[TaxonomyRecord])
final case class PathwayNode(id: String, label: String)
final case class PathwayEdge(id: String, source: String, target: String)
final case class PathwayGraph(
    id: String,
    title: String,
    directed: Boolean,
    nodes: Seq[PathwayNode],
    edges: Seq[PathwayEdge]
)
final case class PathwayResponse(graph: PathwayGraph)

object ApiFixtures:
  val bioactivity: BioactivityResponse = BioactivityResponse(
    records = Seq(
      BioactivityRecord(743069, "Tox21 ER-alpha agonist", 355.1),
      BioactivityRecord(743070, "Tox21 ER-alpha antagonist", 18.2),
      BioactivityRecord(651820, "NCI growth inhibition", 92.4),
      BioactivityRecord(540317, "Cell viability counter-screen", 112.7),
      BioactivityRecord(504332, "ChEMBL potency panel", 8.6),
      BioactivityRecord(720699, "Nuclear receptor confirmation", 61.9),
      BioactivityRecord(743053, "Tox21 luciferase artifact", 140.4),
      BioactivityRecord(743122, "Dose-response validation", 28.8),
      BioactivityRecord(1259368, "Secondary pharmacology", 4.2),
      BioactivityRecord(1345073, "Metabolism pathway screen", 205.5)
    )
  )

  val taxonomy: TaxonomyResponse = TaxonomyResponse(
    organisms = Seq(
      TaxonomyRecord(9913, "Bos taurus"),
      TaxonomyRecord(9913, "Bos taurus"),
      TaxonomyRecord(9823, "Sus scrofa"),
      TaxonomyRecord(9031, "Gallus gallus"),
      TaxonomyRecord(9031, "Gallus gallus"),
      TaxonomyRecord(9103, "Meleagris gallopavo"),
      TaxonomyRecord(9986, "Oryctolagus cuniculus"),
      TaxonomyRecord(9685, "Felis catus")
    )
  )

  val pathway: PathwayResponse = PathwayResponse(
    graph = PathwayGraph(
      id = "glutathione-metabolism-iii",
      title = "Glutathione Metabolism III",
      directed = true,
      nodes = Seq(
        PathwayNode("step-1", "Import precursor"),
        PathwayNode("step-2", "Activate cysteine"),
        PathwayNode("step-3", "Ligate glutamate"),
        PathwayNode("step-4", "Add glycine"),
        PathwayNode("step-5", "Reduce intermediate"),
        PathwayNode("step-6", "Export product")
      ),
      edges = Seq(
        PathwayEdge("step-1-2", "step-1", "step-2"),
        PathwayEdge("step-2-3", "step-2", "step-3"),
        PathwayEdge("step-3-4", "step-3", "step-4"),
        PathwayEdge("step-3-5", "step-3", "step-5"),
        PathwayEdge("step-4-6", "step-4", "step-6"),
        PathwayEdge("step-5-6", "step-5", "step-6")
      )
    )
  )
