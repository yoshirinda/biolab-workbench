import React, { useMemo } from 'react';
import { Typography, Tooltip } from 'antd';

const { Text } = Typography;

interface ProteinViewerProps {
  sequence: string;
  name?: string;
}

// RasMol Color Scheme for Amino Acids
const AA_COLORS: { [key: string]: string } = {
  // Acidic (Red)
  D: '#E60A0A', E: '#E60A0A',
  // Basic (Blue)
  K: '#145AFF', R: '#145AFF', H: '#8282D2',
  // Polar (Green)
  S: '#FA9600', T: '#FA9600', N: '#00DCDC', Q: '#00DCDC',
  // Hydrophobic (Grey/Black)
  A: '#C8C8C8', V: '#0F820F', L: '#0F820F', I: '#0F820F', 
  P: '#DC9682', F: '#3232AA', M: '#E6E600', W: '#B45AB4', 
  G: '#EBEBEB', Y: '#3232AA',
  // Cysteine (Yellow)
  C: '#E6E600',
  // Stop / Unknown
  '*': '#000000', X: '#000000', '-': '#FFFFFF'
};

const AA_NAMES: { [key: string]: string } = {
  A: 'Alanine', R: 'Arginine', N: 'Asparagine', D: 'Aspartic Acid',
  C: 'Cysteine', E: 'Glutamic Acid', Q: 'Glutamine', G: 'Glycine',
  H: 'Histidine', I: 'Isoleucine', L: 'Leucine', K: 'Lysine',
  M: 'Methionine', F: 'Phenylalanine', P: 'Proline', S: 'Serine',
  T: 'Threonine', W: 'Tryptophan', Y: 'Tyrosine', V: 'Valine',
  '*': 'Stop', '-': 'Gap'
};

const ProteinViewer: React.FC<ProteinViewerProps> = ({ sequence, name }) => {
  const chunks = useMemo(() => {
    const cleanSeq = sequence.toUpperCase();
    const rows = [];
    const chunkSize = 60; // AA per row
    for (let i = 0; i < cleanSeq.length; i += chunkSize) {
      rows.push({
        index: i + 1,
        seq: cleanSeq.slice(i, i + chunkSize)
      });
    }
    return rows;
  }, [sequence]);

  return (
    <div style={{ 
      height: '100%', 
      overflow: 'auto', 
      padding: '20px', 
      fontFamily: "'Courier New', Courier, monospace",
      backgroundColor: '#fff',
      userSelect: 'text' 
    }}>
      {name && (
        <div style={{ marginBottom: 16, borderBottom: '1px solid #eee', paddingBottom: 8 }}>
          <Text strong style={{ fontSize: 16 }}>{name}</Text>
          <Text type="secondary" style={{ marginLeft: 12 }}>{sequence.length} aa</Text>
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
        {chunks.map((row, rowIndex) => (
          <div key={rowIndex} style={{ display: 'flex', alignItems: 'baseline' }}>
            {/* Index Column */}
            <div style={{ 
              width: 50, 
              textAlign: 'right', 
              marginRight: 15, 
              color: '#999', 
              fontSize: 12,
              userSelect: 'none'
            }}>
              {row.index}
            </div>

            {/* Sequence Column */}
            <div style={{ display: 'flex', flexWrap: 'wrap', maxWidth: '800px' }}>
              {row.seq.split('').map((aa, aaIndex) => (
                <Tooltip key={aaIndex} title={`${AA_NAMES[aa] || 'Unknown'} (${row.index + aaIndex})`} mouseEnterDelay={0.5}>
                  <span style={{ 
                    display: 'inline-block',
                    width: '1ch',
                    textAlign: 'center',
                    color: AA_COLORS[aa] || '#000',
                    fontWeight: 'bold',
                    fontSize: 14
                  }}>
                    {aa}
                  </span>
                </Tooltip>
              ))}
            </div>
          </div>
        ))}
      </div>
      
      {/* Legend */}
      <div style={{ marginTop: 30, paddingTop: 10, borderTop: '1px solid #eee', fontSize: 12, color: '#666', display: 'flex', gap: 16 }}>
        <div style={{display:'flex', alignItems:'center', gap:4}}><span style={{width:10, height:10, background:'#E60A0A', borderRadius:'50%'}}></span> Acidic</div>
        <div style={{display:'flex', alignItems:'center', gap:4}}><span style={{width:10, height:10, background:'#145AFF', borderRadius:'50%'}}></span> Basic</div>
        <div style={{display:'flex', alignItems:'center', gap:4}}><span style={{width:10, height:10, background:'#0F820F', borderRadius:'50%'}}></span> Hydrophobic</div>
        <div style={{display:'flex', alignItems:'center', gap:4}}><span style={{width:10, height:10, background:'#FA9600', borderRadius:'50%'}}></span> Polar</div>
      </div>
    </div>
  );
};

export default ProteinViewer;
