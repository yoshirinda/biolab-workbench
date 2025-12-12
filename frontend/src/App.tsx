import React, { useState, useCallback } from "react";
import {
  Layout,
  Menu,
  ConfigProvider,
  Empty,
  Descriptions,
  Tag,
  Dropdown,
  Modal,
  Input,
  message,
} from "antd";
import { PanelGroup, Panel, PanelResizeHandle } from "react-resizable-panels";
import { DirectoryTreeProps } from "antd/es/tree";
import DirectoryTree from "antd/es/tree/DirectoryTree";
import { Folder, Dna } from "lucide-react";
import BioSequenceViewer from "./components/BioSequenceViewer";
import { v4 as uuidv4 } from 'uuid';

// 1. 数据模型
interface BioSequence {
  name: string;
  seq: string;
  type: "dna" | "rna" | "protein";
  circular: boolean;
  annotations: Array<{
    name: string;
    start: number;
    end: number;
    direction: 1 | -1;
    color?: string;
    type?: "CDS" | "promoter" | "enzyme";
  }>;
}

interface FileNode {
  key: string;
  title: string;
  isFolder: boolean;
  children?: FileNode[];
  data?: BioSequence | null;
}

// 初始模拟数据
const initialProjectData: FileNode[] = [
  {
    key: "0",
    title: "Geneious Prime Projects",
    isFolder: true,
    children: [
      {
        key: "0-0",
        title: "Plasmid Engineering",
        isFolder: true,
        children: [
          {
            key: "0-0-0",
            title: "pFA6a-GFP(S65T)-kanMX6",
            isFolder: false,
            data: {
              name: "pFA6a-GFP(S65T)-kanMX6",
              seq: "GGCCTCCGCGCCGGGTTTTGGCGCCTCCCGCGGGCGCCCCCCTCCCTCCTCGGCG",
              type: "dna",
              circular: true,
              annotations: [
                { name: "kanMX6", start: 1, end: 15, direction: 1, color: "#f5a623", type: "CDS" },
                { name: "GFP(S65T)", start: 20, end: 40, direction: -1, color: "#7ed321", type: "CDS" },
              ],
            },
          },
        ],
      },
    ],
  },
];

const { Header, Content } = Layout;

// --- 组件 ---

const ProjectExplorer: React.FC<{
  projectData: FileNode[];
  onSelectNode: (sequence: BioSequence | null) => void;
  onRightClick: (info: { event: React.MouseEvent, node: any }) => void;
}> = ({ projectData, onSelectNode, onRightClick }) => {
  const handleSelect: DirectoryTreeProps["onSelect"] = (_, info) => {
    const node = info.node as any;
    // 关键修正：传递 node.data 而不是整个 node
    onSelectNode(node.isLeaf && node.data ? node.data : null);
  };
  
  const getIcon = (isFolder: boolean) => isFolder ? <Folder size={18} /> : <Dna size={18} color="#00e676" />;

  const renderTreeData = (nodes: FileNode[]): any[] =>
    nodes.map((node) => ({
      ...node,
      isLeaf: !node.isFolder,
      icon: getIcon(node.isFolder),
      children: node.children ? renderTreeData(node.children) : [],
    }));

  return (
    <div style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div style={{ padding: "12px 16px", color: "#fff", fontWeight: 600, fontSize: 16, borderBottom: '1px solid #23272e' }}>
        Project Explorer
      </div>
      <div style={{flex: 1, overflowY: 'auto'}}>
        <DirectoryTree
            style={{ background: "transparent", color: "#fff", padding: "8px" }}
            treeData={renderTreeData(projectData)}
            showIcon
            onSelect={handleSelect}
            onRightClick={onRightClick}
            defaultExpandAll
        />
      </div>
    </div>
  );
};

const SequenceInspector: React.FC<{ sequence: BioSequence | null }> = ({
  sequence,
}) => {
  if (!sequence) {
    return <div style={{ padding: 20, color: '#888' }}>Select a sequence to see its properties.</div>;
  }
  return (
    <div style={{ padding: "12px", color: "#fff", height: '100%', overflowY: 'auto' }}>
       <div style={{ padding: "0 4px 12px 4px", color: "#fff", fontWeight: 600, fontSize: 16, borderBottom: '1px solid #23272e', marginBottom: 12 }}>Inspector</div>
      <Descriptions title="Properties" bordered column={1} size="small">
        <Descriptions.Item label="Name">{sequence.name}</Descriptions.Item>
        <Descriptions.Item label="Length">{sequence.seq.length} bp</Descriptions.Item>
        <Descriptions.Item label="Type">{sequence.type.toUpperCase()}</Descriptions.Item>
        <Descriptions.Item label="Topology">{sequence.circular ? "Circular" : "Linear"}</Descriptions.Item>
      </Descriptions>
      <Descriptions title="Annotations" bordered column={1} size="small" style={{marginTop: 20}}>
        {sequence.annotations.map((ann, i) => (
          <Descriptions.Item key={i} label={ann.name}>
             {ann.start}..{ann.end} <Tag color={ann.color} style={{marginLeft: 8}}>{ann.type}</Tag>
          </Descriptions.Item>
        ))}
        {sequence.annotations.length === 0 && <Descriptions.Item label="N/A">No annotations</Descriptions.Item>}
      </Descriptions>
    </div>
  );
};

// --- 主应用 ---
function App() {
  const [projectData, setProjectData] = useState<FileNode[]>(initialProjectData);
  const [activeSequence, setActiveSequence] = useState<BioSequence | null>(null);
  const [contextMenu, setContextMenu] = useState<{ visible: boolean, x: number, y: number, node: FileNode | null }>({ visible: false, x: 0, y: 0, node: null });
  const [modal, setModal] = useState<{ visible: boolean, type: 'newFile' | 'newFolder' | 'rename', node: FileNode | null }>({ visible: false, type: 'newFile', node: null });
  const [inputValue, setInputValue] = useState("");

  // --- 递归文件操作 ---
  const recursiveMap = (nodes: FileNode[], callback: (node: FileNode) => FileNode | null): FileNode[] => {
    return nodes.map(node => {
        const newNode = callback(node);
        if (!newNode) return null;
        if (newNode.children) {
            newNode.children = recursiveMap(newNode.children, callback);
        }
        return newNode;
    }).filter((node): node is FileNode => node !== null);
  };

  const handleMenuClick = (action: 'newFile' | 'newFolder' | 'rename' | 'delete', node: FileNode | null) => {
    setContextMenu({ ...contextMenu, visible: false });

    if (action === 'rename' || action === 'delete') {
        if (!node) return;
        if (action === 'rename') {
            setInputValue(node.title);
            setModal({ visible: true, type: 'rename', node });
        } else { // 'delete'
            Modal.confirm({
              title: `Delete '${node.title}'?`,
              content: `This action will permanently delete the item.`,
              okText: 'Delete',
              okType: 'danger',
              onOk: () => {
                setProjectData(oldTree => recursiveMap(oldTree, n => n.key === node.key ? null : n));
                if (activeSequence && node.data?.name === activeSequence.name) {
                    setActiveSequence(null);
                }
              },
            });
        }
    } else { // 'newFile' or 'newFolder'
        const parent = node ? (node.isFolder ? node : null) : null; // simplified parent logic
        setModal({ visible: true, type: action, node: parent });
    }
  };
  
  const handleModalOk = () => {
    const { type, node } = modal; // node is parent for new, target for rename
    if (!inputValue) {
      message.error("Name cannot be empty.");
      return;
    }

    if (type === 'rename' && node) {
      setProjectData(oldTree => recursiveMap(oldTree, n => {
        if (n.key === node.key) {
          n.title = inputValue;
          if (n.data) n.data.name = inputValue;
        }
        return n;
      }));
    } else { // newFile or newFolder
      const newNode: FileNode = {
        key: uuidv4(),
        title: inputValue,
        isFolder: type === 'newFolder',
        children: type === 'newFolder' ? [] : undefined,
        data: type === 'newFile' ? { name: inputValue, seq: "", type: 'dna', circular: false, annotations: [] } : null
      };
      if (node) { // Add to a specific folder
         setProjectData(oldTree => recursiveMap(oldTree, n => {
            if (n.key === node.key) {
                n.children = [...(n.children || []), newNode];
            }
            return n;
         }));
      } else { // Add to root
         setProjectData(oldTree => [...oldTree, newNode]);
      }
    }

    setModal({ visible: false, type: 'newFile', node: null });
    setInputValue("");
  };

  const onRightClickHandler = ({ event, node }: { event: React.MouseEvent, node: any }) => {
    event.preventDefault();
    setContextMenu({ visible: true, x: event.clientX, y: event.clientY, node });
  };

  const topLevelFileMenu = (
      <Menu onClick={({ key }) => handleMenuClick(key as any, null)}>
        <Menu.Item key="newFile">New Sequence File</Menu.Item>
        <Menu.Item key="newFolder">New Folder</Menu.Item>
      </Menu>
  );

  const contextMenuItems = (node: FileNode | null) => (
      <Menu onClick={({ key }) => handleMenuClick(key as any, node)}>
        {node?.isFolder && <Menu.Item key="newFile">New Sequence File</Menu.Item>}
        {node?.isFolder && <Menu.Item key="newFolder">New Folder</Menu.Item>}
        {node?.isFolder && <Menu.Divider />}
        <Menu.Item key="rename" disabled={!node}>Rename</Menu.Item>
        <Menu.Item key="delete" danger disabled={!node}>Delete</Menu.Item>
      </Menu>
  );

  return (
    <ConfigProvider theme={{
      token: { colorBgBase: "#1f1f1f", colorBgContainer: "#141414", colorText: "#fff", colorPrimary: "#1677ff" },
      components: { Layout: { headerBg: "#181a1b", bodyBg: "#1f1f1f" } }
    }}>
      <Layout style={{ minHeight: "100vh", background: "#1f1f1f" }}>
        <Header style={{ height: 48, background: "#181a1b", display: "flex", alignItems: "center", padding: "0 24px", borderBottom: '1px solid #23272e' }}>
          <div style={{ color: "#90caf9", fontWeight: 700, fontSize: 18, marginRight: 24 }}>BioLab Workbench</div>
          <Dropdown overlay={topLevelFileMenu}><a onClick={e => e.preventDefault()} style={{color: 'white', marginRight: 20}}>File</a></Dropdown>
          <Menu mode="horizontal" theme="dark" style={{ flex: 1, background: "transparent", borderBottom: "none" }} items={["Edit", "View", "Tools", "Help"].map((k) => ({ key: k, label: k }))} />
        </Header>
        
        <Layout>
          <PanelGroup direction="horizontal" style={{ height: "calc(100vh - 48px)" }}>
            <Panel defaultSize={20} minSize={15} maxSize={35} style={{ background: "#141414", borderRight: "1px solid #23272e" }}>
              <ProjectExplorer projectData={projectData} onSelectNode={setActiveSequence} onRightClick={onRightClickHandler} />
            </Panel>
            <PanelResizeHandle style={{ width: 5, background: "#23272e", cursor: "col-resize" }} />
            <Panel minSize={30}>
               <Content style={{ height: '100%', display: 'flex', flexDirection: 'column', background: '#1f1f1f' }}>
                {activeSequence ? <BioSequenceViewer {...activeSequence} /> : <div style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center" }}><Empty description="Select a sequence file to view" /></div>}
              </Content>
            </Panel>
            <PanelResizeHandle style={{ width: 5, background: "#23272e", cursor: "col-resize" }} />
            <Panel defaultSize={20} minSize={15} maxSize={35} style={{ background: "#141414", borderLeft: "1px solid #23272e" }}>
               <SequenceInspector sequence={activeSequence} />
            </Panel>
          </PanelGroup>
        </Layout>
      </Layout>

      <Dropdown
        overlay={contextMenuItems(contextMenu.node)}
        open={contextMenu.visible}
        onOpenChange={(flag) => !flag && setContextMenu({ ...contextMenu, visible: false })}
        trigger={['contextMenu']}
      >
        <div style={{ position: 'fixed', top: contextMenu.y, left: contextMenu.x }} />
      </Dropdown>

      <Modal
        title={modal.type === 'rename' ? 'Rename Item' : (modal.type === 'newFolder' ? 'New Folder' : 'New File')}
        open={modal.visible}
        onOk={handleModalOk}
        onCancel={() => setModal({ visible: false, type: 'newFile', node: null })}
        destroyOnClose
      >
        <Input
          placeholder="Enter name"
          defaultValue={modal.type === 'rename' ? inputValue : ''}
          onChange={(e) => setInputValue(e.target.value)}
          onPressEnter={handleModalOk}
          autoFocus
        />
      </Modal>

    </ConfigProvider>
  );
}

export default App;