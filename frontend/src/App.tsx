import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { ConfigProvider, Button, Space, message, Modal, Input, Form, Select, Empty, Spin, Alert, Typography } from 'antd';
import { 
  Search, Database, ArrowLeft
} from 'lucide-react'; 

import ProjectTree from './components/ProjectTree';
import EnhancedSequenceList from './components/EnhancedSequenceList';
import SequenceViewer from './components/SequenceViewer';
import EnhancedPropertiesPanel from './components/EnhancedPropertiesPanel';
import { FileNode, BioSequence, Sequence } from './types/biolab';
import { fetchProjectTree, deleteProject, getProjectDetails } from './api';

const { Text } = Typography;

// --- Mock Initial Data for Demo (Fallback) ---
const MOCK_ROOT: FileNode[] = [
  { key: 'root', title: 'Loading...', isFolder: true, parentId: null, children: [] }
];

const encodePathSegments = (path: string) =>
  path
    .split('/')
    .filter(Boolean)
    .map((segment) => encodeURIComponent(segment))
    .join('/');

type ExtractSummary = {
  requestedCount: number;
  matchedCount: number;
  savedCount: number;
  unmatchedCount: number;
  unmatchedPreview: string[];
  sourceLabel: string;
};

function App() {
  // --- State ---
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [treeData, setTreeData] = useState<FileNode[]>(MOCK_ROOT);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [activeSequence, setActiveSequence] = useState<BioSequence | Sequence | null>(null);
  const [selection, setSelection] = useState<{ start: number; end: number; clockwise: boolean } | null>(null);
  const [activeFolder, setActiveFolder] = useState<string | null>(null);
  const [activeProjectPath, setActiveProjectPath] = useState<string | null>(null);
  const [openSequence, setOpenSequence] = useState<BioSequence | Sequence | null>(null);
  const [extractFocusIds, setExtractFocusIds] = useState<string[]>([]);
  const [lastExtractSummary, setLastExtractSummary] = useState<ExtractSummary | null>(null);
  
  // Extract Tool State
  const [isExtractModalVisible, setIsExtractModalVisible] = useState(false);
  const [isManageDbModalVisible, setIsManageDbModalVisible] = useState(false);
  const [extractForm] = Form.useForm();
  const [sourceDatabases, setSourceDatabases] = useState<any[]>([]);

  // --- Data Loading ---
  const loadTree = async (options?: { silent?: boolean; forceRefresh?: boolean }) => {
    const silent = !!options?.silent;
    const forceRefresh = !!options?.forceRefresh;
    try {
        if (!silent) setLoading(true);
        setLoadError(null);
        const data = await fetchProjectTree({ forceRefresh });
        
        const mapNode = (n: any, p: string | null): FileNode => {
            const children: FileNode[] = n.children?.map((c: any) => mapNode(c, n.path)) || [];
            return {
                key: n.path,
                title: n.name,
                isFolder: true,
                isProject: !!n.is_project,
                parentId: p,
                children: children,
                data: undefined
            };
        };
        
        if (Array.isArray(data)) {
            setTreeData(data.map(n => mapNode(n, null)));
        }
    } catch (e) {
        console.error(e);
        message.error("Failed to load projects");
        setLoadError(e instanceof Error ? e.message : 'Failed to load projects');
    } finally {
        if (!silent) setLoading(false);
    }
  };

  useEffect(() => { loadTree(); }, []);

  const fetchDatabases = () => {
      fetch('/api/sequences/sources')
        .then(res => res.json())
        .then(data => {
            const sources = Array.isArray(data) ? data : (Array.isArray(data?.data) ? data.data : []);
            if (Array.isArray(sources)) {
                setSourceDatabases(sources);
                if (sources.length > 0) {
                    const defaultSource = sources.find((s: any) => s.exists !== false) || sources[0];
                    extractForm.setFieldsValue({ source_fasta_id: defaultSource?.id });
                }
            }
        })
        .catch(e => console.error("Failed to load sources", e));
  };

  useEffect(() => {
      if (isExtractModalVisible || isManageDbModalVisible) fetchDatabases();
  }, [isExtractModalVisible, isManageDbModalVisible]);

  // --- Logic Helpers ---
  const nodeIndex = useMemo(() => {
    const index = new Map<string, FileNode>();
    const walk = (nodes: FileNode[]) => {
      for (const node of nodes) {
        index.set(node.key, node);
        if (node.children?.length) walk(node.children);
      }
    };
    walk(treeData);
    return index;
  }, [treeData]);

  const findNodeByKey = (key: string | null | undefined): FileNode | null => {
    if (!key) return null;
    return nodeIndex.get(key) || null;
  };

  const resolveNearestProjectPath = (startKey: string | null | undefined): string | null => {
    if (!startKey) return null;
    let current = findNodeByKey(startKey);
    while (current) {
      if (current.isProject) return current.key;
      current = current.parentId ? findNodeByKey(current.parentId) : null;
    }
    return null;
  };

  const findFirstProjectPath = (nodes: FileNode[]): string | null => {
    for (const node of nodes) {
      if (node.isProject) return node.key;
      if (node.children?.length) {
        const childResult = findFirstProjectPath(node.children);
        if (childResult) return childResult;
      }
    }
    return null;
  };

  const getSelectedNode = (): FileNode | null => {
    if (selectedKeys.length === 0) return null;
    return findNodeByKey(selectedKeys[0]);
  };

  const findSequenceByIdLoose = (sequences: any[], targetId: string) => {
    if (!targetId) return null;
    const normalized = targetId.trim().toLowerCase();
    return sequences.find((s: any) => String(s?.id || '').trim().toLowerCase() === normalized) || null;
  };

  const handleSelectSequence = useCallback((seq: Sequence | null) => {
    const next = (seq as any) || null;
    setActiveSequence(next);
    setOpenSequence(next);
    setSelection(null);
  }, []);

  const handleClearExtractFocus = useCallback(() => {
    setExtractFocusIds([]);
  }, []);

  const handleDismissExtractSummary = useCallback(() => {
    setLastExtractSummary(null);
  }, []);

  const handleResetExtractContext = useCallback(() => {
    setExtractFocusIds([]);
    setLastExtractSummary(null);
  }, []);

  // --- Event Handlers ---
  const handleDelete = (node: FileNode) => {
    Modal.confirm({
        title: `Delete ${node.title}?`,
        okType: 'danger',
        onOk: async () => {
            try {
                if (node.isFolder) {
                    await deleteProject(node.key);
                } else {
                    const lastSlash = node.key.lastIndexOf('/');
                    const folderPath = node.key.substring(0, lastSlash);
                    const seqId = node.title;
                    const response = await fetch(`/api/sequences/${encodePathSegments(folderPath)}/${encodeURIComponent(seqId)}`, { method: 'DELETE' });
                    const payload = await response.json().catch(() => null);
                    if (!response.ok || payload?.success === false) {
                      throw new Error(payload?.error?.message || payload?.error || payload?.message || 'Delete failed');
                    }
                }
                message.success("Deleted");
                loadTree({ silent: true, forceRefresh: true });
                if (openSequence && openSequence.id === node.title) {
                    setOpenSequence(null);
                    setActiveSequence(null);
                }
            } catch (e) {
                message.error("Delete failed");
            }
        }
    });
  };

  const handleRename = (node: FileNode) => {
      let newName = prompt("Enter new name:", node.title);
      if (newName && newName !== node.title) {
          if (node.isFolder) {
              message.warning("Renaming folders not yet supported");
          } else {
              const lastSlash = node.key.lastIndexOf('/');
              const folderPath = node.key.substring(0, lastSlash);
              const seqId = node.title;
              fetch(`/api/sequences/${encodePathSegments(folderPath)}/${encodeURIComponent(seqId)}/rename`, {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({ new_name: newName })
              }).then(res => {
                  if (res.ok) {
                      message.success("Renamed");
                      loadTree({ silent: true, forceRefresh: true });
                  } else {
                      res.json().then(d => message.error(d.error?.message || d.error || d.message || "Failed"));
                  }
              });
          }
      }
  };

  const handleExtract = async (values: any) => {
    try {
        const selected = getSelectedNode();
        let targetPath: string | null = null;

        if (selected) {
          if (selected.isFolder) {
            targetPath = selected.isProject ? selected.key : resolveNearestProjectPath(selected.key);
          } else {
            targetPath = resolveNearestProjectPath(selected.parentId || null);
          }
        }
        if (!targetPath) {
          targetPath = resolveNearestProjectPath(activeProjectPath);
        }
        if (!targetPath) {
          targetPath = findFirstProjectPath(treeData);
        }

        if (!targetPath) {
             message.error("Please select a project folder (contains project.json) first.");
             return;
        }
        const rawText = String(values.gene_ids || '').trim();
        if (!rawText) {
          message.error('Please input gene IDs');
          return;
        }

        // Normalize/clean IDs using backend parser first.
        const parseResp = await fetch('/sequence/parse-gene-ids', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text: rawText })
        });
        const parseResult = await parseResp.json();
        if (!parseResp.ok || !parseResult.success) {
          throw new Error(parseResult.error || 'Failed to parse gene IDs');
        }
        if (!parseResult.count) {
          message.error('No valid gene IDs found');
          return;
        }
        const parsedIds = Array.isArray(parseResult.gene_ids) ? parseResult.gene_ids : [];
        const strictSingleId = parsedIds.length === 1;
        const singleTokenInput = !/\s/.test(rawText);
        const normalizeId = (id: string) => id.trim().toLowerCase().replace(/[._-]v?\d+$/i, '');
        if (singleTokenInput && strictSingleId) {
          if (parsedIds.length !== 1 || normalizeId(parsedIds[0] || '') !== normalizeId(rawText)) {
            throw new Error('Single-ID input parsed as multiple/other IDs. Please keep only one clean gene ID in the box.');
          }
        }

        const resolvedSourceId = values.source_fasta_id || sourceDatabases?.[0]?.id;
        if (!resolvedSourceId) {
          message.error('Please upload/select a source FASTA database first.');
          return;
        }

        const payload: any = {
          target_project: targetPath,
          gene_ids: parsedIds.join('\n'),
          source_fasta_id: resolvedSourceId,
          use_latest_database: true,
          strict_single_id: strictSingleId
        };

        const response = await fetch('/api/sequences/extract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const rawResult = await response.json();
        const result = rawResult?.success !== undefined ? (rawResult.data || {}) : rawResult;
        if (!response.ok || rawResult?.success === false) {
          throw new Error(
            rawResult?.error?.message ||
            rawResult?.message ||
            result?.error ||
            result?.message ||
            'Extract failed'
          );
        }

        const matchedCount = Number(result?.matched_count ?? 0);
        const requestedCount = Number(result?.requested_count ?? 0);
        const savedCount = Number(result?.saved_count ?? 0);
        const unmatchedCount = Number(result?.unmatched_count ?? 0);
        const unmatchedPreview = Array.isArray(result?.unmatched_preview) ? result.unmatched_preview : [];
        const extractedIds = Array.isArray(result?.extracted_ids) ? result.extracted_ids : [];
        const baseMessage = result?.message || rawResult?.message || 'Extraction completed';
        const sourceRecord = sourceDatabases.find((db: any) => db.id === resolvedSourceId);
        const sourceLabel = sourceRecord?.label || sourceRecord?.filename || 'Selected source FASTA';

        if (matchedCount > 0 && savedCount > 0) {
          message.success(`${baseMessage} (${matchedCount}/${requestedCount} matched, +${savedCount} added)`);
        } else if (matchedCount > 0 && savedCount === 0) {
          message.warning(`${baseMessage} (${matchedCount}/${requestedCount} matched, +0 added; likely already existed)`);
        } else {
          message.warning(`${baseMessage} (${matchedCount}/${requestedCount} matched)`);
        }
        if (extractedIds.length > 0) {
          const preview = extractedIds.slice(0, 5).join(', ');
          message.info(`Extracted IDs: ${preview}${extractedIds.length > 5 ? ' ...' : ''}`);
        }

        if (unmatchedPreview.length > 0) {
          message.warning(`Unmatched ${unmatchedCount}: ${unmatchedPreview.join(', ')}`);
        }
        setLastExtractSummary({
          requestedCount,
          matchedCount,
          savedCount,
          unmatchedCount,
          unmatchedPreview,
          sourceLabel
        });
        setExtractFocusIds(extractedIds);
        extractForm.setFieldsValue({ gene_ids: '' });
        setIsExtractModalVisible(false);
        await loadTree({ silent: true, forceRefresh: true });
        setSelectedKeys([targetPath]);
        setActiveFolder(targetPath);
        setActiveProjectPath(targetPath);
        if (extractedIds.length === 1) {
          try {
            const project = await getProjectDetails(targetPath);
            const seq = findSequenceByIdLoose(project?.sequences || [], extractedIds[0]);
            setOpenSequence(seq);
            setActiveSequence(seq);
          } catch {
            setOpenSequence(null);
            setActiveSequence(null);
          }
        } else {
          setOpenSequence(null);
          setActiveSequence(null);
        }
    } catch (e: any) {
        message.error(e?.message || 'Extract failed');
    }
  };

  const handleDeleteDb = async (id: string) => {
      try {
          const response = await fetch('/sequence/delete-source-fasta', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({ id, remove_file: true })
          });
          const result = await response.json().catch(() => ({}));
          if (!response.ok || !result.success) {
            throw new Error(result.error || result.message || 'Failed to remove database');
          }
          message.success("Database removed");
          const nextSources = sourceDatabases.filter((db) => db.id !== id);
          setSourceDatabases(nextSources);
          const currentSelectedId = extractForm.getFieldValue('source_fasta_id');
          if (currentSelectedId === id) {
            const fallbackSource = nextSources.find((db) => db.exists !== false) || nextSources[0];
            extractForm.setFieldsValue({ source_fasta_id: fallbackSource?.id });
          }
          fetchDatabases();
      } catch (e: any) {
          message.error(e?.message || "Failed to remove database");
      }
  };

  // --- Render Layout ---
  return (
    <ConfigProvider
      theme={{
        token: {
          colorPrimary: '#0969da',
          borderRadius: 10,
          colorBgContainer: '#ffffff',
          colorText: '#112235',
          colorTextSecondary: '#5d7287',
        },
      }}
    >
      <div className="workbench-shell">
        <div className="wb-header">
          <div>
            <div className="wb-brand-title">BioLab Sequence Workbench</div>
            <div className="wb-brand-subtitle">
              Clean sequence management for daily analysis
            </div>
          </div>
          <Space wrap>
            <Button onClick={() => { window.location.href = '/'; }}>Home</Button>
            <Button icon={<Database size={14} />} onClick={() => setIsManageDbModalVisible(true)}>Databases</Button>
            <Button type="primary" icon={<Search size={14} />} onClick={() => setIsExtractModalVisible(true)}>Extract Genes</Button>
          </Space>
        </div>

        <div className="wb-main">
            <div className="wb-panel wb-left">
                <div className="wb-panel-title">PROJECTS</div>
                <div style={{ flex: 1, overflow: 'auto' }}>
                    {loading ? <div style={{padding: 20, textAlign: 'center'}}><Spin /></div> : (
                        <ProjectTree 
                            treeData={treeData} 
                            selectedKeys={selectedKeys}
                            onSelect={(keys) => {
                                setSelectedKeys(keys as string[]);
                                handleResetExtractContext();
                                if (keys.length > 0) {
                                    const node = findNodeByKey(keys[0] as string);
                                    if (node) {
                                        if (node.isFolder) {
                                            const nextProjectPath = node.isProject ? node.key : resolveNearestProjectPath(node.key);
                                            setActiveFolder(node.key);
                                            setActiveProjectPath(nextProjectPath);
                                            if (nextProjectPath !== activeProjectPath) {
                                                setOpenSequence(null);
                                                setActiveSequence(null);
                                                setSelection(null);
                                            }
                                        } else if (node.data) {
                                            setActiveFolder(node.parentId);
                                            setActiveProjectPath(resolveNearestProjectPath(node.parentId || null) || node.parentId);
                                            setActiveSequence(node.data);
                                            setOpenSequence(node.data);
                                            setSelection(null);
                                        }
                                    }
                                } else {
                                    setActiveFolder(null);
                                    setActiveProjectPath(null);
                                    setOpenSequence(null);
                                    setActiveSequence(null);
                                    setSelection(null);
                                }
                            }}
                            onContextMenuClick={(action, node) => {
                                if (action === 'delete') handleDelete(node);
                                if (action === 'rename') handleRename(node);
                            }}
                        />
                    )}
                </div>
            </div>

            <div className="wb-panel wb-center">
                <div className="wb-center-head">
                    {openSequence ? (
                        <Space>
                            <Button type="text" icon={<ArrowLeft size={16} />} onClick={() => { setOpenSequence(null); setActiveSequence(null); setSelection(null); }}>Back</Button>
                            <Text strong>
                              {(openSequence as any).meta?.name || openSequence.id}
                            </Text>
                        </Space>
                    ) : (
                        <span className="wb-path-text">
                          {activeFolder ? activeFolder : 'Select a folder from the project tree'}
                        </span>
                    )}
                </div>
                <div style={{ flex: 1, position: 'relative', overflow: 'hidden', background: '#ffffff' }}>
                    {openSequence ? (
                        <SequenceViewer sequence={openSequence} onSelection={setSelection} />
                    ) : loadError ? (
                        <div style={{ padding: 16 }}>
                          <Alert
                            type="error"
                            showIcon
                            message="Project Tree Load Failed"
                            description={
                              <div>
                                <div>{loadError}</div>
                                <div style={{ marginTop: 8 }}>
                                  Check backend logs and confirm the backend service is running in your target WSL environment.
                                </div>
                              </div>
                            }
                            action={<Button size="small" onClick={loadTree}>Retry</Button>}
                          />
                        </div>
                    ) : !activeFolder ? (
                        <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                          <Empty description="Select a project/folder from the left panel" />
                        </div>
                    ) : !activeProjectPath ? (
                        <div style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
                          <Empty description="This is a plain folder. Select a project (folder containing project.json) to view sequences." />
                        </div>
                    ) : (
                        <EnhancedSequenceList
                          projectPath={activeProjectPath}
                          activeSequenceId={openSequence?.id || activeSequence?.id || null}
                          focusSequenceIds={extractFocusIds}
                          onClearFocus={handleClearExtractFocus}
                          onDismissExtractSummary={handleDismissExtractSummary}
                          extractSummary={lastExtractSummary}
                          onSelectSequence={handleSelectSequence}
                        />
                    )}
                </div>
            </div>

            <div className="wb-panel wb-right">
                <div className="wb-panel-title">INSPECTOR</div>
                <div style={{ flex: 1, overflow: 'auto' }}>
                    <EnhancedPropertiesPanel
                        sequence={activeSequence} 
                        projectPath={activeProjectPath}
                        selection={selection}
                        onUpdate={loadTree}
                    />
                </div>
            </div>
        </div>

        {/* Modals */}
        <Modal
          title="Extract Sequences by Gene IDs"
          open={isExtractModalVisible}
          onOk={extractForm.submit}
          onCancel={() => {
            setIsExtractModalVisible(false);
            extractForm.setFieldsValue({ gene_ids: '' });
          }}
          okText="Extract"
        >
            <Form form={extractForm} onFinish={handleExtract} layout="vertical">
                <Form.Item name="source_fasta_id" label="Source Database" rules={[{ required: true }]}>
                    <Select placeholder="Select a source FASTA file..." showSearch optionFilterProp="children">
                        {sourceDatabases.map(db => (
                          <Select.Option key={db.id} value={db.id}>
                            {db.label} ({db.sequence_count})
                          </Select.Option>
                        ))}
                    </Select>
                </Form.Item>
                <Form.Item name="gene_ids" label="Gene IDs / BLAST Table" rules={[{ required: true }]}>
                    <Input.TextArea
                      rows={10}
                      placeholder={"支持多种输入格式：\n- 一行一个基因号\n- 逗号/空格分隔\n- BLAST 表格（自动识别第2列）"}
                      style={{fontFamily: 'monospace'}}
                    />
                </Form.Item>
                <Alert
                  type="info"
                  showIcon
                  message="Extraction Guidance"
                  description="先确认 Source Database 与目标物种/基因组一致。若匹配率偏低，优先检查源 FASTA 和 ID 格式，而不是直接把未命中解释为基因缺失。"
                />
            </Form>
        </Modal>

        <Modal title="Manage Databases" open={isManageDbModalVisible} onCancel={() => setIsManageDbModalVisible(false)} footer={null}>
            <div style={{display: 'flex', gap: 8, marginBottom: 16}}>
                <input type="file" id="db-upload" style={{display: 'none'}} onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                        const formData = new FormData();
                        formData.append('file', file);
                        fetch('/sequence/set-source-fasta', { method: 'POST', body: formData })
                          .then(async (r) => ({ ok: r.ok, data: await r.json().catch(() => ({})) }))
                          .then(({ ok, data }) => {
                              if (ok && data.success) {
                                message.success("Uploaded");
                                const uploadedEntry = data.entry;
                                if (uploadedEntry?.id) {
                                  extractForm.setFieldsValue({ source_fasta_id: uploadedEntry.id });
                                }
                                fetchDatabases();
                              } else {
                                message.error(data.error || data.message || 'Upload failed');
                              }
                          })
                          .catch(() => message.error('Upload failed'));
                    }
                }}/>
                <Button type="primary" onClick={() => document.getElementById('db-upload')?.click()}>Upload New</Button>
            </div>
            <div style={{maxHeight: 300, overflow: 'auto', border: '1px solid #d6e4f2', borderRadius: 8, background: '#f8fcff'}}>
                {sourceDatabases.map(db => (
                    <div key={db.id} style={{padding: 8, borderBottom: '1px solid #e4edf6', display: 'flex', justifyContent: 'space-between'}}>
                        <span>{db.label}</span>
                        <Button size="small" danger type="text" onClick={() => handleDeleteDb(db.id)}>Delete</Button>
                    </div>
                ))}
            </div>
        </Modal>

      </div>
    </ConfigProvider>
  );
}

export default App;
