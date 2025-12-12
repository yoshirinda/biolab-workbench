import React from "react";
import { SeqViz, SeqVizProps } from "seqviz";


export interface BioSequenceViewerProps {
  name: string;
  seq: string;
  annotations?: SeqVizProps["annotations"];
}


const BioSequenceViewer: React.FC<BioSequenceViewerProps> = ({
  name,
  seq,
  annotations = [],
}) => {
  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        background: "var(--background, #181a1b)",
        color: "var(--text, #fff)",
        minHeight: 0,
        minWidth: 0,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <SeqViz
        name={name}
        seq={seq}
        annotations={annotations}
        viewer="both"
        showAnnotations={true}
        showComplement={true}
        zoom={{ linear: 50 }}
        style={{ flex: 1, minHeight: 0, minWidth: 0 }}
      />
    </div>
  );
};

export default BioSequenceViewer;
