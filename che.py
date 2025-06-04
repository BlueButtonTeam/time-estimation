import sys
import json
import math
import io
# from chechuang import ShapeAnalyzer  # 不再导入

# 初始化默认的计算数据结构
default_calculation_data = {
    "times": {
        "turning": {"time": 0, "parameters": {}, "formula": "", "debug_log": []},
        "grinding": {"time": 0, "parameters": {}, "formula": "", "debug_log": []},
        "milling": {"time": 0, "parameters": {}, "formula": "", "debug_log": []},
        "threading": {"time": 0, "parameters": {}, "formula": "", "debug_log": []},
        "total_time": 0
    },
    "input_features": {},
    "general_debug_log": [],
    "material_parameters": {}
}

def debug_print(message):
    """调试信息输出函数，确保输出到stderr"""
    print(f"DEBUG: {message}", file=sys.stderr, flush=True)

def output_result(data, is_error=False):
    """统一的输出处理函数"""
    try:
        if is_error:
            output_data = {
                "error": str(data),
                "details": default_calculation_data
            }
        else:
            output_data = data
        
        debug_print("准备输出数据")
        
        # 将数据转换为JSON字符串
        json_str = json.dumps(output_data, ensure_ascii=False)
        
        # 直接写入到stdout
        print(json_str, flush=True)
        
        debug_print("数据输出完成")
        
        if is_error:
            sys.exit(1)
    except Exception as e:
        debug_print(f"输出处理失败: {str(e)}")
        try:
            error_data = {
                "error": "输出序列化失败",
                "details": str(e)
            }
            print(json.dumps(error_data, ensure_ascii=False), flush=True)
        except:
            print('{"error": "Critical output failure", "details": null}', flush=True)
        sys.exit(1)

def main():
    try:
        debug_print("开始执行主函数")
        
        # 确保标准输出使用UTF-8编码
        if sys.stdout.encoding != 'utf-8':
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        
        # 检查命令行参数
        if len(sys.argv) < 3:
            debug_print("参数数量不足")
            output_result("使用方法: python che.py <材料类型> <分析结果json路径>", is_error=True)
            return

        # 从命令行参数获取材料类型和json路径
        material = sys.argv[1]
        json_path = sys.argv[2]
        
        debug_print(f"材料类型: {material}")
        debug_print(f"JSON文件路径: {json_path}")

        # 读取分析结果json文件
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                shape_features = json.load(f)
                if not isinstance(shape_features, dict):
                    output_result("JSON文件格式错误：应为字典类型", is_error=True)
        except FileNotFoundError:
            output_result(f"找不到JSON文件: {json_path}", is_error=True)
        except json.JSONDecodeError as e:
            output_result(f"JSON文件解析失败: {str(e)}", is_error=True)
        except Exception as e:
            output_result(f"读取JSON文件时发生错误: {str(e)}", is_error=True)

        # 检查必需的字段
        required_fields = ["长度(mm)", "高度(mm)", "毛坯体积(mm³)", "净体积(mm³)"]
        missing_fields = [field for field in required_fields if field not in shape_features]
        if missing_fields:
            output_result(f"缺少必需字段: {', '.join(missing_fields)}", is_error=True)

        # 初始化关键变量
        try:
            d = float(shape_features["长度(mm)"])  # 直径
            h = float(shape_features["高度(mm)"])  # 高度
            quchu_mo = float(shape_features["毛坯体积(mm³)"]) - float(shape_features["净体积(mm³)"])  # 去除量
        except (ValueError, TypeError) as e:
            output_result(f"数值转换错误: {str(e)}", is_error=True)

        # 初始化存储详细信息的字典
        calculation_data = default_calculation_data.copy()
        calculation_data["input_features"] = shape_features

        def log_message(message, section="general_debug_log"):
            if section == "general_debug_log":
                calculation_data["general_debug_log"].append(message)
            elif section in calculation_data["times"]:
                calculation_data["times"][section]["debug_log"].append(message)

        log_message(f"输入参数: 材料={material}, JSON路径={json_path}")
        log_message(f"读取到的特征数据: {json.dumps(shape_features, ensure_ascii=False, indent=2)}")

        # 兼容原有接口
        P_luowen = 0
        L_luowen = 0
        exact_thread_match = False
        if '螺纹规格' in shape_features:
            try:
                thread_spec = float(shape_features['螺纹规格'])
                din933_coarse_pitches_mm = {
                    1: 0.25, 1.1: 0.25, 1.2: 0.25, 1.4: 0.3, 1.6: 0.35, 1.8: 0.35, 2: 0.4,
                    2.2: 0.45, 2.5: 0.45, 3: 0.5, 3.5: 0.6, 4: 0.7, 5: 0.8, 6: 1.0, 7: 1.0,
                    8: 1.25, 10: 1.5, 12: 1.75, 14: 2.0, 16: 2.0, 18: 2.5, 20: 2.5, 22: 2.5,
                    24: 3.0, 27: 3.0, 30: 3.5, 33: 3.5, 36: 4.0, 39: 4.0, 42: 4.5, 45: 4.5,
                    48: 5.0, 52: 5.0, 56: 5.5, 60: 5.5, 64: 6.0, 68: 6.0
                }
                if thread_spec in din933_coarse_pitches_mm:
                    P_luowen = din933_coarse_pitches_mm[thread_spec]
                    exact_thread_match = True
                else:
                    closest_spec = min(din933_coarse_pitches_mm.keys(), key=lambda x: abs(x - thread_spec))
                    P_luowen = din933_coarse_pitches_mm[closest_spec]
                    exact_thread_match = False
                    log_message(f"螺纹规格 M{thread_spec} 未精确匹配，使用最接近的 M{closest_spec} 的螺距 {P_luowen} mm", "threading")
            except Exception as e:
                P_luowen = 0
                exact_thread_match = False
                log_message(f"解析螺纹规格时出错: {str(e)}", "threading")
        if '螺纹长度(mm)' in shape_features:
            try:
                L_luowen = float(shape_features['螺纹长度(mm)'])
            except Exception as e:
                L_luowen = 0
                log_message(f"解析螺纹长度时出错: {str(e)}", "threading")

        # 下面所有加工时间等计算逻辑，全部基于 shape_features 变量

        # 显示从chechuang.py获取的所有数据
        # print("\n从图像分析获取的数据:")
        # print("="*50)
        # print(f"尺寸信息: {shape_features['尺寸信息(mm)']}")
        # print(f"长度(直径): {shape_features['长度(mm)']} mm")
        # print(f"宽度(直径): {shape_features['宽度(mm)']} mm")
        # print(f"高度(厚度): {shape_features['高度(mm)']} mm")
        # print(f"表面积: {shape_features['表面积(mm²)']} mm^2")
        # print(f"毛坯体积: {shape_features['毛坯体积(mm³)']} mm^3")
        # print(f"净体积: {shape_features['净体积(mm³)']} mm^3")

        # 显示螺纹信息
        # if '螺纹规格' in shape_features:
        #     print(f"\n螺纹信息:")
        #     print(f"螺纹规格: M{shape_features['螺纹规格']}")
        #     print(f"螺纹长度: {shape_features.get('螺纹长度(mm)', '未知')} mm")
        #     print(f"螺距(P_luowen): {P_luowen} mm")
        #     if not exact_thread_match:
        #         print("警告: 未能精确匹配螺纹规格，不进行螺纹加工时间计算")
        # else:
        #     print("\n未检测到螺纹特征")

        # 显示表面粗糙度信息
        # if '最严格表面粗糙度' in shape_features:
        #     print(f"\n表面粗糙度信息:")
        #     print(f"最严格表面粗糙度: Ra {shape_features['最严格表面粗糙度']}")
        #     print(f"需要磨削的表面: {shape_features['需要磨削的表面']}")
        #     print(f"Ra≤0.8的表面长度: {shape_features.get('Ra≤0.8的表面长度(mm)', 0)} mm")

        # print("\n几何特征:")
        # print(f"所有面的数量: {shape_features['所有面的数量']}")
        # print(f"平面的数量: {shape_features['平面的数量']}")
        # print(f"曲面的数量: {shape_features['曲面的数量']}")
        # print(f"圆柱面数量: {shape_features['圆柱面数量']}")
        # print(f"圆锥面数量: {shape_features['圆锥面数量']}")
        # print(f"螺旋面数量: {shape_features['螺旋面数量']}")
        # print(f"孔的数量: {shape_features['孔的数量']}")

        # 显示槽特征数据
        # if '槽的数量' in shape_features and int(shape_features['槽的数量']) > 0:
        #     print("\n槽特征数据:")
        #     print(f"槽的数量: {shape_features['槽的数量']}")
        #     print(f"槽特征总体积: {shape_features['槽特征总体积(mm³)']} mm^3")
        #     try:
        #         for i, slot in enumerate(shape_features['槽特征']):
        #             print(f"\n槽 #{i+1}:")
        #             for key, value in slot.items():
        #                 display_key = key.replace('(mm³)', '(mm^3)').replace('(mm²)', '(mm^2)')
        #                 print(f"  {display_key}: {value}")
        #     except Exception as e:
        #         print(f"处理槽特征数据时出错: {str(e)}")
        #         # 为了确保调试信息本身不引发编码错误，对json.dumps也进行处理
        #         # 但更安全的做法是避免在GBK环境下直接dump包含非GBK兼容字符的复杂结构
        #         # 这里我们假设主要问题在主打印逻辑，如果此处仍然报错，可能需要进一步简化此处的调试输出
        #         try:
        #             print("原始槽特征数据 (尝试安全打印):", json.dumps(shape_features['槽特征'], ensure_ascii=True, indent=2))
        #         except Exception as dump_e:
        #             print(f"尝试打印原始槽特征数据失败: {str(dump_e)}")
        #             print("未能显示原始槽特征数据。")
        # else:
        #     print("\n未检测到槽特征")

        # print("="*50)

        # 获取用于计算的数据
        # try:
        #     print("\n检查必需字段:")
        #     required_fields = ["长度(mm)", "高度(mm)", "毛坯体积(mm³)", "净体积(mm³)"]
        #     for field in required_fields:
        #         if field not in shape_features:
        #             raise KeyError(f"缺少必需字段: {field}")
        #         display_field = field.replace('(mm³)', '(mm^3)').replace('(mm²)', '(mm^2)')
        #         print(f"{display_field}: {shape_features[field]}")
        #     
        #     d = float(shape_features["长度(mm)"])  # 直径
        #     h = float(shape_features["高度(mm)"])  # 高度
        #     quchu = float(shape_features["毛坯体积(mm³)"]) - float(shape_features["净体积(mm³)"])  # 去除量
        #     
        #     print(f"\n计算的基本参数:")
        #     print(f"直径(d): {d} mm")
        #     print(f"高度(h): {h} mm")
        #     print(f"去除量: {quchu} mm^3")
        #     
        # except (KeyError, ValueError, TypeError) as e:
        #     print(f"\n数据处理错误: {str(e)}")
        #     print("请检查JSON数据中的必需字段和数值格式")
        #     sys.exit(1)

        # 计算磨削层体积 (直径增加0.05mm后的体积差)
        d_plus = float(shape_features["长度(mm)"]) + 0.05  # 增加0.05mm后的直径

        # 使用Ra≤0.8的表面长度计算磨削体积
        ra_surface_length = float(shape_features.get("Ra≤0.8的表面长度(mm)", 0))

        # 只有当Ra≤0.8的表面长度大于0时才进行磨削计算
        if ra_surface_length > 0:
            # 使用Ra≤0.8的表面长度计算磨削体积
            volume_original = math.pi * (float(shape_features["长度(mm)"])/2)**2 * ra_surface_length  # 原始体积
            volume_plus = math.pi * (d_plus/2)**2 * ra_surface_length  # 增加后的体积
            quchu_mo = volume_plus - volume_original  # 磨削层体积
        else:
            # 如果没有Ra≤0.8的表面长度，则不进行磨削计算
            ra_surface_length = 0
            quchu_mo = 0  # 没有磨削去除量
            # print("\n注意：未检测到Ra≤0.8的表面，不进行磨削计算")

        # 从槽特征中获取铣削加工的去除量
        quchu_xi = 0
        if '槽特征总体积(mm³)' in shape_features:
            quchu_xi = float(shape_features.get('槽特征总体积(mm³)', 0))

        # 根据槽的尺寸计算铣刀直径
        D_xi = 10  # 默认铣刀直径 (mm)
        z_xi = 2   # 铣刀齿数

        # 如果有槽特征，根据槽的最小尺寸确定铣刀直径
        if '槽特征' in shape_features and len(shape_features['槽特征']) > 0:
            min_dimensions = []
            for slot in shape_features['槽特征']:
                # 获取槽的三个尺寸
                length = float(slot.get('长度(mm)', 100))
                width = float(slot.get('宽度(mm)', 100))
                depth = float(slot.get('深度(mm)', 100))
                # 找出最小尺寸
                min_dim = min(length, width, depth)
                min_dimensions.append(min_dim)
            # 使用所有槽中最小尺寸的最小值计算铣刀直径
            if min_dimensions:
                smallest_dimension = min(min_dimensions)
                D_xi = smallest_dimension / 5  # 最小尺寸除以5作为铣刀直径
                # 确保铣刀直径在合理范围内
                D_xi = max(3, min(D_xi, 20))  # 最小3mm，最大20mm
                # print(f"计算所得铣刀直径: {D_xi} mm")

        # print("\n用于计算的数据:")
        # print(f"零件直径(d): {d} mm")
        # print(f"零件高度(h): {h} mm")
        # print(f"Ra≤0.8的表面长度: {ra_surface_length} mm")

        # 材料去除率
        material_params_defined = False
        if material == '不锈钢304' or material == '加工-不锈钢304':
            # 车削参数
            mrr_cu_canshu={'切削速度':130,'进给量':0.25,'切削深度':2.5}
            mrr_jing_canshu={'切削速度':150,'进给量':0.12,'切削深度':0.5}
            # 铣削参数 (Vc, fz, ap, ae)
            mrr_xi_cu_canshu={'切削速度':110,'每齿进给量':0.12,'轴向切深':5,'径向切宽':25} # ae=25 假设 D=50mm 时为 50%ae
            mrr_xi_jing_canshu={'切削速度':140,'每齿进给量':0.08,'轴向切深':0.5,'径向切宽':5}  # ae=5 假设 D=50mm 时为 10%ae
            # 磨削参数
            mrr_cu_mo={'径向磨深':0.01,'轴向每转进给':1.25,'工件线速度':14,'砂轮线速度':31.5} # fa 单位改为 mm/min 或和 nw 匹配计算? 假设为mm/min
            mrr_jing_mo={'径向磨深':0.003,'轴向每转进给':0.6,'工件线速度':12,'砂轮线速度':35} # 假设为mm/min
            luowen_canshu={'切削速度':80, 'N_passes_est': 12}
            material_params_defined = True
        elif material =='不锈钢316' or material == '加工-不锈钢316':
            mrr_cu_canshu={'切削速度':120,'进给量':0.25,'切削深度':2.25}
            mrr_jing_canshu={'切削速度':140,'进给量':0.11,'切削深度':0.45}
            mrr_xi_cu_canshu={'切削速度':100,'每齿进给量':0.11,'轴向切深':4.5,'径向切宽':25}
            mrr_xi_jing_canshu={'切削速度':130,'每齿进给量':0.07,'轴向切深':0.4,'径向切宽':5}
            mrr_cu_mo={'径向磨深':0.01,'轴向每转进给':1.25,'工件线速度':14,'砂轮线速度':31.5}
            mrr_jing_mo={'径向磨深':0.003,'轴向每转进给':0.6,'工件线速度':12,'砂轮线速度':35}
            luowen_canshu={'切削速度':70, 'N_passes_est': 14}
            material_params_defined = True
        elif material =='合金钢' or material == '加工-合金钢': # 假设为中等硬度合金钢
            mrr_cu_canshu={'切削速度':160,'进给量':0.3,'切削深度':3.25}
            mrr_jing_canshu={'切削速度':200,'进给量':0.13,'切削深度':0.6}
            mrr_xi_cu_canshu={'切削速度':100,'每齿进给量':0.15,'轴向切深':6,'径向切宽':30} # 取决于硬度
            mrr_xi_jing_canshu={'切削速度':140,'每齿进给量':0.10,'轴向切深':0.5,'径向切宽':6}
            mrr_cu_mo={'径向磨深':0.012,'轴向每转进给':1.6,'工件线速度':17,'砂轮线速度':38}
            mrr_jing_mo={'径向磨深':0.003,'轴向每转进给':0.8,'工件线速度':14,'砂轮线速度':43}
            luowen_canshu={'切削速度':90, 'N_passes_est': 10}
            material_params_defined = True
        elif material =='塑料' or material == '加工-塑料': # 例如 POM, Nylon
            mrr_cu_canshu={'切削速度':225,'进给量':0.27,'切削深度':3.5}
            mrr_jing_canshu={'切削速度':300,'进给量':0.1,'切削深度':0.55}
            mrr_xi_cu_canshu={'切削速度':300,'每齿进给量':0.25,'轴向切深':8,'径向切宽':35} # 需要锋利刀具
            mrr_xi_jing_canshu={'切削速度':400,'每齿进给量':0.15,'轴向切深':1,'径向切宽':5}
            # 塑料通常不磨削
            mrr_cu_mo={'径向磨深':0,'轴向每转进给':0,'工件线速度':0,'砂轮线速度':0}
            mrr_jing_mo={'径向磨深':0,'轴向每转进给':0,'工件线速度':0,'砂轮线速度':0}
            luowen_canshu={'切削速度':150, 'N_passes_est': 6}
            material_params_defined = True
        elif material =='碳钢' or material == '加工-碳钢': # 例如 中碳钢
            mrr_cu_canshu={'切削速度':215,'进给量':0.35,'切削深度':3.75}
            mrr_jing_canshu={'切削速度':250,'进给量':0.15,'切削深度':0.75}
            mrr_xi_cu_canshu={'切削速度':180,'每齿进给量':0.20,'轴向切深':7,'径向切宽':35}
            mrr_xi_jing_canshu={'切削速度':240,'每齿进给量':0.12,'轴向切深':0.8,'径向切宽':7}
            mrr_cu_mo={'径向磨深':0.014,'轴向每转进给':2.0,'工件线速度':20,'砂轮线速度':35} # 原轴向每转进给是2，这里按 mm/min 理解
            mrr_jing_mo={'径向磨深':0.004,'轴向每转进给':1.0,'工件线速度':16,'砂轮线速度':38} # 原轴向每转进给是1，这里按 mm/min 理解
            luowen_canshu={'切削速度':120, 'N_passes_est': 8}
            material_params_defined = True
        elif material =='铜合金' or material == '加工-铜合金': # 例如 黄铜/青铜
            mrr_cu_canshu={'切削速度':265,'进给量':0.3,'切削深度':3}
            mrr_jing_canshu={'切削速度':325,'进给量':0.13,'切削深度':0.6}
            mrr_xi_cu_canshu={'切削速度':250,'每齿进给量':0.18,'轴向切深':6,'径向切宽':30}
            mrr_xi_jing_canshu={'切削速度':350,'每齿进给量':0.10,'轴向切深':0.6,'径向切宽':6}
            mrr_cu_mo={'径向磨深':0.01,'轴向每转进给':1.2,'工件线速度':24,'砂轮线速度':30}
            mrr_jing_mo={'径向磨深':0.003,'轴向每转进给':1.1,'工件线速度':20,'砂轮线速度':34}
            luowen_canshu={'切削速度':180, 'N_passes_est': 7}
            material_params_defined = True
        elif material =='铝合金6061' or material == '加工-铝合金6061':
            mrr_cu_canshu={'切削速度':375,'进给量':0.37,'切削深度':5.25}
            mrr_jing_canshu={'切削速度':450,'进给量':0.17,'切削深度':0.6}
            mrr_xi_cu_canshu={'切削速度':400,'每齿进给量':0.30,'轴向切深':10,'径向切宽':40} # 需要专用刀具防粘刀
            mrr_xi_jing_canshu={'切削速度':600,'每齿进给量':0.15,'轴向切深':1,'径向切宽':8}
            mrr_cu_mo={'径向磨深':0.017,'轴向每转进给':2.25,'工件线速度':28,'砂轮线速度':30}
            mrr_jing_mo={'径向磨深':0.005,'轴向每转进给':1.2,'工件线速度':24,'砂轮线速度':34}
            luowen_canshu={'切削速度':250, 'N_passes_est': 5}
            material_params_defined = True
        else:
            error_msg = f"未知材料类型: {material}"
            output_result(error_msg, is_error=True)

        if not material_params_defined:
            error_msg = f"材料参数未定义: {material}"
            output_result(error_msg, is_error=True)

        # 计算材料去除率
        mrr_cu=mrr_cu_canshu['切削速度']*mrr_cu_canshu['进给量']*mrr_cu_canshu['切削深度']*1000/60
        mrr_jing=mrr_jing_canshu['切削速度']*mrr_jing_canshu['进给量']*mrr_jing_canshu['切削深度']*1000/60
        
        # 修改计算逻辑，增加基础时间和系数
        # 1. 增加基础准备时间（夹具装夹、对刀等）
        base_setup_time = 300  # 基础准备时间，单位秒
        
        # 2. 修改原来的计算公式，添加更合理的系数
        # 原公式：mrr = quchu_mo/mrr_cu*0.8 + quchu_mo/mrr_jing*0.2
        raw_process_time = quchu_mo/mrr_cu*0.8 + quchu_mo/mrr_jing*0.2
        
        # 3. 针对零件直径和长度添加额外时间因素
        diameter_factor = 1.0 + (d / 100)  # 直径因子，直径越大加工难度越大
        length_factor = 1.0 + (h / 200)    # 长度因子，长度越大加工难度越大
        
        # 4. 计算总的车削加工时间
        mrr = base_setup_time + raw_process_time * 1.5 * diameter_factor * length_factor

        # 存储车削参数
        calculation_data["times"]["turning"]["parameters"] = {
            "粗加工材料去除率": mrr_cu,
            "精加工材料去除率": mrr_jing,
            "切削速度": mrr_cu_canshu['切削速度'],
            "进给量": mrr_cu_canshu['进给量'],
            "切削深度": mrr_cu_canshu['切削深度'],
            "基础准备时间": base_setup_time,
            "原始加工时间": raw_process_time,
            "直径因子": diameter_factor,
            "长度因子": length_factor,
            "总系数": 1.5 * diameter_factor * length_factor
        }
        calculation_data["times"]["turning"]["time"] = mrr
        calculation_data["times"]["turning"]["formula"] = "车削时间 = 基础准备时间 + (粗加工时间*0.8 + 精加工时间*0.2) * 系数"

        # 计算磨削参数
        if quchu_mo > 0:
            nw = (mrr_cu_mo['工件线速度']*1000)/(3.14159*float(shape_features["长度(mm)"])) if float(shape_features["长度(mm)"]) > 0 else 0
            mrr_cumo = (float(shape_features["长度(mm)"])*3.14159*mrr_cu_mo['径向磨深']*mrr_cu_mo['轴向每转进给']*nw)/60 if float(shape_features["长度(mm)"]) > 0 and nw > 0 else 0
            mrr_jingmo = (float(shape_features["长度(mm)"])*3.14159*mrr_jing_mo['径向磨深']*mrr_jing_mo['轴向每转进给']*nw)/60 if float(shape_features["长度(mm)"]) > 0 and nw > 0 else 0
            
            if mrr_cumo > 0 and mrr_jingmo > 0:
                # 计算磨削加工时间并添加基础准备时间
                grinding_base_time = 240  # 磨削准备时间(秒)
                raw_grinding_time = quchu_mo/mrr_cumo*0.6 + quchu_mo/mrr_jingmo*0.4
                mrr_mo = grinding_base_time + raw_grinding_time * 1.2  # 增加20%的系数
            else:
                mrr_mo = 0
        else:
            nw = 0
            mrr_cumo = 0
            mrr_jingmo = 0
            mrr_mo = 0

        # 存储磨削参数
        calculation_data["times"]["grinding"]["parameters"] = {
            "工件转速": nw,
            "粗加工材料去除率": mrr_cumo,
            "精加工材料去除率": mrr_jingmo,
            "径向磨深": mrr_cu_mo['径向磨深'],
            "轴向进给": mrr_cu_mo['轴向每转进给'],
            "表面线速度": mrr_cu_mo['工件线速度'],
            "基础准备时间": grinding_base_time if quchu_mo > 0 and mrr_cumo > 0 and mrr_jingmo > 0 else 0,
            "系数": 1.2
        }
        calculation_data["times"]["grinding"]["time"] = mrr_mo
        calculation_data["times"]["grinding"]["formula"] = "磨削时间 = 基础准备时间 + (粗磨时间*0.6 + 精磨时间*0.4) * 系数"

        # 初始化铣削时间和 MRR 变量
        t_xi_s = 0.0        # 铣削总时间 (秒)
        mrr_xi_cu_s = 0.0   # 粗铣 MRR (mm³/s)
        mrr_xi_jing_s = 0.0 # 精铣 MRR (mm³/s)
        n_xi_cu = 0.0
        n_xi_jing = 0.0

        # 仅在铣削去除量大于 0 时进行计算
        if quchu_xi > 0 and D_xi > 0:
            # --- 计算粗铣 MRR (mm³/s) ---
            try:
                Vc_xi_cu = mrr_xi_cu_canshu['切削速度']
                fz_xi_cu = mrr_xi_cu_canshu['每齿进给量']
                ap_xi_cu = mrr_xi_cu_canshu['轴向切深']
                ae_xi_cu = mrr_xi_cu_canshu['径向切宽']

                # 计算粗铣主轴转速 n (RPM)
                n_xi_cu = (Vc_xi_cu * 1000) / (math.pi * D_xi)

                # 计算粗铣 MRR (mm³/s) = (ap * ae * fz * z * n) / 60
                if n_xi_cu > 0 and z_xi > 0:
                    # 先计算 mm³/min
                    mrr_xi_cu_min = ap_xi_cu * ae_xi_cu * fz_xi_cu * z_xi * n_xi_cu
                    # 再转换为 mm³/s
                    mrr_xi_cu_s = mrr_xi_cu_min / 60
                else:
                    mrr_xi_cu_s = 0 # 转速或齿数为0，无法计算MRR
            except KeyError as e:
                debug_print(f"计算粗铣MRR时缺少参数: {e}")
                mrr_xi_cu_s = 0
            except ZeroDivisionError:
                debug_print("计算粗铣转速时发生除零错误 (铣刀直径 D_xi 不能为零)")
                mrr_xi_cu_s = 0

            # --- 计算精铣 MRR (mm³/s) ---
            try:
                Vc_xi_jing = mrr_xi_jing_canshu['切削速度']
                fz_xi_jing = mrr_xi_jing_canshu['每齿进给量']
                ap_xi_jing = mrr_xi_jing_canshu['轴向切深']
                ae_xi_jing = mrr_xi_jing_canshu['径向切宽']

                # 计算精铣主轴转速 n (RPM)
                n_xi_jing = (Vc_xi_jing * 1000) / (math.pi * D_xi)

                # 计算精铣 MRR (mm³/s) = (ap * ae * fz * z * n) / 60
                if n_xi_jing > 0 and z_xi > 0:
                    # 先计算 mm³/min
                    mrr_xi_jing_min = ap_xi_jing * ae_xi_jing * fz_xi_jing * z_xi * n_xi_jing
                    # 再转换为 mm³/s
                    mrr_xi_jing_s = mrr_xi_jing_min / 60
                else:
                    mrr_xi_jing_s = 0 # 转速或齿数为0，无法计算MRR
            except KeyError as e:
                debug_print(f"计算精铣MRR时缺少参数: {e}")
                mrr_xi_jing_s = 0
            except ZeroDivisionError:
                debug_print("计算精铣转速时发生除零错误 (铣刀直径 D_xi 不能为零)")
                mrr_xi_jing_s = 0

            # --- 计算铣削时间 (s) - 基于体积分配的简化模型 ---
            # 假设粗铣去除 90% 体积，精铣去除 10% 体积
            quchu_xi_cu = quchu_xi * 0.8
            quchu_xi_jing = quchu_xi * 0.2

            t_xi_cu_s = 0.0
            t_xi_jing_s = 0.0

            if mrr_xi_cu_s > 0:
                t_xi_cu_s = quchu_xi_cu / mrr_xi_cu_s # 时间单位是 s
            else:
                if quchu_xi_cu > 0:
                    debug_print("警告：粗铣去除量大于0，但粗铣MRR(mm³/s)计算为0，无法估算粗铣时间。")

            if mrr_xi_jing_s > 0:
                t_xi_jing_s = quchu_xi_jing / mrr_xi_jing_s # 时间单位是 s
            else:
                if quchu_xi_jing > 0:
                    debug_print("警告：精铣去除量大于0，但精铣MRR(mm³/s)计算为0，无法估算精铣时间。")

            # 添加铣削基础准备时间
            milling_base_time = 270  # 铣削准备时间(秒)
            
            # 根据槽的数量增加调整时间
            slot_count = int(shape_features.get("槽的数量", 0))
            slot_setup_time = slot_count * 60  # 每个槽增加60秒调整时间

            # 总铣削时间 (秒)
            t_xi_s = milling_base_time + slot_setup_time + (t_xi_cu_s + t_xi_jing_s) * 1.3  # 增加30%的系数
            
            # 总加工时间（秒）
            time = mrr + mrr_mo + t_xi_s

        # P_luowen已经在前面从analyze_shape结果中获取
        V_rapid = 5000
        # --- 计算螺纹加工时间 (s) ---
        t_luowen_s = 0.0
        n_luowen = 0.0
        Vf_luowen = 0.0 # 轴向进给速度 mm/min

        # L_luowen已经在前面从analyze_shape结果中获取

        # 仅在必要参数有效且精确匹配螺纹规格时计算
        if L_luowen > 0 and P_luowen > 0 and float(shape_features["长度(mm)"]) > 0 and exact_thread_match:
            try:
                Vc_luowen = luowen_canshu['切削速度']
                N_passes_est = luowen_canshu['N_passes_est']

                n_luowen = (Vc_luowen * 1000) / (math.pi * float(shape_features["长度(mm)"]))

                if n_luowen > 0 and N_passes_est > 0:
                    Vf_luowen = P_luowen * n_luowen

                    time_cutting_per_pass_s = 0.0
                    if Vf_luowen > 0:
                        time_cutting_per_pass_s = (L_luowen / Vf_luowen) * 60

                    time_retract_per_pass_s = 0.0
                    if V_rapid > 0:
                        time_retract_per_pass_s = (L_luowen / V_rapid) * 60

                    # 添加螺纹加工基础准备时间
                    threading_base_time = 180  # 螺纹加工准备时间(秒)
                    raw_threading_time = N_passes_est * (time_cutting_per_pass_s + time_retract_per_pass_s)
                    t_luowen_s = threading_base_time + raw_threading_time * 1.25  # 增加25%的系数
                    
                    # 输出螺纹加工计算参数
                    # print("\n螺纹加工计算参数:")
                    # print(f"螺纹规格: M{shape_features.get('螺纹规格', '未知')}")
                    # print(f"螺距(P_luowen): {P_luowen} mm")
                    # print(f"螺纹长度(L_luowen): {L_luowen} mm")
                    # print(f"切削速度: {Vc_luowen} m/min")
                    # print(f"主轴转速: {n_luowen:.2f} RPM")
                    # print(f"进给速度: {Vf_luowen:.2f} mm/min")
                    # print(f"切削次数: {N_passes_est}")
                    # print(f"快速移动速度: {V_rapid} mm/min")

            except KeyError as e:
                debug_print(f"计算螺纹时间时缺少参数: {e}")
                t_luowen_s = 0.0
            except ZeroDivisionError:
                debug_print("计算螺纹时间时发生除零错误 (直径、转速或快移速度可能为零)")
                t_luowen_s = 0.0
        else:
            if not exact_thread_match and '螺纹规格' in shape_features:
                debug_print("\n警告：未能精确匹配到螺纹规格M{}，螺纹加工时间设为0。".format(shape_features.get('螺纹规格', '')))
            elif L_luowen <= 0 or P_luowen <= 0 or float(shape_features["长度(mm)"]) <= 0:
                debug_print("\n警告：螺纹长度、螺距或直径参数无效，螺纹加工时间设为0。")
            else:
                debug_print("\n警告：无法计算螺纹加工时间，时间设为0。")
            t_luowen_s = 0.0

        time = mrr + mrr_mo + t_xi_s + t_luowen_s

        # 修改打印语句为调试日志
        debug_print(f"""
计算结果:
车床加工时间估计: {mrr:.2f} s
磨削加工时间估计: {mrr_mo:.2f} s
铣削加工时间估计: {t_xi_s:.2f} s
螺纹加工时间估计: {t_luowen_s:.2f} s
总加工时间估计: {time:.2f} s
""")

        # 检查槽特征数据
        if "槽特征" in shape_features:
            try:
                slots = shape_features["槽特征"]
                if not isinstance(slots, list):
                    raise TypeError("槽特征必须是数组格式")
                
                debug_print(f"槽特征数量: {len(slots)}")
                for i, slot in enumerate(slots):
                    debug_print(f"\n槽 {i+1}:")
                    required_slot_fields = ["类型", "长度(mm)", "宽度(mm)", "深度(mm)"]
                    for field in required_slot_fields:
                        if field not in slot:
                            raise KeyError(f"槽 {i+1} 缺少必需字段: {field}")
                        debug_print(f"{field}: {slot[field]}")
                    
                    # 验证数值字段
                    for field in ["长度(mm)", "宽度(mm)", "深度(mm)"]:
                        try:
                            float(slot[field])
                        except (ValueError, TypeError):
                            raise ValueError(f"槽 {i+1} 的 {field} 不是有效的数值")
            
            except Exception as e:
                error_msg = f"槽特征数据错误: {str(e)}"
                output_result(error_msg, is_error=True)
        else:
            debug_print("\n未找到槽特征数据")

        # 存储螺纹加工参数
        calculation_data["times"]["threading"]["parameters"] = {
            "螺距": P_luowen,
            "螺纹长度": L_luowen,
            "主轴转速": n_luowen,
            "进给速度": Vf_luowen,
            "切削速度": luowen_canshu['切削速度'] if 'luowen_canshu' in locals() else 0,
            "加工次数": luowen_canshu['N_passes_est'] if 'luowen_canshu' in locals() else 0,
            "精确匹配螺纹规格": exact_thread_match,
            "基础准备时间": threading_base_time if 'threading_base_time' in locals() and L_luowen > 0 and P_luowen > 0 and exact_thread_match else 0,
            "原始加工时间": raw_threading_time if 'raw_threading_time' in locals() and L_luowen > 0 and P_luowen > 0 and exact_thread_match else 0,
            "系数": 1.25
        }
        calculation_data["times"]["threading"]["time"] = t_luowen_s
        calculation_data["times"]["threading"]["formula"] = "螺纹时间 = 基础准备时间 + (切削次数 * (进给时间 + 快速返回时间)) * 系数"

        # 计算总时间
        total_time = mrr + mrr_mo + t_xi_s + t_luowen_s
        calculation_data["times"]["total_time"] = total_time

        # 存储铣削参数
        calculation_data["times"]["milling"]["parameters"] = {
            "刀具直径": D_xi,
            "粗加工主轴转速": n_xi_cu,
            "精加工主轴转速": n_xi_jing,
            "粗加工材料去除率": mrr_xi_cu_s,
            "精加工材料去除率": mrr_xi_jing_s,
            "切削速度": mrr_xi_cu_canshu['切削速度'],
            "每齿进给量": mrr_xi_cu_canshu['每齿进给量'],
            "轴向切深": mrr_xi_cu_canshu['轴向切深'],
            "径向切宽": mrr_xi_cu_canshu['径向切宽'],
            "基础准备时间": milling_base_time if quchu_xi > 0 else 0,
            "槽数量": slot_count if 'slot_count' in locals() else 0,
            "槽调整时间": slot_setup_time if 'slot_setup_time' in locals() else 0,
            "系数": 1.3
        }
        calculation_data["times"]["milling"]["time"] = t_xi_s
        calculation_data["times"]["milling"]["formula"] = "铣削时间 = 基础准备时间 + 槽调整时间 + (粗铣时间 + 精铣时间) * 系数"

        # 最终输出
        output_result(calculation_data)

    except Exception as e:
        output_result(f"计算过程中发生未预期的错误: {str(e)}", is_error=True)

if __name__ == "__main__":
    debug_print("脚本开始执行")
    main()
    debug_print("脚本执行完成")