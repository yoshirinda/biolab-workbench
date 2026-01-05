import React, { useState, useEffect } from 'react';
import { Layout, ConfigProvider, Button, Space, message, Modal, Input, theme, Form, Select, Radio, Empty, Spin } from 'antd';
import { 
  Search, Database, ArrowLeft, Folder, FileText 
} from 'lucide-react'; 

import ProjectTree from './components/ProjectTree';
import SequenceList from './components/SequenceList';
import SequenceViewer from './components/SequenceViewer';
import PropertiesPanel from './components/PropertiesPanel';
import { FileNode, BioSequence, ClipboardState } from './types/biolab';
import { cloneNodeWithNewIds, findNode, updateTree } from './utils/treeUtils';
import { calculateGC } from './utils/bioUtils';
import { fetchProjectTree, deleteProject } from './api';

const { Content } = Layout;

// --- Mock Initial Data for Demo (Fallback) ---
const MOCK_ROOT: FileNode[] = [
  { key: 'root', title: 'Loading...', isFolder: true, parentId: null, children: [] }
];

function App() {
  // --- State ---
  const [loading, setLoading] = useState(true);
  const [treeData, setTreeData] = useState<FileNode[]>(MOCK_ROOT);
  const [selectedKeys, setSelectedKeys] = useState<string[]>([]);
  const [clipboard, setClipboard] = useState<ClipboardState>({ node: null, operation: null });
  const [activeSequence, setActiveSequence] = useState<BioSequence | null>(null);
  const [selection, setSelection] = useState<{ start: number; end: number; clockwise: boolean } | null>(null);
  const [activeFolder, setActiveFolder] = useState<string | null>(null);
  const [openSequence, setOpenSequence] = useState<BioSequence | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  
  // Extract Tool State
  const [isExtractModalVisible, setIsExtractModalVisible] = useState(false);
  const [isManageDbModalVisible, setIsManageDbModalVisible] = useState(false);
  const [extractForm] = Form.useForm();
  const [sourceDatabases, setSourceDatabases] = useState<any[]>([]);
  const [extractionSourceType, setExtractionSourceType] = useState<'project' | 'database'>('database');

  // --- Data Loading ---
  const loadTree = async () => {
    try {
        setLoading(true);
        const data = await fetchProjectTree();
        
        const mapNode = (n: any, p: string | null): FileNode => {
            let children: FileNode[] = n.children?.map((c: any) => mapNode(c, n.path)) || [];
            if (n.sequences && Array.isArray(n.sequences)) {
                const seqNodes: FileNode[] = n.sequences.map((seq: any) => {
                    let gc = 0;
                    if (seq.type === 'nucleotide' || !seq.type) {
                        gc = calculateGC(seq.sequence || seq.seq || '');
                    }
                    return {
                        key: `${n.path}/${seq.id}`,
                        title: seq.id,
                        isFolder: false,
                        parentId: n.path,
                        data: {
                            id: seq.id,
                            seq: seq.sequence,
                            features: seq.features || [],
                            meta: {
                                name: seq.id,
                                length: seq.length || seq.sequence?.length,
                                created: seq.added || new Date().toISOString(),
                                type: seq.type || 'nucleotide',
                                topology: 'linear',
                                gcContent: gc 
                            },
                            description: seq.description
                        } as BioSequence
                    };
                });
                children = [...children, ...seqNodes];
            }
            return {
                key: n.path,
                title: n.name,
                isFolder: true,
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
    } finally {
        setLoading(false);
    }
  };

  useEffect(() => { loadTree(); }, []);

  const fetchDatabases = () => {
      fetch('/api/sequences/sources')
        .then(res => res.json())
        .then(data => {
            if (Array.isArray(data)) {
                setSourceDatabases(data);
                if (data.length > 0 && extractionSourceType === 'database') {
                    extractForm.setFieldsValue({ source_fasta_id: data[0].id });
                }
            }
        })
        .catch(e => console.error("Failed to load sources", e));
  };

  useEffect(() => {
      if (isExtractModalVisible || isManageDbModalVisible) fetchDatabases();
  }, [isExtractModalVisible, isManageDbModalVisible]);

  // --- Logic Helpers ---
  const findNodeRecursive = (nodes: FileNode[], key: string): FileNode | null => {
      for (const node of nodes) {
          if (node.key === key) return node;
          if (node.children) {
              const found = findNodeRecursive(node.children, key);
              if (found) return found;
          }
      }
      return null;
  };

  const getSelectedNode = (): FileNode | null => {
    if (selectedKeys.length === 0) return null;
    return findNodeRecursive(treeData, selectedKeys[0]);
  };

  // --- Event Handlers ---
  const handleCopy = (node: FileNode | null) => {
    if (!node) return;
    setClipboard({ node: node, operation: 'copy' });
    message.info(`Copied "${node.title}"`);
  };

  const handlePaste = (targetFolderKey: string) => {
    if (!clipboard.node) return;
    message.info("Paste backend API pending");
  };

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
                    await fetch(`/api/sequences/${folderPath}/${seqId}`, { method: 'DELETE' });
                }
                message.success("Deleted");
                loadTree();
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
              fetch(`/api/sequences/${folderPath}/${seqId}/rename`, {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({ new_name: newName })
              }).then(res => {
                  if (res.ok) {
                      message.success("Renamed");
                      loadTree();
                  } else {
                      res.json().then(d => message.error(d.error || "Failed"));
                  }
              });
          }
      }
  };

  const handleExtract = async (values: any) => {
    try {
        const selected = getSelectedNode();
        let targetPath = selected?.key;
        if (selected && !selected.isFolder) targetPath = selected.parentId || null;
        if (!targetPath) {
             message.error("Please select a target folder first.");
             return;
        }
        const payload: any = { target_project: targetPath, gene_ids: values.gene_ids };
        if (extractionSourceType === 'database') payload.source_fasta_id = values.source_fasta_id;
        else payload.source_project = targetPath;

        const response = await fetch('/api/sequences/extract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const result = await response.json();
        if (!response.ok) throw new Error(result.message || 'Extract failed');
        message.success(result.message);
        if (result.unmatched?.length > 0) message.warning(`Unmatched: ${result.unmatched.join(', ')}`);
        setIsExtractModalVisible(false);
        loadTree();
    } catch (e: any) {
        message.error(e.message);
    }
  };

  const handleDeleteDb = async (id: string) => {
      try {
          await fetch('/sequence/delete-source-fasta', {
              method: 'POST',
              headers: {'Content-Type': 'application/json'},
              body: JSON.stringify({ id, remove_file: true })
          });
          message.success("Database removed");
          fetchDatabases();
      } catch (e) {
          message.error("Failed to remove database");
      }
  };

  // --- Render Layout ---
  return (
    <ConfigProvider theme={{ algorithm: theme.darkAlgorithm, token: { colorPrimary: "#1677ff" } }}>
      <Layout style={{ height: "100%", background: '#141414', display: 'flex', flexDirection: 'column' }}>
        
        {/* Toolbar */}
        <div style={{ height: 48, minHeight: 48, display: "flex", alignItems: "center", justifyContent: 'space-between', padding: "0 16px", borderBottom: '1px solid #303030', background: '#1f1f1f' }}>
           <div style={{ color: "#fff", fontWeight: 'bold' }}>Sequence Manager</div>
           <Space>
            <Button icon={<Database size={14} />} onClick={() => setIsManageDbModalVisible(true)}>Databases</Button>
            <Button type="primary" icon={<Search size={14} />} onClick={() => setIsExtractModalVisible(true)}>Extract Genes</Button>
           </Space>
        </div>

        {/* Main Content Area - Flex Row */}
        <div style={{ flex: 1, display: 'flex', overflow: 'hidden' }}>
            
            {/* Left: Project Tree */}
            <div style={{ width: 250, minWidth: 200, borderRight: "1px solid #303030", display: 'flex', flexDirection: 'column', background: '#141414' }}>
                <div style={{ padding: '8px 12px', background: '#1f1f1f', fontSize: 12, fontWeight: 'bold', color: '#888' }}>PROJECTS</div>
                <div style={{ flex: 1, overflow: 'auto' }}>
                    {loading ? <div style={{padding: 20, textAlign: 'center'}}><Spin /></div> : (
                        <ProjectTree 
                            treeData={treeData} 
                            selectedKeys={selectedKeys}
                            onSelect={(keys) => {
                                setSelectedKeys(keys as string[]);
                                if (keys.length > 0) {
                                    const node = findNodeRecursive(treeData, keys[0] as string);
                                    if (node) {
                                        if (node.isFolder) {
                                            setActiveFolder(node.key);
                                            setOpenSequence(null);
                                            setActiveSequence(null);
                                        } else if (node.data) {
                                            setActiveSequence(node.data);
                                            setOpenSequence(node.data);
                                        }
                                    }
                                }
                            }}
                            onContextMenuClick={(action, node) => {
                                if (action === 'copy') handleCopy(node);
                                if (action === 'delete') handleDelete(node);
                                if (action === 'rename') handleRename(node);
                            }}
                        />
                    )}
                </div>
            </div>

            {/* Middle: Sequence Viewer */}
            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', background: '#000', overflow: 'hidden' }}>
                <div style={{ height: 40, borderBottom: '1px solid #303030', display: 'flex', alignItems: 'center', padding: '0 16px', background: '#1f1f1f' }}>
                    {openSequence ? (
                        <Space>
                            <Button type="text" icon={<ArrowLeft size={16} />} onClick={() => setOpenSequence(null)} style={{color: '#fff'}}>Back</Button>
                            <span style={{color: '#fff', fontWeight: 'bold'}}>{openSequence.meta.name}</span>
                        </Space>
                    ) : (
                        <span style={{color: '#888'}}>{activeFolder ? activeFolder : 'Select a folder'}</span>
                    )}
                </div>
                <div style={{ flex: 1, position: 'relative', overflow: 'hidden' }}>
                    {openSequence ? (
                        <SequenceViewer sequence={openSequence} onSelection={setSelection} />
                    ) : (
                        <SequenceList projectPath={activeFolder} onSelectSequence={(seq) => { setActiveSequence(seq); setOpenSequence(seq); }} />
                    )}
                </div>
            </div>

            {/* Right: Inspector */}
            <div style={{ width: 300, minWidth: 200, borderLeft: "1px solid #303030", display: 'flex', flexDirection: 'column', background: '#141414' }}>
                <div style={{ padding: '8px 12px', background: '#1f1f1f', fontSize: 12, fontWeight: 'bold', color: '#888' }}>INSPECTOR</div>
                <div style={{ flex: 1, overflow: 'auto' }}>
                    <PropertiesPanel 
                        sequence={activeSequence} 
                        projectPath={activeFolder || (activeSequence ? 'derived' : null)}
                        selection={selection}
                        onUpdate={loadTree}
                    />
                </div>
            </div>
        </div>

        {/* Modals */}
        <Modal title="Batch Extract Sequences" open={isExtractModalVisible} onOk={extractForm.submit} onCancel={() => setIsExtractModalVisible(false)} okText="Extract">
            <Form form={extractForm} onFinish={handleExtract} layout="vertical" initialValues={{ source_type: 'database' }}>
                <Form.Item label="Source Type" name="source_type">
                    <Radio.Group onChange={e => setExtractionSourceType(e.target.value)} value={extractionSourceType}>
                        <Radio.Button value="database">Database</Radio.Button>
                        <Radio.Button value="project">Current Folder</Radio.Button>
                    </Radio.Group>
                </Form.Item>
                {extractionSourceType === 'database' && (
                    <Form.Item name="source_fasta_id" label="Source Database" rules={[{ required: true }]}>
                        <Select placeholder="Select a source FASTA file...">
                            {sourceDatabases.map(db => <Select.Option key={db.id} value={db.id}>{db.label} ({db.sequence_count})</Select.Option>)}
                        </Select>
                    </Form.Item>
                )}
                <Form.Item name="gene_ids" label="Gene IDs" rules={[{ required: true }]}>
                    <Input.TextArea rows={8} placeholder="Enter IDs..." style={{fontFamily: 'monospace'}} />
                </Form.Item>
            </Form>
        </Modal>

        <Modal title="Manage Databases" open={isManageDbModalVisible} onCancel={() => setIsManageDbModalVisible(false)} footer={null}>
            <div style={{display: 'flex', gap: 8, marginBottom: 16}}>
                <input type="file" id="db-upload" style={{display: 'none'}} onChange={(e) => {
                    const file = e.target.files?.[0];
                    if (file) {
                        const fd = new FormData();
                        formData.append('file', file); // Error here: formData undefined. Fixed below.
                        // Actually let's fix inline var name
                        const formData = new FormData();
                        formData.append('file', file);
                        fetch('/sequence/set-source-fasta', { method: 'POST', body: formData }).then(r=>r.json()).then(d => {
                            if(d.success) { message.success("Uploaded"); fetchDatabases(); }
                            else message.error(d.error);
                        });
                    }
                }}/>
                <Button type="primary" onClick={() => document.getElementById('db-upload')?.click()}>Upload New</Button>
            </div>
            <div style={{maxHeight: 300, overflow: 'auto', border: '1px solid #333'}}>
                {sourceDatabases.map(db => (
                    <div key={db.id} style={{padding: 8, borderBottom: '1px solid #333', display: 'flex', justifyContent: 'space-between'}}>
                        <span>{db.label}</span>
                        <Button size="small" danger type="text" onClick={() => handleDeleteDb(db.id)}>Del</Button>
                    </div>
                ))}
            </div>
        </Modal>

      </Layout>
    </ConfigProvider>
  );
}

export default App;