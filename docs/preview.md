# 后台图纸预览

`cad_preview` 通过共享后端导出实际图纸快照，返回 PNG 图片内容及 PNG、SVG、DXF 和 metadata.json 文件路径。包括图纸尚未保存的几何内容，不读取屏幕像素。

```text
Codex / MCP cad_preview
  → 共享业务核心（调度、文档 ID、执行记录、跨进程锁）
  → CADBackend.export_snapshot(document_id, path)
  → 兼容 COM 后端 Document.Export(..., "DXF", selectionSet)
  → 共享 ezdxf + Matplotlib Agg 渲染器
  → PNG / SVG / DXF / metadata.json
```

AutoCAD、ZWCAD、GstarCAD、BricsCAD 使用同一个后端方法，没有按品牌分支或独立中望实现。未来原生/RPC 后端只需实现快照契约，继续复用渲染器。

## 调用

1. `cad_connect` 连接已运行的 CAD。
2. `cad_documents(action="list")` 取得目标 document_id。
3. `cad_preview(document_id="...", width=1600, height=1200, theme="dark")`。

可选 `output_dir` 必须是绝对路径；每次在其下创建唯一结果目录，不覆盖旧结果。默认存入当前用户的 CADBridge 状态目录。`layout_name` 默认为 `Model`，可指定 DXF 内存在的布局名称。宽高范围为 256–4096 像素，theme 支持 dark/light。

独立验收脚本只针对已打开的指定图纸运行，不会创建或打开图纸：

```powershell
.venv\Scripts\python.exe scripts\preview_live.py '目标图纸.dwg'
```

## 执行与验证

- 通过绑定的文档对象导出，无需将它设为活动图纸，不调用截图、SendCommand、SaveAs、Zoom 或窗口输入。
- 只创建临时命名选择集；在 finally 中删除集合，保留集合内的实体。
- 记录导出前后名称、路径、模型空间实体数量、活动图纸名称及 context_unchanged。它是状态核验，不是数据库级内容一致性证明；外部用户操作仍可能并发发生。
- CAD 有活动命令时拒绝导出；Export 不支持或失败时返回错误，不自动降级为电脑操控。
- 返回图片以 MCP ImageContent 提供，工具文本与 structuredContent 包含文件路径和核验元数据。

2026-11-10 在 ZWCAD 2026 教育版验证：现有住宅草图的 206 个实体导出、1600×1200 PNG 与 SVG 生成、MCP 图片返回成功；目标图纸非活动状态时也已成功导出。其他三个 CAD 保留同一兼容接口路径，尚无实机验收。

## 画面含义

这是 **DXF 二维几何渲染**，可用于检查平面布局、文字、图层、颜色、块和尺寸。它不是 CAD 原生视口、打印预览或施工出图。字体、SHX、厂商代理对象、外部参照和复杂三维内容可能存在差异；metadata 中列出 fidelity、limitations 和 skipped。隐藏实体/图层也可能出现在 skipped 中，不代表发生渲染故障。

接口依据：[COM Export](https://help.autodesk.com/cloudhelp/2026/ENU/AutoCAD-ActiveX-Reference/files/GUID-893F1711-3591-4DDC-8D27-DF91052F5E5A.htm)、[ezdxf 绘图后端](https://ezdxf.readthedocs.io/en/stable/addons/drawing.html)。
