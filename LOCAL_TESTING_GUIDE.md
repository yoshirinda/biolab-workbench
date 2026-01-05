# 本地测试指南

本指南将帮助你测试新创建的重构代码。

---

## 快速开始

### 1. 启动应用

```bash
cd /mnt/e/Kun/wsl/biolab/biolab-workbench

# 激活虚拟环境（如果有）
# source venv/bin/activate

# 启动Flask应用
python run.py
```

应用默认会在 `http://localhost:5000` 启动。

---

## 测试新的后端API

### 选项1: 使用curl命令测试

```bash
# 测试获取所有项目
curl -X GET http://localhost:5000/api/projects

# 测试创建项目
curl -X POST http://localhost:5000/api/projects \
  -H "Content-Type: application/json" \
  -d '{"name": "测试项目", "description": "这是一个测试项目"}'

# 测试获取项目详情
curl -X GET http://localhost:5000/api/projects/测试项目

# 测试删除项目
curl -X DELETE http://localhost:5000/api/projects/测试项目
```

### 选项2: 使用Postman或类似工具

1. 打开Postman
2. 创建新请求
3. 设置URL: `http://localhost:5000/api/projects`
4. 选择方法: GET/POST/PUT/DELETE
5. 发送请求

### 选项3: 使用Python测试脚本

创建文件 `test_api.py`:

```python
import requests
import json

BASE_URL = "http://localhost:5000/api"

def test_projects_api():
    # 测试获取所有项目
    print("1. 测试获取所有项目...")
    response = requests.get(f"{BASE_URL}/projects")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()
    
    # 测试创建项目
    print("2. 测试创建项目...")
    data = {
        "name": "API测试项目",
        "description": "通过API创建的测试项目"
    }
    response = requests.post(f"{BASE_URL}/projects", json=data)
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()
    
    # 测试获取项目详情
    print("3. 测试获取项目详情...")
    response = requests.get(f"{BASE_URL}/projects/API测试项目")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    print()

if __name__ == "__main__":
    test_projects_api()
```

运行:
```bash
python test_api.py
```

---

## 测试新的前端库

### 方法1: 创建测试HTML页面

创建文件 `test_frontend.html`:

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>前端库测试</title>
    <link rel="stylesheet" href="/static/css/ui-components.css">
</head>
<body>
    <div style="padding: 20px;">
        <h1>前端库测试</h1>
        
        <div style="margin: 20px 0;">
            <h2>1. 测试消息提示</h2>
            <button onclick="testMessages()">测试消息</button>
        </div>
        
        <div style="margin: 20px 0;">
            <h2>2. 测试加载指示器</h2>
            <button onclick="testLoading()">测试加载</button>
        </div>
        
        <div style="margin: 20px 0;">
            <h2>3. 测试对话框</h2>
            <button onclick="testDialogs()">测试对话框</button>
        </div>
        
        <div style="margin: 20px 0;">
            <h2>4. 测试API客户端</h2>
            <button onclick="testAPI()">测试API</button>
        </div>
        
        <div style="margin: 20px 0;">
            <h2>5. 测试组件</h2>
            <div id="testComponent"></div>
            <button onclick="testComponent()">测试组件</button>
        </div>
    </div>

    <!-- 引入前端库 -->
    <script src="/static/js/lib/ui-helpers.js"></script>
    <script src="/static/js/lib/api-client.js"></script>
    <script src="/static/js/lib/base-component.js"></script>

    <script>
        // 测试消息提示
        function testMessages() {
            UIHelpers.showSuccess('这是成功消息');
            setTimeout(() => UIHelpers.showError('这是错误消息'), 500);
            setTimeout(() => UIHelpers.showWarning('这是警告消息'), 1000);
            setTimeout(() => UIHelpers.showInfo('这是信息消息'), 1500);
        }
        
        // 测试加载指示器
        function testLoading() {
            UIHelpers.showLoading(true, '加载中...');
            setTimeout(() => {
                UIHelpers.showLoading(false);
                UIHelpers.showSuccess('加载完成');
            }, 2000);
        }
        
        // 测试对话框
        async function testDialogs() {
            const confirmed = await UIHelpers.confirm('确定要执行这个操作吗？', '确认');
            if (confirmed) {
                const name = await UIHelpers.prompt('请输入你的名字', '输入');
                if (name) {
                    UIHelpers.showSuccess(`你好，${name}！`);
                }
            }
        }
        
        // 测试API客户端
        async function testAPI() {
            const client = new APIClient('/api');
            try {
                UIHelpers.showLoading(true);
                const projects = await client.get('/projects');
                UIHelpers.showLoading(false);
                UIHelpers.showSuccess(`获取到 ${projects.length} 个项目`);
                console.log('项目列表:', projects);
            } catch (error) {
                UIHelpers.showLoading(false);
                UIHelpers.showError('API调用失败: ' + error.message);
            }
        }
        
        // 测试组件
        function testComponent() {
            class TestComponent extends BaseComponent {
                render() {
                    this.container.innerHTML = `
                        <div style="padding: 20px; background: #f0f0f0; border-radius: 8px;">
                            <h3>测试组件</h3>
                            <p>这是一个基于BaseComponent的测试组件</p>
                            <button class="btn btn-primary" id="testBtn">点击测试</button>
                        </div>
                    `;
                    
                    this.find('#testBtn').addEventListener('click', () => {
                        this.showSuccess('组件按钮被点击了！');
                    });
                }
            }
            
            const component = new TestComponent('testComponent');
            component.init();
        }
    </script>
</body>
</html>
```

将此文件放在 `app/templates/` 目录，然后访问对应的路由。

### 方法2: 在浏览器控制台测试

1. 打开应用: `http://localhost:5000`
2. 打开浏览器开发者工具 (F12)
3. 在控制台输入:

```javascript
// 测试消息
UIHelpers.showSuccess('测试成功');

// 测试加载
UIHelpers.showLoading(true);
setTimeout(() => UIHelpers.showLoading(false), 2000);

// 测试API
const client = new APIClient('/api');
client.get('/projects').then(data => console.log(data));

// 测试确认对话框
UIHelpers.confirm('测试确认', '确认').then(result => console.log(result));
```

---

## 检查新API是否正常工作

### 步骤1: 确认API蓝图已注册

检查 `app/__init__.py` 或 `run.py` 是否包含:

```python
from app.api import api_bp
app.register_blueprint(api_bp)
```

如果没有，需要添加这段代码。

### 步骤2: 测试API端点

```bash
# 应该返回成功
curl http://localhost:5000/api/projects

# 如果返回404，说明蓝图没有正确注册
# 如果返回500，检查日志看具体错误
```

### 步骤3: 查看日志

启动应用时会显示日志，查看是否有错误:

```bash
python run.py
```

输出应该类似:
```
 * Running on http://127.0.0.1:5000
 * Debugger is active!
```

---

## 常见问题排查

### 问题1: ImportError

**错误**: `ModuleNotFoundError: No module named 'app.api'`

**解决**:
1. 确认 `app/api/__init__.py` 存在
2. 确认文件中没有语法错误
3. 重启应用

### 问题2: 404 Not Found

**错误**: 访问 `/api/projects` 返回404

**解决**:
1. 检查蓝图是否已注册
2. 检查URL前缀是否正确
3. 查看Flask启动日志中的路由列表

### 问题3: 前端库未加载

**错误**: `UIHelpers is not defined`

**解决**:
1. 确认HTML中正确引入了JS文件:
   ```html
   <script src="/static/js/lib/ui-helpers.js"></script>
   ```
2. 检查浏览器网络面板，确认JS文件加载成功
3. 检查浏览器控制台是否有JS错误

### 问题4: CSS样式不生效

**错误**: UI组件没有样式

**解决**:
1. 确认HTML中引入了CSS:
   ```html
   <link rel="stylesheet" href="/static/css/ui-components.css">
   ```
2. 清除浏览器缓存 (Ctrl+Shift+R)
3. 检查CSS文件路径是否正确

---

## 验证重构效果

### 对比测试

#### 旧API测试
```bash
# 测试旧的API（如果还存在）
curl http://localhost:5000/sequence/projects
```

#### 新API测试
```bash
# 测试新的API
curl http://localhost:5000/api/projects
```

**观察差异**:
- 新API响应格式更统一
- 错误处理更完善
- 代码更简洁

---

## 性能测试

### 测试响应时间

```bash
# 使用time命令
time curl http://localhost:5000/api/projects

# 或使用Apache Bench
ab -n 100 -c 10 http://localhost:5000/api/projects
```

---

## 下一步

测试通过后，你可以:

1. ✅ 在应用中集成新的API
2. ✅ 使用新的前端库替换旧代码
3. ✅ 逐步迁移其他功能到新架构
4. ✅ 添加更多测试用例

---

## 需要帮助？

查看这些文档:
- [`CODE_QUALITY_REPORT.md`](CODE_QUALITY_REPORT.md) - 问题详情
- [`REFACTORING_PLAN.md`](REFACTORING_PLAN.md) - 重构计划
- [`REFACTORING_EXAMPLE.md`](REFACTORING_EXAMPLE.md) - 使用示例

祝测试顺利！🚀