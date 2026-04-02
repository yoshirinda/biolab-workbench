import React, { useState, useMemo } from 'react';
import type { CSSProperties } from 'react';
import {
  Card, Statistic, Row, Col, Divider, Tag, Button, Space,
  message, Typography, Modal, Form, Select, Alert, Input
} from 'antd';
import {
  SwapOutlined, ScissorOutlined,
  DownloadOutlined, CopyOutlined, FileTextOutlined,
  ExperimentFilled
} from '@ant-design/icons';
import { BioSequence, Sequence } from '../types/biolab';
import {
  calculateGC,
  calculateMolecularWeight,
  calculateTm,
  getReverseComplement,
  translateSequence
} from '../utils/bioUtils';
import { addFeature, deleteFeature, updateFeature, updateSequenceAnnotation } from '../api';

const { Text, Paragraph } = Typography;

interface EnhancedPropertiesPanelProps {
  sequence: (BioSequence | Sequence) | null;
  projectPath: string | null;
  selection?: { start: number; end: number; clockwise: boolean } | null;
  onUpdate?: () => void;
  onFeatureJump?: (featureId: string) => void;
  activeFeatureId?: string | null;
}

const EnhancedPropertiesPanel: React.FC<EnhancedPropertiesPanelProps> = ({
  sequence,
  projectPath,
  selection,
  onUpdate,
  onFeatureJump,
  activeFeatureId
}) => {
  const [showTranslateModal, setShowTranslateModal] = useState(false);
  const [translateFrame, setTranslateFrame] = useState(1);
  const [translatedProtein, setTranslatedProtein] = useState('');
  const [annotationDraft, setAnnotationDraft] = useState('');
  const [featureLabel, setFeatureLabel] = useState('');
  const [featureType, setFeatureType] = useState('Misc');
  const [featureColor, setFeatureColor] = useState('#4CAF50');
  const [featureFilter, setFeatureFilter] = useState('');
  const [featureSort, setFeatureSort] = useState<'start' | 'type' | 'name'>('start');
  const [editingFeatureId, setEditingFeatureId] = useState<string | null>(null);
  const [savingAnnotation, setSavingAnnotation] = useState(false);
  const [savingFeature, setSavingFeature] = useState(false);
  const [deletingFeatureId, setDeletingFeatureId] = useState<string | null>(null);

  const seqData = (sequence as any)?.seq || (sequence as any)?.sequence || '';
  const seqType = (sequence as any)?.meta?.type || (sequence as any)?.type || 'nucleotide';
  const sequenceName = (sequence as any)?.meta?.name || (sequence as any)?.id || 'sequence';
  const sequenceLength = (sequence as any)?.meta?.length || seqData.length;
  const topology = (sequence as any)?.meta?.topology || 'linear';
  const isNucleotide = seqType === 'nucleotide';
  const panelCardStyle: CSSProperties = {
    marginBottom: 12,
    borderColor: '#d6e4f2',
    borderRadius: 10,
    background: '#ffffff'
  };

  // Calculate statistics
  const stats = useMemo(() => {
    const gc = isNucleotide ? calculateGC(seqData) : undefined;
    const mw = calculateMolecularWeight(seqData, seqType);
    const tm = isNucleotide && seqData.length < 100 ? calculateTm(seqData) : undefined;
    return { gc, mw, tm };
  }, [seqData, seqType, isNucleotide]);

  const selectedSeq = useMemo(() => {
    if (!selection || !isNucleotide) return null;
    const { start, end } = selection;
    return seqData.substring(start, end + 1);
  }, [selection, seqData, isNucleotide]);

  const provenanceEvents = Array.isArray((sequence as any)?.provenance) ? (sequence as any).provenance : [];
  const derivation = ((sequence as any)?.derivation && typeof (sequence as any).derivation === 'object') ? (sequence as any).derivation : null;
  const sourceSequenceId = (sequence as any)?.source_sequence_id || provenanceEvents[0]?.source_sequence_id || null;
  const sourceProject = (sequence as any)?.source_project || provenanceEvents[0]?.source_project || null;
  const featureCount = Array.isArray((sequence as any)?.features) ? (sequence as any).features.length : 0;
  const visibleFeatures = useMemo(() => {
    const all = Array.isArray((sequence as any)?.features) ? [...(sequence as any).features] : [];
    const filtered = featureFilter.trim()
      ? all.filter((feature: any) => `${feature.label || feature.name || ''} ${feature.type || ''}`.toLowerCase().includes(featureFilter.trim().toLowerCase()))
      : all;
    filtered.sort((a: any, b: any) => {
      if (featureSort === 'name') return String(a.label || a.name || '').localeCompare(String(b.label || b.name || ''));
      if (featureSort === 'type') return String(a.type || '').localeCompare(String(b.type || '')) || Number(a.start || 0) - Number(b.start || 0);
      return Number(a.start || 0) - Number(b.start || 0);
    });
    return filtered;
  }, [sequence, featureFilter, featureSort]);

  React.useEffect(() => {
    setAnnotationDraft((sequence as any)?.annotation || '');
  }, [sequence]);

  if (!sequence) {
    return (
      <div style={{ padding: 24, textAlign: 'center', color: '#5d7287' }}>
        <FileTextOutlined style={{ fontSize: 48, marginBottom: 16 }} />
        <div>No sequence selected</div>
        <div style={{ fontSize: 12, marginTop: 8 }}>
          Select a sequence to view details
        </div>
      </div>
    );
  }

  const saveSequenceToProject = async (
    name: string,
    value: string,
    description = '',
    provenance?: Record<string, unknown>
  ) => {
    if (!projectPath) {
      message.warning('Select a project folder before saving derived sequences');
      return;
    }

    const form = new FormData();
    form.append('project_path', projectPath);
    form.append('source', 'text');
    form.append('text', `>${name} ${description}\n${value}`);
    if (provenance) {
      form.append('provenance_json', JSON.stringify(provenance));
    }

    const response = await fetch('/sequence/import', {
      method: 'POST',
      body: form,
    });
    const result = await response.json();
    if (!response.ok || !result.success) {
      throw new Error(result.error || result.message || 'Failed to save sequence');
    }
  };

  const handleTranslate = () => {
    if (!isNucleotide) {
      message.warning('Can only translate nucleotide sequences');
      return;
    }
    const translated = translateSequence(seqData.slice(translateFrame - 1));
    setTranslatedProtein(translated);
    setShowTranslateModal(true);
  };

  const refreshTranslation = (frame: number) => {
    setTranslateFrame(frame);
    const start = frame > 0 ? frame - 1 : 0;
    const source = frame > 0 ? seqData : getReverseComplement(seqData);
    setTranslatedProtein(translateSequence(source.slice(start)));
  };

  const saveTranslation = async () => {
    if (!translatedProtein) return;
    try {
      await saveSequenceToProject(
        `${sequenceName}_F${translateFrame}_AA`,
        translatedProtein,
        `Translated from ${sequenceName}`,
        {
          operation: 'translate',
          source_sequence_id: sequenceName,
          source_project: projectPath,
          source_type: seqType,
          frame: translateFrame
        }
      );
      message.success('Translated protein saved to current project');
      setShowTranslateModal(false);
      onUpdate?.();
    } catch (e: any) {
      message.error(e.message || 'Failed to save translated sequence');
    }
  };

  const handleReverseComplement = async () => {
    if (!isNucleotide) {
      message.warning('Can only reverse complement nucleotide sequences');
      return;
    }

    const rc = getReverseComplement(seqData);

    try {
      await saveSequenceToProject(
        `${sequenceName}_RC`,
        rc,
        `Reverse complement of ${sequenceName}`,
        {
          operation: 'reverse_complement',
          source_sequence_id: sequenceName,
          source_project: projectPath,
          source_type: seqType
        }
      );
      message.success('Reverse complement saved to current project');
      onUpdate?.();
    } catch (error) {
      message.error('Failed to create reverse complement');
    }
  };

  const handleCopySequence = () => {
    const fasta = buildFastaText();
    navigator.clipboard.writeText(fasta);
    message.success('FASTA copied to clipboard');
  };

  const handleExportFasta = () => {
    const fasta = buildFastaText();
    const blob = new Blob([fasta], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${sequenceName}.fasta`;
    a.click();
    URL.revokeObjectURL(url);
    message.success('FASTA file downloaded');
  };

  const handleSaveAnnotation = async () => {
    if (!projectPath || !sequence) return;
    try {
      setSavingAnnotation(true);
      await updateSequenceAnnotation(projectPath, (sequence as any).id, annotationDraft);
      message.success('Annotation updated');
      onUpdate?.();
    } catch (error: any) {
      message.error(error?.message || 'Failed to update annotation');
    } finally {
      setSavingAnnotation(false);
    }
  };

  const handleAddFeature = async () => {
    if (!projectPath || !sequence || !selection) {
      message.warning('Select a sequence range first to create a feature');
      return;
    }
    if (!featureLabel.trim()) {
      message.warning('Feature name is required');
      return;
    }
    try {
      setSavingFeature(true);
      await addFeature(projectPath, (sequence as any).id, {
        label: featureLabel.trim(),
        type: featureType,
        start: selection.start + 1,
        end: selection.end + 1,
        strand: selection.clockwise === false ? '-' : '+',
        color: featureColor,
      });
      message.success('Feature added');
      setFeatureLabel('');
      onUpdate?.();
    } catch (error: any) {
      message.error(error?.message || 'Failed to add feature');
    } finally {
      setSavingFeature(false);
    }
  };

  const handleDeleteFeature = async (featureId: string) => {
    if (!projectPath || !sequence) return;
    try {
      setDeletingFeatureId(featureId);
      await deleteFeature(projectPath, (sequence as any).id, featureId);
      message.success('Feature deleted');
      onUpdate?.();
    } catch (error: any) {
      message.error(error?.message || 'Failed to delete feature');
    } finally {
      setDeletingFeatureId(null);
    }
  };

  const handleStartEditFeature = (feature: any) => {
    setEditingFeatureId(feature.id || null);
    setFeatureLabel(feature.label || feature.name || '');
    setFeatureType(feature.type || 'Misc');
    setFeatureColor(feature.color || '#4CAF50');
  };

  const handleSaveFeatureEdit = async () => {
    if (!projectPath || !sequence || !editingFeatureId) return;
    try {
      setSavingFeature(true);
      await updateFeature(projectPath, (sequence as any).id, editingFeatureId, {
        label: featureLabel.trim(),
        type: featureType,
        color: featureColor,
      });
      message.success('Feature updated');
      setEditingFeatureId(null);
      setFeatureLabel('');
      onUpdate?.();
    } catch (error: any) {
      message.error(error?.message || 'Failed to update feature');
    } finally {
      setSavingFeature(false);
    }
  };

  const buildFastaText = () => {
    const wrapped = seqData.replace(/(.{1,60})/g, '$1\n').trim();
    return `>${sequenceName}\n${wrapped}\n`;
  };

  const openBlastWithSequence = async () => {
    const fasta = buildFastaText();
    navigator.clipboard.writeText(fasta);
    sessionStorage.setItem('biolab-blast-query', fasta);
    message.success('Sequence copied and sent to BLAST workspace');
    window.location.href = '/blast/';
  };

  const openAlignmentWithSequence = async () => {
    const fasta = buildFastaText();
    navigator.clipboard.writeText(fasta);
    sessionStorage.setItem('biolab-alignment-query', fasta);
    message.success('Sequence copied and sent to alignment workspace');
    window.location.href = '/alignment/';
  };

  return (
    <div style={{ height: '100%', overflow: 'auto', background: '#f8fcff' }}>
      <div style={{ padding: 12 }}>
        <Card
          title="Quick Actions"
          size="small"
          style={panelCardStyle}
        >
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            <Button
              block
              icon={<SwapOutlined />}
              onClick={handleTranslate}
              disabled={!isNucleotide}
            >
              Translate
            </Button>
            <Button
              block
              icon={<ScissorOutlined />}
              onClick={handleReverseComplement}
              disabled={!isNucleotide}
            >
              Reverse Complement
            </Button>
            <Divider style={{ margin: '8px 0', borderColor: '#e4edf6' }} />
            <Button block icon={<CopyOutlined />} onClick={handleCopySequence}>
              Copy FASTA
            </Button>
            <Button block onClick={openBlastWithSequence}>
              Send to BLAST
            </Button>
            <Button block onClick={openAlignmentWithSequence}>
              Send to Alignment
            </Button>
            <Button block onClick={() => { window.location.href = '/tree/'; }}>
              Open Tree Workspace
            </Button>
            <Button block icon={<DownloadOutlined />} onClick={handleExportFasta}>
              Export FASTA
            </Button>
          </Space>
        </Card>

        <Card
          title="Sequence Information"
          size="small"
          style={panelCardStyle}
        >
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            <div>
                <Text type="secondary">Name:</Text>
              <div style={{ fontWeight: 500 }}>{sequenceName}</div>
            </div>
            <div>
              <Text type="secondary">Type:</Text>
              <div>
                <Tag color={isNucleotide ? 'green' : 'blue'} icon={<ExperimentFilled />}>
                  {isNucleotide ? 'Nucleotide' : 'Protein'}
                </Tag>
              </div>
            </div>
            <div>
                <Text type="secondary">Topology:</Text>
              <div>
                <Tag>{String(topology).toLowerCase() === 'circular' ? 'Circular' : 'Linear'}</Tag>
              </div>
            </div>
            {sequence?.description && (
              <div>
                <Text type="secondary">Description:</Text>
                <Paragraph ellipsis={{ rows: 2, expandable: true }} style={{ marginBottom: 0 }}>
                  {sequence?.description}
                </Paragraph>
              </div>
            )}
          </Space>
        </Card>

        <Card
          title="Workbench Summary"
          size="small"
          style={panelCardStyle}
        >
          <Row gutter={[8, 8]}>
            <Col span={12}>
              <Statistic
                title="Features"
                value={featureCount}
                valueStyle={{ fontSize: 18 }}
              />
            </Col>
            <Col span={12}>
              <Statistic
                title="Lineage Events"
                value={provenanceEvents.length}
                valueStyle={{ fontSize: 18 }}
              />
            </Col>
          </Row>
          {(sourceSequenceId || derivation) && (
            <Alert
              style={{ marginTop: 12 }}
              type="info"
              showIcon
              message={sourceSequenceId ? `Derived from ${sourceSequenceId}` : 'Derived sequence'}
              description={sourceProject ? `Source project: ${sourceProject}` : 'This sequence was generated from another sequence or analysis step.'}
            />
          )}
        </Card>

        <Card
          title="Key Statistics"
          size="small"
          style={panelCardStyle}
        >
          <Row gutter={[8, 8]}>
            <Col span={12}>
              <Statistic
                title="Length"
                value={sequenceLength}
                suffix={isNucleotide ? 'bp' : 'aa'}
                valueStyle={{ fontSize: 20 }}
              />
            </Col>
            <Col span={12}>
              <Statistic
                title="Mol. Weight"
                value={(stats.mw / 1000).toFixed(1)}
                suffix="kDa"
                valueStyle={{ fontSize: 20 }}
              />
            </Col>
            {isNucleotide && stats.gc !== undefined && (
              <>
                <Col span={12}>
                  <Statistic
                    title="GC Content"
                    value={stats.gc}
                    suffix="%"
                    valueStyle={{ fontSize: 20 }}
                  />
                </Col>
                {stats.tm && (
                  <Col span={12}>
                    <Statistic
                      title="Tm"
                      value={stats.tm.toFixed(1)}
                      suffix="°C"
                      valueStyle={{ fontSize: 20 }}
                    />
                  </Col>
                )}
              </>
            )}
          </Row>
        </Card>

        <Card
          title="Annotation"
          size="small"
          style={panelCardStyle}
        >
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            <Input.TextArea
              value={annotationDraft}
              onChange={(e) => setAnnotationDraft(e.target.value)}
              rows={3}
              placeholder="Short note shown in FASTA export headers"
            />
            <Button type="primary" onClick={handleSaveAnnotation} loading={savingAnnotation} disabled={!projectPath}>
              Save Annotation
            </Button>
          </Space>
        </Card>

        <Card
          title={`Features (${featureCount})`}
          size="small"
          style={panelCardStyle}
        >
          <Space direction="vertical" style={{ width: '100%' }} size="small">
            <Alert
              type={editingFeatureId ? 'warning' : 'info'}
              showIcon
              message={editingFeatureId ? 'Editing existing feature' : 'Feature workspace'}
              description={editingFeatureId ? 'Update name, type, or color for the selected feature below.' : 'Locate, edit, or delete existing features, or turn the current viewer selection into a new feature.'}
            />
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12, color: '#5d7287' }}>
              <span>{featureCount} annotated region{featureCount === 1 ? '' : 's'}</span>
              {selection ? <span>selection ready</span> : <span>no active selection</span>}
            </div>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                value={featureFilter}
                onChange={(e) => setFeatureFilter(e.target.value)}
                placeholder="Filter features"
                style={{ width: '60%' }}
              />
              <Select value={featureSort} onChange={(v) => setFeatureSort(v)} style={{ width: '40%' }}>
                <Select.Option value="start">Sort: Start</Select.Option>
                <Select.Option value="name">Sort: Name</Select.Option>
                <Select.Option value="type">Sort: Type</Select.Option>
              </Select>
            </Space.Compact>
            {visibleFeatures.length > 0 ? visibleFeatures.slice(0, 12).map((feature: any) => (
              <div key={feature.id || `${feature.label}_${feature.start}_${feature.end}`} style={{ padding: 8, background: editingFeatureId === feature.id ? '#fff8e6' : activeFeatureId === feature.id ? '#eef6ff' : '#f8fcff', border: editingFeatureId === feature.id ? '1px solid #f0b429' : activeFeatureId === feature.id ? '1px solid #0969da' : '1px solid #e4edf6', borderRadius: 6 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                  <div>
                    <div style={{ fontWeight: 500 }}>{feature.label || feature.name || feature.type}</div>
                    <div style={{ fontSize: 12, color: '#5d7287' }}>
                      {feature.type} · {feature.start}-{feature.end} · strand {feature.strand || '+'}
                    </div>
                    {feature.color && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 4, fontSize: 11, color: '#5d7287' }}>
                        <span style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: feature.color, border: '1px solid rgba(0,0,0,0.15)' }} />
                        {feature.color}
                      </div>
                    )}
                  </div>
                  <Space size={0}>
                    {feature.id && (
                      <Button
                        size="small"
                        type="text"
                        onClick={() => onFeatureJump?.(feature.id)}
                      >
                        Locate
                      </Button>
                    )}
                    <Button
                      size="small"
                      type="text"
                      onClick={() => handleStartEditFeature(feature)}
                    >
                      Edit
                    </Button>
                    {feature.id && (
                      <Button
                        size="small"
                        danger
                        type="text"
                        loading={deletingFeatureId === feature.id}
                        onClick={() => handleDeleteFeature(feature.id)}
                      >
                        Delete
                      </Button>
                    )}
                  </Space>
                </div>
              </div>
            )) : (
              <div style={{ color: '#5d7287', fontSize: 12 }}>No features yet.</div>
            )}
            <Divider style={{ margin: '8px 0', borderColor: '#e4edf6' }} />
            <Input
              value={featureLabel}
              onChange={(e) => setFeatureLabel(e.target.value)}
              placeholder={selection ? `Feature for ${selection.start + 1}-${selection.end + 1}` : 'Select a region first'}
            />
            {selection && (
              <Alert
                type="success"
                showIcon
                message={`Selected region: ${selection.start + 1}-${selection.end + 1}`}
                description="You can turn the current viewer selection into a feature annotation directly below."
              />
            )}
            {!selection && (
              <div style={{ color: '#5d7287', fontSize: 12 }}>
                Tip: drag across bases in the viewer to create a selection, then add it as a feature here.
              </div>
            )}

            <Space.Compact style={{ width: '100%' }}>
              <Select value={featureType} onChange={setFeatureType} style={{ width: '55%' }}>
                <Select.Option value="Gene">Gene</Select.Option>
                <Select.Option value="CDS">CDS</Select.Option>
                <Select.Option value="Promoter">Promoter</Select.Option>
                <Select.Option value="Misc">Misc</Select.Option>
              </Select>
              <Input value={featureColor} onChange={(e) => setFeatureColor(e.target.value)} placeholder="#4CAF50" style={{ width: '45%' }} />
            </Space.Compact>
            {editingFeatureId ? (
              <Space style={{ width: '100%', justifyContent: 'space-between' }}>
                <Button onClick={() => { setEditingFeatureId(null); setFeatureLabel(''); }}>
                  Cancel Edit
                </Button>
                <Button type="primary" onClick={handleSaveFeatureEdit} loading={savingFeature} disabled={!projectPath || !featureLabel.trim()}>
                  Save Feature Edit
                </Button>
              </Space>
            ) : (
              <Button type="primary" onClick={handleAddFeature} loading={savingFeature} disabled={!selection || !projectPath}>
                Add Feature from Selection
              </Button>
            )}
          </Space>
        </Card>

        {(provenanceEvents.length > 0 || derivation) && (
          <Card
            title="Lineage / Provenance"
            size="small"
            style={panelCardStyle}
          >
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              <Alert
                type="info"
                showIcon
                message="Sequence lineage"
                description="Use this panel to trace where the sequence came from before aligning, trimming, or building trees."
              />
              {derivation && (
                <div>
                  <Text type="secondary">Operation:</Text>
                  <div>{String(derivation.operation || 'derived')}</div>
                </div>
              )}
              {sourceSequenceId && (
                <div>
                  <Text type="secondary">Source sequence:</Text>
                  <div>{sourceSequenceId}</div>
                </div>
              )}
              {sourceProject && (
                <div>
                  <Text type="secondary">Source project:</Text>
                  <div style={{ wordBreak: 'break-all' }}>{sourceProject}</div>
                </div>
              )}
              {provenanceEvents.slice(0, 3).map((event: any, idx: number) => (
                <div key={`${event.created_at || 'evt'}_${idx}`} style={{ padding: 8, background: '#f8fcff', border: '1px solid #e4edf6', borderRadius: 6 }}>
                  <div style={{ fontWeight: 500 }}>{String(event.operation || 'derived')}</div>
                  {event.created_at && <div style={{ fontSize: 12, color: '#5d7287' }}>{event.created_at}</div>}
                  {event.details && Object.keys(event.details).length > 0 && (
                    <div style={{ marginTop: 4, fontSize: 12, color: '#34495e' }}>
                      {Object.entries(event.details).map(([k, v]) => `${k}: ${String(v)}`).join(' | ')}
                    </div>
                  )}
                </div>
              ))}
            </Space>
          </Card>
        )}

        {selection && selectedSeq && (
          <Card
            title="Selection"
            size="small"
            style={panelCardStyle}
          >
            <Space direction="vertical" style={{ width: '100%' }} size="small">
              <div>
                <Text type="secondary">Range:</Text>
                <div>{selection.start + 1} - {selection.end + 1}</div>
              </div>
              <div>
                <Text type="secondary">Length:</Text>
                <div>{selectedSeq.length} bp</div>
              </div>
              <div>
                <Text type="secondary">GC Content:</Text>
                <div>{calculateGC(selectedSeq).toFixed(1)}%</div>
              </div>
            </Space>
          </Card>
        )}
      </div>

      {/* Translate Modal */}
      <Modal
        title="Translate Sequence"
        open={showTranslateModal}
        onCancel={() => setShowTranslateModal(false)}
        footer={null}
        width={600}
      >
        <Form layout="vertical">
          <Form.Item label="Reading Frame">
            <Select value={String(translateFrame)} onChange={(v) => refreshTranslation(parseInt(v, 10))}>
              <Select.Option value="1">Frame +1</Select.Option>
              <Select.Option value="2">Frame +2</Select.Option>
              <Select.Option value="3">Frame +3</Select.Option>
            </Select>
          </Form.Item>
          <Form.Item label="Protein Sequence (preview)">
            <div
              style={{
                maxHeight: 180,
                overflow: 'auto',
                padding: 8,
                border: '1px solid #d6e4f2',
                borderRadius: 6,
                fontFamily: 'IBM Plex Mono, SFMono-Regular, Menlo, monospace',
                background: '#f8fcff',
                whiteSpace: 'pre-wrap',
                wordBreak: 'break-all',
              }}
            >
              {translatedProtein || '(empty)'}
            </div>
          </Form.Item>
          <Form.Item>
            <Space style={{ width: '100%', justifyContent: 'space-between' }}>
              <Button
                onClick={() => {
                  navigator.clipboard.writeText(translatedProtein || '');
                  message.success('Protein sequence copied');
                }}
              >
                Copy
              </Button>
              <Button type="primary" onClick={saveTranslation} disabled={!translatedProtein}>
                Save To Project
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default EnhancedPropertiesPanel;
