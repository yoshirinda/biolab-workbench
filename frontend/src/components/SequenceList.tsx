import React, { useEffect, useState } from 'react';
import { Table, Button, Upload, message, Tooltip, Space, Tag, Dropdown, Modal, Input, Form } from 'antd';
import { 
  UploadOutlined, 
  DeleteOutlined, 
  CopyOutlined, 
  ScissorOutlined,
  FileTextOutlined,
  EditOutlined,
  MoreOutlined
} from '@ant-design/icons';
import { ProjectNode, Sequence } from '../types/biolab';
import { getProjectDetails, uploadSequences, deleteSequence } from '../api';

interface SequenceListProps {
  projectPath: string | null;
  onSelectSequence: (sequence: Sequence | null) => void;
}

const SequenceList: React.FC<SequenceListProps> = ({ projectPath, onSelectSequence }) => {
  const [loading, setLoading] = useState(false);
  const [projectData, setProjectData] = useState<ProjectNode | null>(null);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  
  // Rename state
  const [isRenameModalVisible, setIsRenameModalVisible] = useState(false);
  const [renameTarget, setRenameTarget] = useState<Sequence | null>(null);
  const [renameForm] = Form.useForm();

  const loadProject = async () => {
    if (!projectPath) return;
    setLoading(true);
    try {
      const data = await getProjectDetails(projectPath);
      setProjectData(data);
      // If previously selected sequence is gone, deselect
      onSelectSequence(null); 
    } catch (error) {
      message.error('Failed to load sequences');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadProject();
    setSelectedRowKeys([]);
  }, [projectPath]);

  const handleUpload = async (file: File) => {
    if (!projectPath) return false;
    // Allow more extensions
    const allowedExtensions = ['.fasta', '.fa', '.gb', '.gbk', '.dna', '.txt'];
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
    
    // Optional client-side validation, but backend handles parsing
    
    try {
      setLoading(true);
      await uploadSequences(file, projectPath);
      message.success('Uploaded successfully');
      loadProject();
      return false; // Prevent auto upload
    } catch (error: any) {
      message.error(error.message || 'Upload failed');
      return false;
    } finally {
        setLoading(false);
    }
  };

  const handleDelete = async (ids?: string[]) => {
    const targets = ids || selectedRowKeys as string[];
    if (!projectPath || targets.length === 0) return;
    
    Modal.confirm({
      title: `Delete ${targets.length} sequence(s)?`,
      content: 'This cannot be undone.',
      okType: 'danger',
      onOk: async () => {
        try {
          setLoading(true);
          for (const key of targets) {
            await deleteSequence(projectPath, key);
          }
          message.success('Deleted sequences');
          setSelectedRowKeys([]);
          loadProject();
        } catch (error) {
          message.error('Delete failed');
        } finally {
          setLoading(false);
        }
      }
    });
  };

  const handleRename = async (values: any) => {
    if (!projectPath || !renameTarget) return;
    try {
      const response = await fetch(`/api/sequences/${projectPath}/${renameTarget.id}/rename`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ new_name: values.new_name })
      });
      
      if (!response.ok) {
          const err = await response.json();
          throw new Error(err.message || 'Rename failed');
      }
      
      message.success('Renamed successfully');
      setIsRenameModalVisible(false);
      loadProject();
    } catch (error: any) {
      message.error(error.message);
    }
  };

  const columns = [
    {
      title: 'Name',
      dataIndex: 'id',
      key: 'id',
      sorter: (a: Sequence, b: Sequence) => a.id.localeCompare(b.id),
      render: (text: string, record: Sequence) => (
        <span><FileTextOutlined style={{ marginRight: 8 }} />{text}</span>
      )
    },
    {
      title: 'Type',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => (
        <Tag color={type === 'protein' ? 'blue' : 'green'}>{type}</Tag>
      )
    },
    {
      title: 'Length',
      dataIndex: 'length',
      key: 'length',
      sorter: (a: Sequence, b: Sequence) => a.length - b.length,
      render: (len: number) => len.toLocaleString() + ' bp'
    },
    {
      title: 'Description',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true,
    },
    {
      title: 'Features',
      dataIndex: 'features',
      key: 'features',
      render: (features: any[]) => features ? features.length : 0
    },
    {
      title: 'Action',
      key: 'action',
      render: (_: any, record: Sequence) => (
        <Dropdown menu={{ 
            items: [
                { 
                    key: 'rename', 
                    label: 'Rename', 
                    icon: <EditOutlined />, 
                    onClick: (e) => {
                        e.domEvent.stopPropagation();
                        setRenameTarget(record);
                        renameForm.setFieldsValue({ new_name: record.id });
                        setIsRenameModalVisible(true);
                    }
                },
                { 
                    key: 'delete', 
                    label: 'Delete', 
                    icon: <DeleteOutlined />, 
                    danger: true, 
                    onClick: (e) => {
                        e.domEvent.stopPropagation();
                        handleDelete([record.id]);
                    }
                }
            ] 
        }} trigger={['click']}>
           <Button type="text" icon={<MoreOutlined />} onClick={e => e.stopPropagation()} />
        </Dropdown>
      ),
    }
  ];

  const rowSelection = {
    selectedRowKeys,
    onChange: (keys: React.Key[], selectedRows: Sequence[]) => {
      setSelectedRowKeys(keys);
    },
    type: 'checkbox' as const
  };

  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      <div style={{ padding: '8px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Upload 
            beforeUpload={handleUpload} 
            showUploadList={false}
            disabled={!projectPath}
            multiple // Allow multiple files
            fileList={[]} // Controlled to empty
          >
            <Button icon={<UploadOutlined />} disabled={!projectPath}>Import</Button>
          </Upload>
          <Button 
            icon={<DeleteOutlined />} 
            danger 
            disabled={selectedRowKeys.length === 0}
            onClick={() => handleDelete()}
          >
            Delete
          </Button>
        </Space>
        <div>
           {projectData ? `${projectData.sequences?.length || 0} items` : ''}
        </div>
      </div>

      <div style={{ flex: 1, overflow: 'auto' }}>
        <Table
          dataSource={projectData?.sequences || []}
          columns={columns}
          rowKey="id"
          size="small"
          loading={loading}
          rowSelection={rowSelection}
          pagination={false}
          onRow={(record) => ({
            onClick: () => {
              onSelectSequence(record);
            },
            onDoubleClick: () => {
               // Could open in new tab or dedicated edit mode
               onSelectSequence(record);
            },
            onContextMenu: (event) => {
               // Optional: Native context menu support could go here
            }
          })}
        />
      </div>

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

export default SequenceList;
