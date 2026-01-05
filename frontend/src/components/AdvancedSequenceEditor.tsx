import React, { useCallback, useMemo } from "react";
import { Editor } from "@teselagen/ove";
import { message } from "antd";

interface Feature {
  id?: string;
  name: string;
  start: number;
  end: number;
  type?: string;
  direction?: 1 | -1;
  color?: string;
}

interface SequenceData {
  name: string;
  seq: string;
  circular?: boolean;
  features?: Feature[];
  description?: string;
}

interface AdvancedSequenceEditorProps {
  sequence: SequenceData;
  onSave?: (sequenceData: any) => void;
  onCopy?: (copiedData: any) => void;
  readOnly?: boolean;
  height?: string | number;
}

/**
 * Advanced Sequence Editor using Open Vector Editor (OVE)
 * 
 * Features:
 * - Circular and linear sequence views
 * - Feature annotation editing
 * - Restriction enzyme cut sites
 * - ORF finder
 * - Translation viewer
 * - Smart copy/paste with annotations
 */
const AdvancedSequenceEditor: React.FC<AdvancedSequenceEditorProps> = ({
  sequence,
  onSave,
  onCopy,
  readOnly = false,
  height = "600px"
}) => {
  // Convert our sequence format to OVE format
  const sequenceData = useMemo(() => {
    return {
      sequence: sequence.seq || "",
      name: sequence.name || "Untitled",
      circular: sequence.circular || false,
      features: (sequence.features || []).map(f => ({
        name: f.name,
        start: f.start - 1, // OVE uses 0-based indexing
        end: f.end - 1,
        type: f.type || "misc_feature",
        strand: f.direction || 1,
        color: f.color || "#9DEAED"
      })),
      description: sequence.description || ""
    };
  }, [sequence]);

  // Handle save event from editor
  const handleSave = useCallback((event: any, sequenceDataToSave: any[]) => {
    if (onSave && sequenceDataToSave && sequenceDataToSave.length > 0) {
      const savedSeq = sequenceDataToSave[0];
      // Convert back to our format (1-based indexing)
      const convertedData = {
        name: savedSeq.name,
        seq: savedSeq.sequence,
        circular: savedSeq.circular,
        features: (savedSeq.features || []).map((f: any) => ({
          name: f.name,
          start: f.start + 1,
          end: f.end + 1,
          type: f.type,
          direction: f.strand,
          color: f.color
        })),
        description: savedSeq.description
      };
      onSave(convertedData);
      message.success('Sequence saved successfully');
    }
  }, [onSave]);

  // Handle copy event - preserve annotations
  const handleCopy = useCallback((event: any, copiedSequenceData: any) => {
    if (onCopy) {
      onCopy(copiedSequenceData);
    }
    // The OVE editor will handle clipboard automatically
    message.success('Sequence copied with annotations');
  }, [onCopy]);

  return (
    <div 
      style={{ 
        width: "100%", 
        height: height,
        border: "1px solid #d9d9d9",
        borderRadius: "8px",
        overflow: "hidden"
      }}
    >
      <Editor
        sequenceData={sequenceData}
        // Editor Configuration
        readOnly={readOnly}
        // Panel Visibility
        annotationVisibility={{
          features: true,
          translations: true,
          parts: true,
          orfs: true,
          cutsites: true,
          primers: true
        }}
        // Show both circular and linear views
        showCircularView={sequence.circular}
        // Panels to show
        PropertiesProps={{
          propertiesList: [
            "general",
            "features",
            "parts",
            "primers",
            "translations",
            "cutsites"
          ]
        }}
        // Enable cut sites analysis
        ToolBarProps={{
          toolList: [
            "cutsiteTool",
            "featureTool", 
            "orfTool",
            "viewTool",
            "editTool",
            "findTool",
            "visibilityTool"
          ]
        }}
        // Event handlers
        onSave={handleSave}
        onCopy={handleCopy}
        // Style
        style={{
          width: "100%",
          height: "100%"
        }}
        // Additional options
        showMenuBar={true}
        allowSeqDataOverride={!readOnly}
      />
    </div>
  );
};

export default AdvancedSequenceEditor;