import React, { useState, Component, ErrorInfo } from 'react';
import { SeqViz } from 'seqviz';
import { Sequence } from '../types/biolab';
import { Empty, Segmented, Space, Button, Tooltip, Tag, Alert } from 'antd';
import { ReloadOutlined, ZoomInOutlined, ZoomOutOutlined } from '@ant-design/icons';
import ProteinViewer from './ProteinViewer';

// --- Error Boundary Component ---
interface ErrorBoundaryProps {
  children: React.ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

class ViewerErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("SequenceViewer Error:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: 20, height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Alert
            message="Visualization Error"
            description={this.state.error?.message || "An unexpected error occurred while rendering the sequence."}
            type="error"
            showIcon
            action={
              <Button size="small" type="primary" onClick={() => this.setState({ hasError: false, error: null })}>
                Retry
              </Button>
            }
          />
        </div>
      );
    }
    return this.props.children;
  }
}

// --- Main SequenceViewer Component ---

interface SequenceViewerProps {
  sequence: Sequence | null;
  onSelection?: (selection: { start: number; end: number; clockwise: boolean } | null) => void;
}

const SequenceViewer: React.FC<SequenceViewerProps> = ({ sequence, onSelection }) => {
  const [viewType, setViewType] = useState<'linear' | 'circular'>('linear');
  const [zoom, setZoom] = useState(50);

  // 1. Check if sequence object exists
  if (!sequence) {
    return (
      <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
        <Empty description="Select a sequence to view" />
      </div>
    );
  }
  
  // 2. Safe access to sequence string and validation
  const seqString = (sequence.sequence || sequence.seq || '').trim();
  
  if (!seqString) {
      return (
        <div style={{ padding: 20 }}>
            <Alert message="Invalid Data" description="The sequence data is empty." type="warning" showIcon />
        </div>
      );
  }

  // 3. Transform features to SeqViz format safely
  const annotations = (sequence.features || []).map(f => ({
    id: f.id,
    name: f.label || f.id || 'Feature',
    start: f.start !== undefined ? Math.max(0, f.start - 1) : 0, // Ensure non-negative
    end: f.end !== undefined ? Math.max(0, f.end - 1) : 0,
    direction: f.strand === '+' ? 1 : -1,
    color: f.color
  }));

  // SeqViz handling for proteins is limited. 
  // If protein, ensure we are in linear mode.
  const isProtein = sequence.meta?.type === 'protein' || sequence.type === 'protein';
  
  if (isProtein && viewType === 'circular') {
      setViewType('linear');
  }

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Viewer Controls */}
      <div style={{ padding: '8px 16px', borderBottom: '1px solid #303030', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: '#262626' }}>
        <Space>
           <Segmented 
             options={[
               { label: 'Linear', value: 'linear' },
               { label: 'Circular', value: 'circular', disabled: isProtein }
             ]}
             value={viewType}
             onChange={(val) => setViewType(val as any)}
           />
           {isProtein && <Tag color="blue">Protein</Tag>}
        </Space>
        <Space>
           <Tooltip title="Zoom Out"><Button icon={<ZoomOutOutlined />} onClick={() => setZoom(z => Math.max(0, z - 10))} size="small"/></Tooltip>
           <Tooltip title="Zoom In"><Button icon={<ZoomInOutlined />} onClick={() => setZoom(z => Math.min(100, z + 10))} size="small"/></Tooltip>
           <Tooltip title="Reset"><Button icon={<ReloadOutlined />} onClick={() => setZoom(50)} size="small"/></Tooltip>
        </Space>
      </div>

      {/* Main Viewer with Error Boundary */}
      <div style={{ flex: 1, width: '100%', overflow: 'hidden', display: 'flex', flexDirection: 'column', background: '#fff' }}>
        <ViewerErrorBoundary>
            {isProtein ? (
                <ProteinViewer sequence={seqString} name={sequence.id} />
            ) : (
                <SeqViz
                name={sequence.id || 'Sequence'}
                seq={seqString}
                annotations={annotations}
                style={{ height: '100%', width: '100%' }}
                viewer={viewType}
                showComplement={sequence.type === 'nucleotide'}
                zoom={{ linear: zoom, circular: zoom }}
                onSelection={(selection: any) => {
                    if (onSelection && selection) {
                    onSelection({
                        start: selection.start + 1, 
                        end: selection.end, 
                        clockwise: selection.clockwise
                    });
                    } else if (onSelection) {
                    onSelection(null);
                    }
                }}
                />
            )}
        </ViewerErrorBoundary>
      </div>
    </div>
  );
};

export default SequenceViewer;