import React from "react";
import { SeqViz, SeqVizProps } from "seqviz";

// 接受完整的 BioSequence 对象或其关键属性
export interface BioSequenceViewerProps {
  name: string;
  seq: string;
  annotations?: SeqVizProps["annotations"];
  circular?: boolean; // 新增：支持环形序列
}

const BioSequenceViewer: React.FC<BioSequenceViewerProps> = ({
  name,
  seq,
  annotations = [],
  circular = false, // 默认值为线性
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
        padding: "16px",
      }}
    >
      <SeqViz
        name={name}
        seq={seq}
        annotations={annotations}
        viewer={circular ? "circular" : "both"} // 如果是环形，使用环形查看器
        showAnnotations={true}
        showComplement={true}
        zoom={{ linear: 50 }}
        style={{ flex: 1, minHeight: 0, minWidth: 0, background: '#141414', borderRadius: 8 }}
      />
    </div>
  );
};

export default BioSequenceViewer;