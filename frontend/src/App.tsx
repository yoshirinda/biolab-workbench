import './index.css';

const workflows = [
  {
    title: 'Reference Miner',
    href: '/uniprot/',
    description: 'Curate UniProt reference FASTA sets with explicit query, taxonomy, reviewed status, metadata, and saved provenance.',
  },
  {
    title: 'BLAST Workbench',
    href: '/blast/',
    description: 'Build local BLAST databases and run parameterized searches with detailed TSV, alignment text, summaries, and hit extraction.',
  },
  {
    title: 'Alignment Workbench',
    href: '/alignment/',
    description: 'Run MAFFT, ClustalW, or MUSCLE alignments with reproducible parameters and exportable visualizations.',
  },
  {
    title: 'Tree / Clade Viewer',
    href: '/tree/',
    description: 'Render target-centered clades with support labels, species highlighting, layout controls, and SVG export.',
  },
  {
    title: 'Phylogenetic Pipeline',
    href: '/phylo/',
    description: 'Run the HMMER → BLAST filter → length filter → MAFFT → ClipKIT → IQ-TREE workflow with preserved intermediates.',
  },
];

function App() {
  return (
    <main className="biolab-shell">
      <section className="hero">
        <p className="eyebrow">BioLab Workbench</p>
        <h1>Personal reproducible phylogenetics workspace</h1>
        <p>
          This interface is limited to the five original scientific workflows. Each workflow should expose parameters,
          preserve intermediate files, and record enough provenance to rerun or audit the analysis.
        </p>
      </section>

      <section className="workflow-grid" aria-label="BioLab workflows">
        {workflows.map((workflow) => (
          <a className="workflow-card" href={workflow.href} key={workflow.href}>
            <h2>{workflow.title}</h2>
            <p>{workflow.description}</p>
            <span>Open workflow</span>
          </a>
        ))}
      </section>
    </main>
  );
}

export default App;
