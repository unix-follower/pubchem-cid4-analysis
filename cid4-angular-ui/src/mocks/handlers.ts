import { delay, http, HttpResponse } from "msw"

export interface MockHealthResponse {
  message: string
  source: "msw"
  timestamp: string
}

const bioactivityFixture = {
  records: [
    { aid: 743069, assay: "Tox21 ER-alpha agonist", activityValue: 355.1 },
    { aid: 743070, assay: "Tox21 ER-alpha antagonist", activityValue: 18.2 },
    { aid: 651820, assay: "NCI growth inhibition", activityValue: 92.4 },
    { aid: 540317, assay: "Cell viability counter-screen", activityValue: 112.7 },
    { aid: 504332, assay: "ChEMBL potency panel", activityValue: 8.6 },
    { aid: 720699, assay: "Nuclear receptor confirmation", activityValue: 61.9 },
    { aid: 743053, assay: "Tox21 luciferase artifact", activityValue: 140.4 },
    { aid: 743122, assay: "Dose-response validation", activityValue: 28.8 },
    { aid: 1259368, assay: "Secondary pharmacology", activityValue: 4.2 },
    { aid: 1345073, assay: "Metabolism pathway screen", activityValue: 205.5 },
  ],
}

const taxonomyFixture = {
  organisms: [
    { taxonomyId: 9913, sourceOrganism: "Bos taurus" },
    { taxonomyId: 9913, sourceOrganism: "Bos taurus" },
    { taxonomyId: 9823, sourceOrganism: "Sus scrofa" },
    { taxonomyId: 9031, sourceOrganism: "Gallus gallus" },
    { taxonomyId: 9031, sourceOrganism: "Gallus gallus" },
    { taxonomyId: 9103, sourceOrganism: "Meleagris gallopavo" },
    { taxonomyId: 9986, sourceOrganism: "Oryctolagus cuniculus" },
    { taxonomyId: 9685, sourceOrganism: "Felis catus" },
  ],
}

const pathwayFixture = {
  graph: {
    id: "glutathione-metabolism-iii",
    title: "Glutathione Metabolism III",
    directed: true,
    nodes: [
      { id: "step-1", label: "Import precursor" },
      { id: "step-2", label: "Activate cysteine" },
      { id: "step-3", label: "Ligate glutamate" },
      { id: "step-4", label: "Add glycine" },
      { id: "step-5", label: "Reduce intermediate" },
      { id: "step-6", label: "Export product" },
    ],
    edges: [
      { id: "step-1-2", source: "step-1", target: "step-2" },
      { id: "step-2-3", source: "step-2", target: "step-3" },
      { id: "step-3-4", source: "step-3", target: "step-4" },
      { id: "step-3-5", source: "step-3", target: "step-5" },
      { id: "step-4-6", source: "step-4", target: "step-6" },
      { id: "step-5-6", source: "step-5", target: "step-6" },
    ],
  },
}

const baseConformerCoordinates = {
  x: [
    1.5903, -1.9942, 0.4693, -0.7967, 0.7313, 0.4149, -0.709, -0.8967, 1.6841, 0.8156, -0.0587,
    -2.8156, -2.0968, 1.4396,
  ],
  y: [
    -0.8258, 0.1028, -0.0273, -0.643, 1.3933, -0.0317, -0.6871, -1.6812, 1.7603, 1.4252, 2.0827,
    -0.377, 0.1155, -1.7233,
  ],
  z: [
    0.0378, -0.1015, -0.3404, 0.2606, 0.1435, -1.4353, 1.3526, -0.0775, -0.2541, 1.2355, -0.1681,
    0.2637, -1.1153, -0.3047,
  ],
}

const structure2dCoordinates = {
  x: [
    2.5369, 5.135, 3.403, 4.269, 3.403, 3.403, 4.6675, 3.8705, 2.783, 3.403, 4.023, 5.672, 5.135, 2,
  ],
  y: [0.75, 0.25, 0.25, 0.75, -0.75, 1.1, 1.225, 1.225, -0.75, -1.37, -0.75, 0.56, -0.37, 0.44],
}

function buildConformerFixture(index: number) {
  const rotation = (index - 1) * 0.34
  const cos = Math.cos(rotation)
  const sin = Math.sin(rotation)
  const wobble = (index - 1) * 0.08

  const x = baseConformerCoordinates.x.map((value, atomIndex) => {
    const y = baseConformerCoordinates.y[atomIndex]
    return Number((value * cos - y * sin).toFixed(4))
  })

  const y = baseConformerCoordinates.x.map((value, atomIndex) => {
    const currentY = baseConformerCoordinates.y[atomIndex]
    return Number((value * sin + currentY * cos).toFixed(4))
  })

  const z = baseConformerCoordinates.z.map((value, atomIndex) => {
    const direction = atomIndex % 2 === 0 ? 1 : -1
    return Number((value + wobble * direction).toFixed(4))
  })

  return {
    PC_Compounds: [
      {
        id: {
          id: {
            cid: 4,
          },
        },
        atoms: {
          aid: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
          element: [8, 7, 6, 6, 6, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        },
        bonds: {
          aid1: [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 5, 5, 5],
          aid2: [3, 14, 4, 12, 13, 4, 5, 6, 7, 8, 9, 10, 11],
          order: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
        },
        coords: [
          {
            aid: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
            conformers: [
              {
                x,
                y,
                z,
              },
            ],
          },
        ],
      },
    ],
  }
}

const structure2dFixture = {
  PC_Compounds: [
    {
      id: {
        id: {
          cid: 4,
        },
      },
      atoms: {
        aid: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14],
        element: [8, 7, 6, 6, 6, 1, 1, 1, 1, 1, 1, 1, 1, 1],
      },
      bonds: {
        aid1: [1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 5, 5, 5],
        aid2: [3, 14, 4, 12, 13, 4, 5, 6, 7, 8, 9, 10, 11],
        order: [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
      },
      coords: [
        {
          conformers: [
            {
              x: structure2dCoordinates.x,
              y: structure2dCoordinates.y,
            },
          ],
        },
      ],
    },
  ],
}

const conformerFixtures = new Map(
  [1, 2, 3, 4, 5, 6].map((index) => [index, buildConformerFixture(index)]),
)

const compoundFixture = {
  Record: {
    RecordType: "CID",
    RecordNumber: 4,
    RecordTitle: "1-Amino-2-propanol",
    Section: [
      {
        TOCHeading: "Structures",
        Description:
          "Structure depictions of this compound, including computationally generated two-dimensional (2D) and three-dimensional (3D) structures.",
        Section: [
          {
            TOCHeading: "2D Structure",
            Description: "A two-dimensional structure representation of the compound.",
          },
          {
            TOCHeading: "3D Conformer",
            Description: "A three-dimensional structure representation computed by PubChem.",
          },
        ],
      },
      {
        TOCHeading: "Names and Identifiers",
        Description: "Chemical names, synonyms, identifiers, and descriptors.",
        Section: [
          {
            TOCHeading: "Record Description",
            Description: "Summary information for the compound record.",
          },
          {
            TOCHeading: "Computed Descriptors",
            Description: "Programmatically generated descriptors and properties.",
          },
        ],
      },
      {
        TOCHeading: "Chemical and Physical Properties",
        Description: "Experimental and calculated physicochemical properties.",
        Section: [
          {
            TOCHeading: "Computed Properties",
            Description: "Calculated physical descriptors.",
          },
        ],
      },
    ],
  },
}

export const handlers = [
  http.get("/api/health", async ({ request }) => {
    await delay(120)

    const mode = new URL(request.url).searchParams.get("mode")

    if (mode === "error") {
      return HttpResponse.json(
        {
          message: "Mocked transport error from MSW",
          source: "msw",
          timestamp: new Date().toISOString(),
        } satisfies MockHealthResponse,
        { status: 503 },
      )
    }

    return HttpResponse.json({
      message: "Mock transport is healthy",
      source: "msw",
      timestamp: new Date().toISOString(),
    } satisfies MockHealthResponse)
  }),
  http.get("/api/cid4/conformer/:index", async ({ params }) => {
    await delay(180)

    const index = Number(params["index"])
    const fixture = conformerFixtures.get(index)

    if (!fixture) {
      return HttpResponse.json({ message: `Unknown conformer ${params["index"]}` }, { status: 404 })
    }

    return HttpResponse.json(fixture)
  }),
  http.get("/api/cid4/structure/2d", async () => {
    await delay(160)
    return HttpResponse.json(structure2dFixture)
  }),
  http.get("/api/cid4/compound", async () => {
    await delay(140)
    return HttpResponse.json(compoundFixture)
  }),
  http.get("/api/algorithms/pathway", async () => {
    await delay(100)
    return HttpResponse.json(pathwayFixture)
  }),
  http.get("/api/algorithms/bioactivity", async () => {
    await delay(90)
    return HttpResponse.json(bioactivityFixture)
  }),
  http.get("/api/algorithms/taxonomy", async () => {
    await delay(90)
    return HttpResponse.json(taxonomyFixture)
  }),
]
