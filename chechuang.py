import os
import sys
from pathlib import Path
import requests
import base64
import json
import time
import tempfile

class ShapeAnalyzer:
    """轴类零件形状识别专家(动态)"""
    
    def __init__(self):
        # API配置
        self.config = {
            "model": "gemini-2.5-flash-preview-04-17-nothink",
            "api_key": "sk-0sjpjpifXG8PIyGjE739350eE69b4b72Ad4fCdA96d076dA2",
            "base_url": "https://aihubmix.com/v1",
            "timeout": 120
        }
        
        self.headers = {
            "Authorization": f"Bearer {self.config['api_key']}",
            "Content-Type": "application/json"
        }
        
        # DIN 933标准粗牙螺纹螺距表
        self.din933_coarse_pitches_mm = {
            1: 0.25, 1.1: 0.25, 1.2: 0.25, 1.4: 0.3, 1.6: 0.35, 1.8: 0.35, 2: 0.4,
            2.2: 0.45, 2.5: 0.45, 3: 0.5, 3.5: 0.6, 4: 0.7, 5: 0.8, 6: 1.0, 7: 1.0,
            8: 1.25, 10: 1.5, 12: 1.75, 14: 2.0, 16: 2.0, 18: 2.5, 20: 2.5, 22: 2.5,
            24: 3.0, 27: 3.0, 30: 3.5, 33: 3.5, 36: 4.0, 39: 4.0, 42: 4.5, 45: 4.5,
            48: 5.0, 52: 5.0, 56: 5.5, 60: 5.5, 64: 6.0, 68: 6.0
        }
        
        # 添加system_prompt
        self.system_prompt = """你是一位专业的机械工程师，专注于识别轴类零件的几何特征。请分析工程图纸并以指定的JSON格式返回结果。

分析图纸时，请遵循以下步骤：
1. 识别图纸的不同视图并分析它们之间的关系：
   - 主视图（正视图）：显示零件的最大直径（对应长度和宽度）
   - 侧视图：必须从这里获取零件的厚度（轴向尺寸）
   - 剖视图：显示内部结构

2. 从四个方向系统地测量尺寸：
   - 上方：查看从顶部标注的尺寸
   - 下方：查看从底部标注的尺寸
   - 左侧：查看从左侧标注的尺寸
   - 右侧：查看从右侧标注的尺寸
   特别注意：
   - 厚度必须从侧视图中寻找，通常在图形的上方或下方有明确的尺寸标注
   - 直径(Ø)标注通常在主视图中，这就是长度和宽度的值

3. 测量基本尺寸（注意轴类零件的回转特性）：
   - 直径：零件的最大直径，同时作为长度和宽度
   - 厚度：零件的轴向尺寸，必须从侧视图中获取
   - 在主视图中寻找带有直径符号(Ø)的尺寸标注，这就是长度和宽度的值
   - 注意：对于轴类零件，长度=宽度=直径，厚度是独立的轴向尺寸

4. 几何特征分析（特别注意轴类零件的回转特性）：
   - 平面：端面、台肩端面等平整表面
   - 曲面：倒角、圆角过渡等非平面表面
   - 圆柱面：外圆柱面、阶梯轴的台阶面、内孔壁等
   - 圆锥面：锥形过渡、锥孔等
   - 螺旋面：螺纹区域

5. 孔特征分析：
   - 识别中心孔、通孔、台阶孔等
   - 注意区分同轴孔和偏心孔
   - 螺纹孔的规格和位置

6. 铣削特征分析（特别关注非旋转对称的特征）：
   - 槽（沟槽/键槽）：识别所有的槽特征，包括轴向槽、径向槽和环形槽
   - 对于每个槽，记录以下信息：
     * 槽的类型（轴向槽、径向槽、环形槽等）
     * 槽的长度：槽在其主要方向上的尺寸
     * 槽的宽度：槽在垂直于长度方向上的尺寸
     * 槽的深度：槽从表面到底部的深度
     * 槽的位置：相对于零件坐标系的位置描述
     * 槽的体积：长×宽×深的计算结果
   - 平面切削面：非旋转对称的平面切削特征
   - 铣削孔：非中心轴线上的孔，通常是铣削加工的

7. 螺纹特征分析（特别关注螺纹规格和长度）:
   - 识别图纸中所有螺纹特征及其位置
   - 明确识别螺纹规格，如M8、M10等，特别注意识别符号"M"后面的数字
   - 精确测量螺纹的长度
   - 对于外螺纹，识别其直径和长度
   - 对于内螺纹，识别其内径和深度
   - 记录螺纹的位置和方向（轴向或径向）

8. 表面粗糙度分析（特别是对于精加工和磨削需求）：
   - 查找图纸上的表面粗糙度符号，通常标记为"Ra"
   - 特别关注Ra≤0.8的表面，这些通常需要磨削加工
   - 测量所有标记了Ra≤0.8的表面的长度总和
   - 记录最严格的表面粗糙度要求及其对应的表面位置
   - 注意：常用的标准表面粗糙度值包括Ra 12.5, 6.3, 3.2, 1.6, 0.8, 0.4，最低不会小于Ra 0.4

9. 计算重要数据：
   - 毛坯体积：基于圆柱体计算 π×(直径/2)²×厚度
   - 净体积：考虑所有去除材料后的体积
   - 表面积：所有表面积之和
   - 材料去除率：(毛坯体积-净体积)/毛坯体积×100%
   - 槽特征的总体积：所有槽特征体积之和
   - Ra≤0.8表面的长度：需要精密磨削的表面长度总和

重要提示：
- 轴类零件的尺寸关系：长度=宽度=直径
- 厚度必须从侧视图中寻找，通常在图形的上方或下方有明确的尺寸标注
- 尺寸信息格式为"直径x直径x厚度 mm"
- 如无法确定精确值，请提供合理的估计值而非"未知"
- 对于模糊或不确定的特征，应基于轴类零件加工的特点做出判断
- 确保返回的每个字段都有数值，尤其是几何特征数量和表面粗糙度相关的长度
- 表面粗糙度Ra值必须在合理范围内：0.4, 0.8, 1.6, 3.2, 6.3, 12.5，不能低于0.4
- 对于螺纹，必须明确识别规格（如M8、M10等）和长度

请严格按照以下JSON格式返回结果，不要添加任何额外说明或思考过程：
{
    "零件名称": "根据图纸判断的零件名称",
    "所有面的数量": "总面数",
    "平面的数量": "平面数",
    "曲面的数量": "曲面数",
    "圆柱面数量": "圆柱面数",
    "圆锥面数量": "圆锥面数",
    "螺旋面数量": "螺旋面数",
    "孔的数量": "孔总数",
    "尺寸信息(mm)": "直径x直径x厚度 mm",
    "长度(mm)": "直径值",
    "宽度(mm)": "直径值（等于长度）",
    "高度(mm)": "从侧视图获取的厚度值",
    "表面积(mm²)": "表面积值",
    "毛坯体积(mm³)": "毛坯体积值",
    "净体积(mm³)": "净体积值",
    "材料去除率(%)": "材料去除率值",
    "槽的数量": "槽总数",
    "槽特征": [
        {
            "类型": "轴向槽/径向槽/环形槽",
            "长度(mm)": "槽长度值",
            "宽度(mm)": "槽宽度值",
            "深度(mm)": "槽深度值",
            "位置": "槽位置描述",
            "体积(mm³)": "槽体积值"
        }
    ],
    "槽特征总体积(mm³)": "所有槽特征体积之和",
    "螺纹规格": "如M8、M10等，仅返回数字部分",
    "螺纹长度(mm)": "螺纹长度值",
    "最严格表面粗糙度": "图纸中出现的最小Ra值（在0.4到12.5范围内）",
    "需要磨削的表面": "需要磨削的表面描述",
    "Ra≤0.8的表面长度(mm)": "需要精密磨削的表面长度总和"
}"""

    def _convert_pdf_to_png(self, pdf_path):
        """将PDF文件转换为PNG图像
        
        Args:
            pdf_path: PDF文件路径
            
        Returns:
            str: 转换后的PNG文件路径
        """
        try:
            # 尝试导入pdf2image库
            try:
                from pdf2image import convert_from_path
            except ImportError:
                print("警告: 缺少pdf2image库，请使用 'pip install pdf2image' 安装")
                print("然后还需要安装poppler，Windows用户可以从这里下载：https://github.com/oschwartz10612/poppler-windows/releases")
                print("Linux用户可以使用 'sudo apt-get install poppler-utils'")
                print("Mac用户可以使用 'brew install poppler'")
                raise ImportError("缺少pdf2image库，无法处理PDF文件")
            
            # 输出到 uploads 目录，文件名与PDF一致
            uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
            os.makedirs(uploads_dir, exist_ok=True)
            output_path = os.path.join(uploads_dir, Path(pdf_path).stem + ".png")
            
            # 转换PDF的第一页为PNG
            print(f"正在将PDF文件转换为PNG: {pdf_path}")
            images = convert_from_path(pdf_path, dpi=300, first_page=1, last_page=1)
            if images:
                images[0].save(output_path, 'PNG')
                print(f"PDF成功转换为PNG: {output_path}")
                return output_path
            else:
                raise Exception("PDF转换失败，未生成图像")
                
        except Exception as e:
            print(f"PDF转换失败: {str(e)}")
            raise

    def _encode_image(self, image_path: str) -> str:
        """将图像文件转换为base64编码"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def analyze_shape(self, image_path: str) -> dict:
        """分析图像并返回识别结果
        
        Args:
            image_path: 图像文件的路径(支持PNG和PDF)
            
        Returns:
            dict: 包含识别结果的字典，格式为
            {
                "status": "success" 或 "error",
                "shape_features": JSON字符串或错误消息,
                "P_luowen": 螺纹螺距,
                "L_luowen": 螺纹长度
            }
        """
        max_retries = 3  # 最大重试次数
        retry_count = 0
        retry_delay = 5  # 重试间隔时间(秒)
        
        while retry_count < max_retries:
            try:
                # 检查文件是否存在
                if not Path(image_path).exists():
                    raise FileNotFoundError(f"文件不存在: {image_path}")
                
                # 检查文件类型，如果是PDF则转换为PNG
                actual_image_path = image_path
                is_pdf = Path(image_path).suffix.lower() == '.pdf'
                
                if is_pdf:
                    try:
                        actual_image_path = self._convert_pdf_to_png(image_path)
                    except Exception as e:
                        raise Exception(f"PDF转换失败: {str(e)}")
                
                # 确保图像文件存在
                if not Path(actual_image_path).exists():
                    raise FileNotFoundError(f"图像文件不存在: {actual_image_path}")

                # 将图像转换为base64编码
                image_base64 = self._encode_image(actual_image_path)

                # 获取文件名去除扩展名
                file_name = Path(image_path).stem

                # 准备API请求数据
                analysis_prompt = """请仔细分析这张轴类零件工程图，提取关键特征并返回结构化数据。

具体分析步骤：

1. 首先识别零件名称和基本尺寸：
   - 检查标题栏或图纸中的文字说明确定零件名称
   - 在主视图中查找带有直径符号(Ø)的尺寸标注，这是零件的最大直径，也就是长度和宽度
   - 在侧视图中系统地查看四个方向的尺寸标注：
     * 上方：查看从顶部标注的尺寸
     * 下方：查看从底部标注的尺寸
     * 左侧：查看从左侧标注的尺寸
     * 右侧：查看从右侧标注的尺寸
   - 厚度必须从侧视图中获取，通常在图形的上方或下方有明确的尺寸标注
   - 注意：长度=宽度=直径，厚度是独立的轴向尺寸

2. 详细分析几何特征（遵循轴类零件的回转特性）：
   - 平面：端面、台肩面等平整表面
   - 曲面：倒角、圆角过渡等非平面表面
   - 圆柱面：外圆柱面、内孔壁等圆柱形表面
   - 圆锥面：锥形表面、锥度孔等
   - 螺旋面：螺纹相关表面
   - 所有面总数 = 平面 + 曲面 + 圆柱面 + 圆锥面 + 螺旋面

3. 识别所有孔特征：
   - 中心孔：在零件中心轴线上的孔
   - 通孔：完全穿透零件的孔
   - 盲孔：不完全穿透的孔
   - 台阶孔：有多个直径的复合孔
   - 螺纹孔：内螺纹特征
   - 注意区分轴向孔和径向孔

4. 识别铣削特征（特别是非旋转对称的特征）：
   - 仔细查找所有的槽特征，如键槽、T形槽、环形槽等
   - 测量每个槽的长度、宽度和深度
   - 描述槽的位置（相对于零件的哪个部位）
   - 计算每个槽的体积（长×宽×深）
   - 区分轴向槽、径向槽和环形槽

5. 识别螺纹特征：
   - 查找图纸中所有的螺纹标记，如M8、M10等
   - 特别注意符号"M"后面的数字，这表示螺纹的公称直径
   - 仔细测量螺纹的长度
   - 对外螺纹和内螺纹都需要记录其规格和长度

6. 分析表面粗糙度要求：
   - 查找图纸上所有的表面粗糙度标记（Ra值）
   - 标准表面粗糙度值通常为Ra 12.5, 6.3, 3.2, 1.6, 0.8, 0.4（微米），不会低于Ra 0.4
   - 特别注意找出Ra=0.8或小于0.8的表面，这些表面通常需要精密磨削
   - 测量所有Ra≤0.8表面的长度总和
   - 识别图纸上的最严格表面粗糙度要求（最小Ra值）及其表面位置
   - 如果图纸中没有明确标注Ra值，请估计可能需要精密加工的表面长度

7. 计算以下数据：
   - 毛坯体积：基于圆柱体计算 π×(直径/2)²×厚度
   - 净体积：考虑所有孔、槽和其他特征后的体积
   - 表面积：所有外表面和孔内表面的面积总和
   - 材料去除率：(毛坯体积-净体积)/毛坯体积×100%
   - 槽特征的总体积：所有槽体积的总和
   - Ra≤0.8的表面长度：需要精密磨削的表面长度总和

注意：
- 长度=宽度=直径（从主视图获取）
- 厚度必须从侧视图中寻找，通常在图形的上方或下方有明确的尺寸标注
- 尺寸信息格式为"直径x直径x厚度 mm"
- 对于任何无法精确确定的值，请提供合理估计而非标记为"未知"
- 利用你的工程知识和对轴类零件的理解进行判断
- 确保表面粗糙度Ra值在标准范围内（0.4到12.5），不会低于Ra 0.4
- 对于螺纹，仅返回M后面的数字作为螺纹规格，例如对于M8，返回"8"

请严格按照以下JSON格式返回结果，不要添加任何解释或思考过程：

{
    "零件名称": "零件名称",
    "所有面的数量": "总面数（数字）",
    "平面的数量": "平面数（数字）",
    "曲面的数量": "曲面数（数字）",
    "圆柱面数量": "圆柱面数（数字）",
    "圆锥面数量": "圆锥面数（数字）",
    "螺旋面数量": "螺旋面数（数字）",
    "孔的数量": "孔总数（数字）",
    "尺寸信息(mm)": "直径x直径x厚度 mm",
    "长度(mm)": "直径值",
    "宽度(mm)": "直径值（等于长度）",
    "高度(mm)": "从侧视图获取的厚度值",
    "表面积(mm²)": "表面积值（数字）",
    "毛坯体积(mm³)": "毛坯体积值（数字）",
    "净体积(mm³)": "净体积值（数字）",
    "材料去除率(%)": "材料去除率值（数字）",
    "槽的数量": "槽总数（数字，如果没有则为0）",
    "槽特征": [
        {
            "类型": "轴向槽/径向槽/环形槽",
            "长度(mm)": "槽长度值",
            "宽度(mm)": "槽宽度值",
            "深度(mm)": "槽深度值",
            "位置": "槽位置描述",
            "体积(mm³)": "槽体积值"
        }
    ],
    "槽特征总体积(mm³)": "所有槽特征体积之和（如果没有槽则为0）",
    "螺纹规格": "仅返回M后面的数字，如8、10等（数字）",
    "螺纹长度(mm)": "螺纹长度值（数字）",
    "最严格表面粗糙度": "图纸中出现的最小Ra值（标准值：0.4, 0.8, 1.6, 3.2, 6.3或12.5）",
    "需要磨削的表面": "需要磨削的表面描述（例如：外圆柱面、端面等）",
    "Ra≤0.8的表面长度(mm)": "需要精密磨削的表面长度总和（数字，如无则为0）"
}"""

                payload = {
                    "model": self.config["model"],
                    "messages": [
                        {
                            "role": "system",
                            "content": self.system_prompt
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": analysis_prompt
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    "temperature": 0
                }

                # 调用模型API
                print(f"正在调用API分析图像，尝试次数：{retry_count + 1}/{max_retries}")
                response = requests.post(
                    f"{self.config['base_url']}/chat/completions",
                    headers=self.headers,
                    json=payload,
                    timeout=self.config["timeout"]
                )
                response.raise_for_status()
                result = response.json()
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                
                # 尝试将结果解析为JSON，如果返回的不是严格的JSON格式，则直接返回原始内容
                try:
                    # 查找内容中的JSON部分
                    import re
                    json_match = re.search(r'({[\s\S]*})', content)
                    if json_match:
                        json_str = json_match.group(1)
                        json_data = json.loads(json_str)
                        
                        # 使用文件名作为零件名称
                        json_data["零件名称"] = file_name
                        
                        # 处理螺纹数据并设置P_luowen和L_luowen
                        P_luowen = 0
                        L_luowen = 0
                        exact_thread_match = False  # 默认为未精确匹配
                        
                        # 解析螺纹规格和长度
                        if "螺纹规格" in json_data and json_data["螺纹规格"]:
                            try:
                                # 提取螺纹规格（M后面的数字）
                                thread_spec = float(json_data["螺纹规格"])
                                
                                # 查找对应的螺距
                                if thread_spec in self.din933_coarse_pitches_mm:
                                    P_luowen = self.din933_coarse_pitches_mm[thread_spec]
                                    exact_thread_match = True  # 标记为精确匹配
                                else:
                                    # 找到最接近的规格
                                    closest_spec = min(self.din933_coarse_pitches_mm.keys(), 
                                                    key=lambda x: abs(x - thread_spec))
                                    P_luowen = self.din933_coarse_pitches_mm[closest_spec]
                                    print(f"警告：未找到精确的螺纹规格")
                                    exact_thread_match = False  # 确保为未精确匹配
                            except (ValueError, TypeError):
                                # 如果无法解析螺纹规格，设置默认值
                                P_luowen = 0  # 修改为0，不使用默认值
                                exact_thread_match = False
                                print("警告：无法解析螺纹规格，螺距设为0")
                        
                        if "螺纹长度(mm)" in json_data and json_data["螺纹长度(mm)"]:
                            try:
                                # 提取螺纹长度
                                L_luowen = float(json_data["螺纹长度(mm)"])
                            except (ValueError, TypeError):
                                # 如果无法解析螺纹长度，使用高度作为默认值
                                if "高度(mm)" in json_data and json_data["高度(mm)"]:
                                    try:
                                        L_luowen = float(json_data["高度(mm)"])
                                        print("警告：无法解析螺纹长度，使用零件高度作为螺纹长度")
                                    except (ValueError, TypeError):
                                        L_luowen = 0
                                        print("警告：无法解析螺纹长度和高度，使用默认值0")
                                else:
                                    L_luowen = 0
                                    print("警告：无法解析螺纹长度和高度，使用默认值0")
                        
                        # 修正不合理的表面粗糙度值
                        if "最严格表面粗糙度" in json_data:
                            try:
                                # 将表面粗糙度值转换为浮点数
                                ra_value = float(json_data["最严格表面粗糙度"])
                                
                                # 标准粗糙度值
                                standard_ra_values = [0.4, 0.8, 1.6, 3.2, 6.3, 12.5]
                                
                                # 如果值小于0.4，将其设置为0.4
                                if ra_value < 0.4:
                                    json_data["最严格表面粗糙度"] = "0.4"
                                    print("警告：检测到不合理的表面粗糙度值，已修正为标准值Ra 0.4")
                                else:
                                    # 找到最接近的标准值
                                    closest_ra = min(standard_ra_values, key=lambda x: abs(x - ra_value))
                                    json_data["最严格表面粗糙度"] = str(closest_ra)
                            except ValueError:
                                # 如果无法转换为数字，则设置为合理的默认值
                                json_data["最严格表面粗糙度"] = "1.6"
                                print("警告：表面粗糙度值格式错误，已设置为默认值Ra 1.6")
                        
                        response_data = {
                            "status": "success", 
                            "shape_features": json.dumps(json_data, ensure_ascii=False, indent=4),
                            "P_luowen": P_luowen,
                            "L_luowen": L_luowen,
                            "exact_thread_match": exact_thread_match  # 添加精确匹配标志到返回结果
                        }
                        return response_data
                    else:
                        return {
                            "status": "success", 
                            "shape_features": content,
                            "P_luowen": 0,
                            "L_luowen": 0,
                            "exact_thread_match": False  # 默认为未精确匹配
                        }
                except json.JSONDecodeError:
                    return {
                        "status": "success", 
                        "shape_features": content,
                        "P_luowen": 0,
                        "L_luowen": 0,
                        "exact_thread_match": False  # 默认为未精确匹配
                    }
                
            except requests.exceptions.Timeout as e:
                retry_count += 1
                if retry_count < max_retries:
                    print(f"API请求超时，{retry_delay}秒后进行第{retry_count + 1}次重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避，增加重试间隔
                    continue
                else:
                    return {
                        "status": "error",
                        "message": f"API请求超时，已重试{retry_count}次: {str(e)}",
                        "P_luowen": 0,
                        "L_luowen": 0,
                        "exact_thread_match": False
                    }
            
            except (requests.exceptions.RequestException, Exception) as e:
                retry_count += 1
                if retry_count < max_retries and isinstance(e, requests.exceptions.RequestException):
                    print(f"网络请求错误，{retry_delay}秒后进行第{retry_count + 1}次重试...")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # 指数退避，增加重试间隔
                    continue
                else:
                    return {
                        "status": "error",
                        "message": f"处理过程出错: {str(e)}",
                        "P_luowen": 0,
                        "L_luowen": 0,
                        "exact_thread_match": False
                    }
            
            # 如果是临时转换的PNG文件，在完成后删除
            finally:
                if is_pdf and os.path.exists(actual_image_path) and actual_image_path != image_path:
                    try:
                        os.remove(actual_image_path)
                    except:
                        pass  # 忽略删除时的错误

    def _process_dimension_format(self, result: dict) -> dict:
        """处理尺寸信息，确保格式正确"""
        # 简化处理，直接返回原始结果
        return result

# 当直接运行该脚本时的入口点
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('使用方法: python chechuang.py <PDF文件路径>')
        print('  PDF文件路径: 要分析的PDF文件的路径')
        sys.exit(1)
    
    analyzer = ShapeAnalyzer()
    pdf_path = sys.argv[1]
    
    # 检查文件是否为PDF
    if not pdf_path.lower().endswith('.pdf'):
        print('只支持PDF文件作为输入！')
        sys.exit(1)
    
    result = analyzer.analyze_shape(pdf_path)
    
    if result["status"] == "success":
        # 生成json文件名
        json_path = pdf_path.rsplit('.', 1)[0] + '.json'
        try:
            # shape_features是json字符串
            with open(json_path, 'w', encoding='utf-8') as f:
                f.write(result["shape_features"])
            print(f"分析完成，结果已保存为: {json_path}")
        except Exception as e:
            print(f"保存JSON文件失败: {str(e)}")
            sys.exit(1)
    else:
        print(f"分析图像失败: {result.get('message', '未知错误')}")
        sys.exit(1)

# 该模块也可以作为库被导入，che.py可以通过以下方式使用：
# 
# ```python
# from chechuang import ShapeAnalyzer
# 
# analyzer = ShapeAnalyzer()
# result = analyzer.analyze_shape("零件图像.png")
# 
# if result["status"] == "success":
#     shape_features = json.loads(result["shape_features"])
#     # 现在可以获取各种特征值
#     diameter = float(shape_features["长度(mm)"])
#     volume_raw = float(shape_features["毛坯体积(mm³)"])
#     volume_net = float(shape_features["净体积(mm³)"])
#     material_removal = volume_raw - volume_net
# ``` 