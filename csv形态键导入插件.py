
bl_info = {
    "name": "从 CSV 导入形态键动画",
    "author": "GPT-o1",
    "version": (1, 3),
    "blender": (4, 20, 0),
    "location": "3D视图 > 侧栏(N) > 动画导入",
    "description": "从 CSV 文件导入表情动画到所选对象",
    "warning": "",
    "doc_url": "",
    "category": "Animation",
}

import bpy
import csv
import os

# ------------------------------------------------------------------------
# 当布尔切换时更新形态键范围的函数
# ------------------------------------------------------------------------
def update_shape_key_range(self, context):
    obj = context.active_object
    if obj and obj.type == 'MESH' and obj.data.shape_keys:
        for kb in obj.data.shape_keys.key_blocks:
            if self.shape_key_range_toggle:
                kb.slider_min = -10.0
                kb.slider_max = 10.0
            else:
                kb.slider_min = 0.0
                kb.slider_max = 1.0

# ------------------------------------------------------------------------
# 核心操作类 (Operator)
# ------------------------------------------------------------------------
class OBJECT_OT_ImportShapeKeyCSV(bpy.types.Operator):
    """从 CSV 文件导入表情动画"""
    bl_idname = "object.import_shape_key_csv"
    bl_label = "导入 CSV 动画"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        # 仅在选择了对象时才可执行
        return context.active_object is not None

    def execute(self, context):
        scene = context.scene
        obj = context.active_object
        filepath = scene.shape_key_csv_path

        # --- 1. 验证输入 ---
        if not obj:
            self.report({'ERROR'}, "未选择任何活动对象。")
            return {'CANCELLED'}

        if obj.type != 'MESH':
            self.report({'ERROR'}, "所选对象不是网格类型(MESH)。")
            return {'CANCELLED'}

        shape_key_data = obj.data.shape_keys
        if not shape_key_data:
            self.report({'ERROR'}, "所选对象没有形态键。")
            return {'CANCELLED'}

        if not filepath or not os.path.exists(filepath):
            self.report({'ERROR'}, f"在指定路径未找到 CSV 文件: {filepath}")
            return {'CANCELLED'}

        # --- 2. 读取CSV文件 ---
        try:
            with open(filepath, 'r', newline='', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                # 读取表头 (形态键名称)
                header = [h.strip() for h in next(reader)]
                # 读取所有数据行
                data_rows = list(reader)
        except Exception as e:
            self.report({'ERROR'}, f"读取 CSV 文件失败: {e}")
            return {'CANCELLED'}

        if not header or not data_rows:
            self.report({'ERROR'}, "CSV 文件为空或无效。")
            return {'CANCELLED'}

        # --- 3. 清除现有动画并映射CSV列到模型的形态键 ---
        if shape_key_data.animation_data and shape_key_data.animation_data.action:
            fcurves = shape_key_data.animation_data.action.fcurves
            curves_to_remove = []
            
            # 查找所有与CSV表头中名称匹配的F-Curves
            for key_name in header:
                target_data_path = f'key_blocks["{key_name}"].value'
                for curve in fcurves:
                    if curve.data_path == target_data_path:
                        curves_to_remove.append(curve)
            
            for curve in curves_to_remove:
                fcurves.remove(curve)
        
        # 创建一个映射列表，格式为: (形态键对象, CSV中的列索引)
        mapped_keys = []
        for i, key_name in enumerate(header):
            if key_name in shape_key_data.key_blocks:
                sk = shape_key_data.key_blocks[key_name]
                mapped_keys.append((sk, i))
            else:
                print(f"警告: CSV 中的形态键 '{key_name}' 未在对象 '{obj.name}' 上找到。")

        if not mapped_keys:
            self.report({'ERROR'}, "CSV 与对象之间未找到匹配的形态键。")
            return {'CANCELLED'}

        # --- 4. 逐帧设置关键帧 ---
        start_frame = scene.frame_start
        
        for frame_index, row in enumerate(data_rows):
            current_frame = start_frame + frame_index
            if current_frame > scene.frame_end:
                scene.frame_end = current_frame

            for sk, col_index in mapped_keys:
                try:
                    value = float(row[col_index])
                    sk.value = value
                    sk.keyframe_insert(data_path='value', frame=current_frame)
                except (ValueError, IndexError) as e:
                    self.report({'WARNING'}, f"跳过在帧 {current_frame}、列 {header[col_index]} 的无效数据: {e}")
                    continue

        self.report({'INFO'}, f"成功导入了 {len(data_rows)} 帧动画，并应用到 {len(mapped_keys)} 个形态键上。")
        return {'FINISHED'}


# ------------------------------------------------------------------------
# UI 面板类 (Panel)
# ------------------------------------------------------------------------
class VIEW3D_PT_ShapeKeyCSVImporter(bpy.types.Panel):
    """在3D视图侧边栏创建一个面板"""
    bl_label = "形态键 CSV 导入器"
    bl_idname = "OBJECT_PT_shape_key_csv_importer"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'CSV表情动画导入'  # 侧边栏的Tab名称

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        box = layout.box()
        box.label(text="导入设置", icon='SETTINGS')
        
        # CSV 文件路径
        box.prop(scene, "shape_key_csv_path")
        
        # 导入按钮
        row = box.row()
        row.scale_y = 1.5
        row.operator(OBJECT_OT_ImportShapeKeyCSV.bl_idname, icon='IMPORT')
        
        layout.separator()

        # 切换形态键数值范围
        toggle_box = layout.box()
        toggle_box.label(text="形态键值范围切换", icon='KEY_HLT')
        toggle_box.prop(scene, "shape_key_range_toggle", text="切换范围")
        
        layout.separator()
        
        # 使用说明
        info_box = layout.box()
        info_box.label(text="使用说明:", icon='INFO')
        col = info_box.column(align=True)
        col.label(text="1. 选择要赋予表情动画的模型")
        col.label(text="2. 选择 CSV 动画文件")
        col.label(text="3. 点击『导入 CSV 动画』")

        col.separator()
        
        col.label(text="介绍：")
        col.label(text="— CSV的每一行代表一帧")
        col.label(text="— CSV的标题行为形态键名")


# ------------------------------------------------------------------------
# 注册与注销
# ------------------------------------------------------------------------
classes = (
    OBJECT_OT_ImportShapeKeyCSV,
    VIEW3D_PT_ShapeKeyCSVImporter,
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.Scene.shape_key_csv_path = bpy.props.StringProperty(
        name="CSV 文件",
        description="包含形态键动画数据的 CSV 文件路径",
        default="",
        maxlen=1024,
        subtype='FILE_PATH'
    )
    
    bpy.types.Scene.shape_key_range_toggle = bpy.props.BoolProperty(
        name="扩展范围",
        description="形态键下限和上限是 0~1 或是 -10~10",
        default=False,
        update=update_shape_key_range
    )

def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    del bpy.types.Scene.shape_key_csv_path
    del bpy.types.Scene.shape_key_range_toggle

if __name__ == "__main__":
    register()
