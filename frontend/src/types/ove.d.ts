declare module '@teselagen/ove' {
  import { ComponentType } from 'react';

  export interface EditorProps {
    sequenceData?: any;
    readOnly?: boolean;
    annotationVisibility?: {
      features?: boolean;
      translations?: boolean;
      parts?: boolean;
      orfs?: boolean;
      cutsites?: boolean;
      primers?: boolean;
    };
    showCircularView?: boolean;
    PropertiesProps?: {
      propertiesList?: string[];
    };
    ToolBarProps?: {
      toolList?: string[];
    };
    onSave?: (event: any, sequenceData: any[]) => void;
    onCopy?: (event: any, copiedData: any) => void;
    style?: React.CSSProperties;
    showMenuBar?: boolean;
    allowSeqDataOverride?: boolean;
  }

  export const Editor: ComponentType<EditorProps>;
}