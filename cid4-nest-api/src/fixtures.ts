export const bioactivityFixture = {
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
} as const

export const taxonomyFixture = {
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
} as const

export const pathwayFixture = {
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
} as const
