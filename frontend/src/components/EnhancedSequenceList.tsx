import React, { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from 'react';
import {
  Table, Button, Upload, message, Tooltip, Space, Tag, Dropdown, Modal, Input, Form,
  Statistic, Divider, Alert
} from 'antd';
import {
  UploadOutlined,
  DeleteOutlined,
  FileTextOutlined,
  EditOutlined,
  MoreOutlined,
  DownloadOutlined,
  SearchOutlined,
  ApartmentOutlined,
  ExperimentFilled
} from '@ant-design/icons';
import { Sequence } from '../types/biolab';
import { getProjectDetails, uploadSequences, deleteSequence } from '../api';
import { formatNumber } from '../utils/bioUtils';

interface EnhancedSequenceListProps {
  projectPath: string | null;
  focusSequenceIds?: string[];
  onClearFocus?: () => void;
  onDismissExtractSummary?: () => void;
  extractSummary?: {
    requestedCount: number;
    matchedCount: number;
    savedCount: number;
    unmatchedCount: number;
    unmatchedPreview: string[];
    sourceLabel: string;
  } | null;
  onSelectSequence: (sequence: Sequence | null) => void;
}

interface SequenceWithStats extends Sequence {
  featureCount?: number;
  provenanceCount?: number;
  isDerived?: boolean;
}

const EnhancedSequenceList: React.FC<EnhancedSequenceListProps> = ({
  projectPath,
  focusSequenceIds = [],
  onClearFocus,
  onDismissExtractSummary,
  extractSummary = null,
  onSelectSequence
}) => {
  const [loading, setLoading] = useState(false);
  const [sequences, setSequences] = useState<SequenceWithStats[]>([]);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [searchText, setSearchText] = useState('');
  const [pageSize, setPageSize] = useState(50);
  const loadRequestIdRef = useRef(0);

  // Rename state
  const [isRenameModalVisible, setIsRenameModalVisible] = useState(false);
  const [renameTarget, setRenameTarget] = useState<Sequence | null>(null);
  const [renameForm] = Form.useForm();

  const loadSequences = useCallback(async (options?: { forceRefresh?: boolean }) => {
    const forceRefresh = !!options?.forceRefresh;
    const requestId = ++loadRequestIdRef.current;
    if (!projectPath) {
      if (requestId === loadRequestIdRef.current) {
        setSequences([]);
        onSelectSequence(null);
      }
      return;
    }
    setLoading(true);
    try {
      const data = await getProjectDetails(projectPath, { forceRefresh });
      const simpleSequences = (data.sequences || []).map((seq: Sequence) => ({
        ...seq,
        featureCount: seq.features?.length || 0,
        provenanceCount: seq.provenance?.length || 0,
        isDerived: Boolean(seq.derivation || seq.source_sequence_id || (seq.provenance && seq.provenance.length))
      })) as SequenceWithStats[];
      if (requestId !== loadRequestIdRef.current) return;
      setSequences(simpleSequences);
    } catch (error: any) {
      if (requestId !== loadRequestIdRef.current) return;
      // Selecting a plain folder (no project.json) is valid tree behavior; treat as empty sequence list.
      if (error?.status === 404) {
        setSequences([]);
        return;
      }
      message.error(error?.message || 'Failed to load sequences');
    } finally {
      if (requestId === loadRequestIdRef.current) {
        setLoading(false);
      }
    }
  }, [projectPath, onSelectSequence]);

  useEffect(() => {
    loadSequences({ forceRefresh: true });
    setSelectedRowKeys([]);
  }, [projectPath, loadSequences]);

  const handleUpload = useCallback(async (file: File) => {
    if (!projectPath) return false;

    try {
      setLoading(true);
      await uploadSequences(file, projectPath);
      message.success(`Uploaded ${file.name} successfully`);
      loadSequences({ forceRefresh: true });
      return false;
    } catch (error: any) {
      message.error(error.message || 'Upload failed');
      return false;
    } finally {
      setLoading(false);
    }
  }, [projectPath, loadSequences]);

  const handleDelete = useCallback(async (ids?: string[]) => {
    const targets = ids || selectedRowKeys as string[];
    if (!projectPath || targets.length === 0) return;

    Modal.confirm({
      title: `Delete ${targets.length} sequence(s)?`,
      content: 'This action cannot be undone.',
      okType: 'danger',
      onOk: async () => {
        try {
          setLoading(true);
          await Promise.all(targets.map((key) => deleteSequence(projectPath, String(key))));
          message.success(`Deleted ${targets.length} sequence(s)`);
          setSelectedRowKeys([]);
          loadSequences({ forceRefresh: true });
        } catch (error) {
          message.error('Delete failed');
        } finally {
          setLoading(false);
        }
      }
    });
  }, [projectPath, selectedRowKeys, loadSequences]);

  const handleRename = useCallback(async (values: any) => {
    if (!projectPath || !renameTarget) return;
    try {
      const encodedProjectPath = projectPath
        .split('/')
        .filter(Boolean)
        .map((segment) => encodeURIComponent(segment))
        .join('/');
      const encodedSequenceId = encodeURIComponent(renameTarget.id);
      const response = await fetch(`/api/sequences/${encodedProjectPath}/${encodedSequenceId}/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_name: values.new_name })
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.error?.message || err.error || err.message || 'Rename failed');
      }

      message.success('Renamed successfully');
      setIsRenameModalVisible(false);
      loadSequences({ forceRefresh: true });
    } catch (error: any) {
      message.error(error.message);
    }
  }, [projectPath, renameTarget, loadSequences]);

  const handleExport = useCallback(async (format: 'fasta' | 'genbank' = 'fasta') => {
    const selectedSeqs = sequences
      .filter(seq => selectedRowKeys.includes(seq.id))
      .map((seq) => ({
        ...seq,
        sequence: seq.sequence || (seq as any).seq || ''
      }));
    if (selectedSeqs.length === 0) {
      message.warning('No sequences selected');
      return;
    }

    try {
      const response = await fetch('/sequence/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sequences: selectedSeqs })
      });

      const result = await response.json();
      if (result.success) {
        // Create download
        const blob = new Blob([result.fasta], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `sequences_${Date.now()}.${format}`;
        a.click();
        URL.revokeObjectURL(url);
        message.success(`Exported ${selectedSeqs.length} sequences`);
      } else {
        message.error(result.error || result.message || 'Export failed');
      }
    } catch (error) {
      message.error('Export failed');
    }
  }, [sequences, selectedRowKeys]);

  const deferredSearchText = useDeferredValue(searchText);
  const normalizedSearch = deferredSearchText.trim().toLowerCase();
  const normalizedFocusIds = useMemo(
    () => new Set((focusSequenceIds || []).map((id) => String(id || '').trim().toLowerCase()).filter(Boolean)),
    [focusSequenceIds]
  );
  const focusOrder = useMemo(() => {
    const order = new Map<string, number>();
    (focusSequenceIds || []).forEach((id, idx) => {
      const key = String(id || '').trim().toLowerCase();
      if (key && !order.has(key)) {
        order.set(key, idx);
      }
    });
    return order;
  }, [focusSequenceIds]);
  const focusedSequences = useMemo(
    () => {
      if (normalizedFocusIds.size === 0) return sequences;
      return sequences
        .filter((seq) => normalizedFocusIds.has(String(seq.id || '').trim().toLowerCase()))
        .sort((a, b) => {
          const aKey = String(a.id || '').trim().toLowerCase();
          const bKey = String(b.id || '').trim().toLowerCase();
          const aOrder = focusOrder.get(aKey);
          const bOrder = focusOrder.get(bKey);
          if (aOrder === undefined && bOrder === undefined) return 0;
          if (aOrder === undefined) return 1;
          if (bOrder === undefined) return -1;
          return aOrder - bOrder;
        });
    },
    [sequences, normalizedFocusIds, focusOrder]
  );
  const filteredSequences = useMemo(
    () => focusedSequences.filter((seq) =>
      seq.id.toLowerCase().includes(normalizedSearch) ||
      seq.description?.toLowerCase().includes(normalizedSearch)
    ),
    [focusedSequences, normalizedSearch]
  );
  const useVirtualTable = filteredSequences.length >= 200;
  const tableScroll = useMemo(
    () => (
      useVirtualTable
        ? { x: 'max-content' as const, y: 560 }
        : { x: 'max-content' as const }
    ),
    [useVirtualTable]
  );
  const paginationConfig = useMemo(
    () => ({
      pageSize,
      showSizeChanger: true,
      showTotal: (total: number) => `Total ${total} sequences`,
      pageSizeOptions: ['20', '50', '100', '200'],
      onChange: (_page: number, size: number) => {
        if (size !== pageSize) setPageSize(size);
      },
      onShowSizeChange: (_current: number, size: number) => {
        if (size !== pageSize) setPageSize(size);
      }
    }),
    [pageSize]
  );
  const nucleotideCount = useMemo(
    () => sequences.filter((seq) => (seq.type || 'nucleotide') === 'nucleotide').length,
    [sequences]
  );
  const proteinCount = useMemo(
    () => sequences.filter((seq) => seq.type === 'protein').length,
    [sequences]
  );

  const openSequenceByRecord = useCallback((record: SequenceWithStats) => {
    onSelectSequence(record);
  }, [onSelectSequence]);

  const openRenameModal = useCallback((record: SequenceWithStats) => {
    setRenameTarget(record);
    renameForm.setFieldsValue({ new_name: record.id });
    setIsRenameModalVisible(true);
  }, [renameForm]);

  const columns = useMemo(() => [
    {
      title: 'Name',
      dataIndex: 'id',
      key: 'id',
      width: 200,
      sorter: (a: SequenceWithStats, b: SequenceWithStats) => a.id.localeCompare(b.id),
      render: (text: string, record: SequenceWithStats) => (
        <Space direction="vertical" size={2}>
          <Space>
            <FileTextOutlined style={{ color: record.type === 'protein' ? '#1890ff' : '#52c41a' }} />
            <span style={{ fontWeight: 500 }}>{text}</span>
            {record.isDerived && <Tag color="purple" style={{ marginInlineStart: 4 }}>Derived</Tag>}
          </Space>
          {record.source_sequence_id && (
            <span style={{ color: '#5d7287', fontSize: 11 }}>
              from {record.source_sequence_id}
            </span>
          )}
        </Space>
      ),
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      width: 100,
      filters: [
        { text: 'Nucleotide', value: 'nucleotide' },
        { text: 'Protein', value: 'protein' }
      ],
      onFilter: (value: any, record: SequenceWithStats) => record.type === value,
      render: (type: string) => (
        <Tag color={type === 'protein' ? 'blue' : 'green'} icon={<ExperimentFilled />}>
          {type === 'protein' ? 'Protein' : 'DNA'}
        </Tag>
      ),
    },
    {
      title: 'Length',
      dataIndex: 'length',
      key: 'length',
      width: 120,
      sorter: (a: SequenceWithStats, b: SequenceWithStats) => a.length - b.length,
      render: (len: number, record: SequenceWithStats) => (
        <span className="mono">
          {formatNumber(len)} {record.type === 'protein' ? 'aa' : 'bp'}
        </span>
      ),
    },
    {
      title: 'Features',
      dataIndex: 'featureCount',
      key: 'featureCount',
      width: 100,
      sorter: (a: SequenceWithStats, b: SequenceWithStats) =>
        (a.featureCount || 0) - (b.featureCount || 0),
      render: (count: number) => (
        <Tag icon={<ApartmentOutlined />} color={count > 0 ? 'cyan' : 'default'}>
          {count}
        </Tag>
      ),
    },
    {
      title: 'Origin',
      key: 'origin',
      width: 150,
      render: (_: any, record: SequenceWithStats) => {
        if (record.source_sequence_id) {
          return <span style={{ color: '#5d7287', fontSize: 12 }}>{record.source_sequence_id}</span>;
        }
        if (record.provenanceCount) {
          return <Tag color="purple">{record.provenanceCount} event{record.provenanceCount > 1 ? 's' : ''}</Tag>;
        }
        return <span style={{ color: '#9aa9b8', fontSize: 12 }}>Primary</span>;
      },
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      ellipsis: { showTitle: false },
      render: (desc: string) => (
        <Tooltip title={desc} placement="topLeft">
          <span style={{ color: '#5d7287', fontSize: 12 }}>{desc || '-'}</span>
        </Tooltip>
      ),
    },
    {
      title: 'Action',
      key: 'action',
      width: 80,
      fixed: 'right' as const,
      render: (_: any, record: SequenceWithStats) => (
        <Dropdown menu={{
          items: [
            {
              key: 'view',
              label: 'View Details',
              icon: <FileTextOutlined />,
              onClick: () => openSequenceByRecord(record)
            },
            { type: 'divider' },
            {
              key: 'rename',
              label: 'Rename',
              icon: <EditOutlined />,
              onClick: () => openRenameModal(record)
            },
            {
              key: 'delete',
              label: 'Delete',
              icon: <DeleteOutlined />,
              danger: true,
              onClick: () => handleDelete([record.id])
            }
          ]
        }} trigger={['click']}>
          <Button type="text" icon={<MoreOutlined />} onClick={e => e.stopPropagation()} />
        </Dropdown>
      ),
    }
  ], [handleDelete, openRenameModal, openSequenceByRecord]);

  const rowSelection = useMemo(() => ({
    selectedRowKeys,
    onChange: (keys: React.Key[]) => {
      setSelectedRowKeys(keys);
    },
    type: 'checkbox' as const
  }), [selectedRowKeys]);

  const tableRowHandlers = useCallback((record: SequenceWithStats) => ({
    onClick: () => {
      // Single click opens sequence for faster inspection.
      openSequenceByRecord(record);
    },
    onDoubleClick: () => {
      // Keep double click behavior consistent with single click for user habit.
      openSequenceByRecord(record);
    }
  }), [openSequenceByRecord]);

  const renderExtractSummaryDescription = () => {
    if (!extractSummary) return undefined;

    return (
      <div>
        <div>
          Matched {extractSummary.matchedCount}/{extractSummary.requestedCount} requested IDs from {extractSummary.sourceLabel}.
          {extractSummary.savedCount > 0 ? ` Added ${extractSummary.savedCount} new sequence(s) to this project.` : ' No new sequences were added, which usually means they were already present.'}
        </div>
        {extractSummary.unmatchedCount > 0 && (
          <div style={{ marginTop: 6 }}>
            Unmatched {extractSummary.unmatchedCount}: {extractSummary.unmatchedPreview.join(', ')}
            {extractSummary.unmatchedCount > extractSummary.unmatchedPreview.length ? ' ...' : ''}
          </div>
        )}
        {extractSummary.sourceLabel.toLowerCase().includes('uniprot') && (
          <div style={{ marginTop: 6 }}>
            These sequences came from a UniProt direct import. Review names, taxa, and redundancy before treating them as a final phylogenetic reference panel.
          </div>
        )}
        {extractSummary.requestedCount > 0 && extractSummary.matchedCount / extractSummary.requestedCount < 0.5 && (
          <div style={{ marginTop: 6 }}>
            Low match rate usually points to a source FASTA or identifier-format mismatch before it supports a biological absence claim.
          </div>
        )}
      </div>
    );
  };

  const renderExtractSummaryActions = () => {
    if (!extractSummary && normalizedFocusIds.size === 0) return undefined;

    return (
      <Space>
        {normalizedFocusIds.size > 0 && (
          <Button size="small" onClick={() => onClearFocus?.()}>
            Show All
          </Button>
        )}
        {extractSummary && (
          <Button size="small" onClick={() => onDismissExtractSummary?.()}>
            Dismiss
          </Button>
        )}
      </Space>
    );
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#fff' }}>
      {/* Toolbar */}
      <div style={{
        padding: '10px 12px',
        borderBottom: '1px solid #d6e4f2',
        background: '#f6faff',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        flexWrap: 'wrap',
        gap: 8
      }}>
        <Space wrap>
          <Upload
            beforeUpload={handleUpload}
            showUploadList={false}
            disabled={!projectPath}
            multiple
            fileList={[]}
          >
            <Button icon={<UploadOutlined />} disabled={!projectPath}>
              Import
            </Button>
          </Upload>

          <Divider type="vertical" style={{ background: '#434343' }} />

          <Dropdown
            menu={{
              items: [
                { key: 'export-fasta', label: 'Export as FASTA', onClick: () => handleExport('fasta') },
                { key: 'export-genbank', label: 'Export as GenBank', onClick: () => handleExport('genbank') }
              ]
            }}
            disabled={selectedRowKeys.length === 0}
          >
            <Button icon={<DownloadOutlined />} disabled={selectedRowKeys.length === 0}>
              Export
            </Button>
          </Dropdown>

          <Button
            icon={<DeleteOutlined />}
            danger
            disabled={selectedRowKeys.length === 0}
            onClick={() => handleDelete()}
          >
            Delete
          </Button>

          <Tag color="blue">DNA {nucleotideCount}</Tag>
          <Tag color="geekblue">Protein {proteinCount}</Tag>
        </Space>

        <Space>
          <Input
            placeholder="Search sequences..."
            prefix={<SearchOutlined />}
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            style={{ width: 200 }}
            allowClear
          />

          <Statistic
            value={filteredSequences.length}
            suffix={`/ ${focusedSequences.length}${focusedSequences.length !== sequences.length ? ` (project ${sequences.length})` : ''}`}
            valueStyle={{ fontSize: 14, color: '#1a334d' }}
          />
        </Space>
      </div>

      {(extractSummary || normalizedFocusIds.size > 0) && (
        <div style={{ padding: '8px 12px', borderBottom: '1px solid #e6eff8', background: '#f2f8ff' }}>
          <Alert
            type={normalizedFocusIds.size > 0 ? 'info' : (extractSummary?.unmatchedCount || 0) > 0 ? 'warning' : 'success'}
            showIcon
            message={normalizedFocusIds.size > 0
              ? `Showing extraction hits only (${focusedSequences.length}/${focusSequenceIds.length} IDs visible in this project)`
              : 'Last extraction summary'}
            description={renderExtractSummaryDescription()}
            action={renderExtractSummaryActions()}
          />
        </div>
      )}

      {/* Table */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        <Table
          dataSource={filteredSequences}
          columns={columns}
          rowKey="id"
          size="small"
          loading={loading}
          rowSelection={rowSelection}
          pagination={paginationConfig}
          virtual={useVirtualTable}
          scroll={tableScroll}
          onRow={tableRowHandlers}
        />
      </div>

      {/* Rename Modal */}
      <Modal
        title="Rename Sequence"
        open={isRenameModalVisible}
        onOk={renameForm.submit}
        onCancel={() => setIsRenameModalVisible(false)}
      >
        <Form form={renameForm} onFinish={handleRename} layout="vertical">
          <Form.Item name="new_name" label="New Name" rules={[{ required: true }]}>
            <Input autoFocus />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default EnhancedSequenceList;
