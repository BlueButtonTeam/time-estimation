from flask import Flask, render_template, request, redirect, url_for, send_from_directory, flash, jsonify
import os
import subprocess
import json
from werkzeug.utils import secure_filename
import time

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'pdf'}

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = 'your_secret_key'

# 材料类型选项
MATERIALS = [
    '不锈钢304', '不锈钢316', '合金钢', '塑料', '碳钢', '铜合金', '铝合金6061'
]

# 字段类型定义
NUMERIC_FIELDS = [
    "长度(mm)", "宽度(mm)", "高度(mm)", "表面积(mm²)", "毛坯体积(mm³)", "净体积(mm³)", "材料去除率(%)",
    "槽的数量", "槽特征总体积(mm³)", "螺纹规格", "螺纹长度(mm)", "Ra≤0.8的表面长度(mm)", "所有面的数量",
    "平面的数量", "曲面的数量", "圆柱面数量", "圆锥面数量", "螺旋面数量", "孔的数量"
]
ARRAY_FIELDS = ["槽特征"]

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        # 获取表单数据
        material = request.form.get('material')
        quantity = int(request.form.get('quantity', 1))
        file = request.files.get('file')
        filename = request.form.get('file')  # 从结果页面返回时的文件名
        
        # 如果是从结果页面返回编辑页面
        if filename and not file:
            json_path = os.path.join(app.config['UPLOAD_FOLDER'], filename.rsplit('.', 1)[0] + '.json')
            if os.path.exists(json_path):
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        shape_features = json.load(f)
                    return render_template('index.html',
                                        step='edit',
                                        filename=filename,
                                        material=material,
                                        quantity=quantity,
                                        shape_features=shape_features,
                                        NUMERIC_FIELDS=NUMERIC_FIELDS,
                                        ARRAY_FIELDS=ARRAY_FIELDS,
                                        materials=MATERIALS)
                except Exception as e:
                    flash(f'读取分析结果JSON文件失败: {str(e)}')
                    return redirect(url_for('index'))
            else:
                flash('未找到分析结果文件，请重新上传图纸！')
                return redirect(url_for('index'))
        
        # 原有的文件上传处理逻辑
        if not file or not allowed_file(file.filename):
            flash('请上传PDF格式的图纸文件！')
            return redirect(request.url)
        if not material:
            flash('请选择材料类型！')
            return redirect(request.url)
        if quantity < 1:
            flash('零件数量必须大于0！')
            return redirect(request.url)
        
        # 保存上传文件
        filename = secure_filename(file.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(pdf_path)
        
        # 标记分析未完成
        status_path = pdf_path + '.status'
        with open(status_path, 'w', encoding='utf-8') as f:
            f.write('processing')
        
        # 启动子进程分析（异步）
        import threading
        def analyze_pdf():
            try:
                subprocess.run(['python', 'chechuang.py', pdf_path], check=True, encoding='utf-8')
                # 标记分析完成
                with open(status_path, 'w', encoding='utf-8') as f:
                    f.write('done')
            except Exception as e:
                with open(status_path, 'w', encoding='utf-8') as f:
                    f.write('error:' + str(e))
        threading.Thread(target=analyze_pdf, daemon=True).start()
        
        # 跳转到processing页面
        return redirect(url_for('processing', filename=filename, material=material, quantity=quantity))
    # GET请求
    return render_template('index.html', step='upload', materials=MATERIALS)

@app.route('/processing')
def processing():
    filename = request.args.get('filename')
    material = request.args.get('material')
    quantity = request.args.get('quantity', 1)
    return render_template('processing.html', filename=filename, material=material, quantity=quantity)

@app.route('/check_status')
def check_status():
    filename = request.args.get('filename')
    pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    status_path = pdf_path + '.status'
    json_path = pdf_path.rsplit('.', 1)[0] + '.json'
    if os.path.exists(status_path):
        with open(status_path, 'r', encoding='utf-8') as f:
            status = f.read().strip()
        if status == 'done' and os.path.exists(json_path):
            return jsonify({'status': 'done'})
        elif status.startswith('error'):
            error_msg = status
            # 检查是否包含API超时错误
            if 'timed out' in status or 'timeout' in status:
                error_msg = "图纸分析超时，可能是由于网络问题或服务器繁忙，请稍后再试。"
            return jsonify({'status': 'error', 'msg': error_msg})
        else:
            return jsonify({'status': 'processing'})
    else:
        return jsonify({'status': 'processing'})

@app.route('/calculate', methods=['POST'])
def calculate():
    filename = request.form.get('filename')
    material = request.form.get('material')
    quantity = int(request.form.get('quantity', 1))
    
    current_shape_features = {} # 用于当计算出错时，回填编辑页面
    error_fields = []
    
    # 从表单重建 shape_features
    for key_form in request.form:
        if key_form.startswith('field_'):
            field_name = key_form[6:]
            value_str = request.form[key_form]
            try:
                if field_name in NUMERIC_FIELDS:
                    if value_str == '' or value_str is None: value = 0
                    elif '.' in value_str: value = float(value_str)
                    else: value = int(value_str)
                elif field_name in ARRAY_FIELDS:
                    try:
                        value = json.loads(value_str) if value_str else []
                    except json.JSONDecodeError as e:
                        error_fields.append(f"{field_name} (JSON格式错误: {str(e)})")
                        value = [] # 或保持原始错误字符串，取决于如何回显
                else: # 文本字段
                    value = value_str
                current_shape_features[field_name] = value
            except ValueError as e:
                error_fields.append(f"{field_name} (数值转换错误: {str(e)})")
                current_shape_features[field_name] = value_str # 保留原始字符串以便编辑
            except Exception as e: # 其他通用错误
                error_fields.append(f"{field_name} (处理错误: {str(e)})")
                current_shape_features[field_name] = value_str

    if error_fields:
        flash(f"提交的特征数据格式错误，请检查：{', '.join(error_fields)}")
        return render_template('index.html', step='edit', filename=filename, material=material, quantity=quantity, 
                               shape_features=current_shape_features, NUMERIC_FIELDS=NUMERIC_FIELDS, 
                               ARRAY_FIELDS=ARRAY_FIELDS, materials=MATERIALS)

    # 保存修改后的特征到JSON文件 (这步很重要，che.py会读取这个文件)
    json_path = os.path.join(app.config['UPLOAD_FOLDER'], filename.rsplit('.', 1)[0] + '.json')
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(current_shape_features, f, ensure_ascii=False, indent=4)
    except Exception as e:
        flash(f'保存修改后的特征数据失败: {str(e)}')
        return render_template('index.html', step='edit', filename=filename, material=material, quantity=quantity, 
                               shape_features=current_shape_features, NUMERIC_FIELDS=NUMERIC_FIELDS, 
                               ARRAY_FIELDS=ARRAY_FIELDS, materials=MATERIALS)

    # 调用che.py计算加工时间
    calculation_details = None
    error_message_from_che = None
    
    try:
        print(f"开始调用che.py: python che.py \"{material}\" \"{json_path}\"")
        print(f"当前工作目录: {os.getcwd()}")
        print(f"检查文件是否存在: {os.path.exists(json_path)}")
        print(f"检查che.py是否存在: {os.path.exists('che.py')}")
        
        # 打印JSON文件内容用于调试
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                json_content = json.load(f)
                print(f"JSON文件内容:\n{json.dumps(json_content, ensure_ascii=False, indent=2)}")
        except Exception as e:
            print(f"读取JSON文件失败: {str(e)}")
        
        # 使用subprocess.run来执行命令
        process = subprocess.run(
            ['python', 'che.py', material, json_path],
            capture_output=True,
            text=True,
            encoding='utf-8',
            env=dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONUNBUFFERED='1')
        )
        
        print(f"进程返回码: {process.returncode}")
        if process.stderr:
            print(f"错误输出:\n{process.stderr}")
        
        # 检查是否有输出
        if not process.stdout:
            error_message_from_che = "计算脚本没有输出任何内容"
            print(error_message_from_che)
            # 检查che.py文件
            try:
                with open('che.py', 'r', encoding='utf-8') as f:
                    print(f"che.py 文件大小: {os.path.getsize('che.py')} 字节")
                    print("che.py 文件前100个字符:")
                    print(f.read(100))
            except Exception as e:
                print(f"检查che.py文件时出错: {str(e)}")
        else:
            print(f"标准输出:\n{process.stdout}")
            try:
                # 尝试解析输出为JSON
                # 移除可能的前导和尾随空白字符
                stdout_cleaned = process.stdout.strip()
                output_data = json.loads(stdout_cleaned)
                
                # 检查是否包含错误信息
                if "error" in output_data:
                    error_message_from_che = output_data["error"]
                    if "details" in output_data:
                        calculation_details = output_data["details"]
                        print(f"che.py 返回错误详情: {json.dumps(output_data['details'], ensure_ascii=False, indent=2)}")
                else:
                    # 如果没有错误，使用输出作为计算结果
                    calculation_details = output_data
                    
                # 验证计算结果的基本结构
                if calculation_details and "times" in calculation_details:
                    if not isinstance(calculation_details["times"], dict):
                        error_message_from_che = "计算结果格式错误：times 字段不是字典类型"
                        calculation_details = None
                else:
                    error_message_from_che = "计算结果缺少必要的 times 字段"
                    calculation_details = None
                    
            except json.JSONDecodeError as e:
                error_message_from_che = f"无法解析计算脚本的输出为JSON: {str(e)}"
                print(f"JSON解析错误位置: {e.pos}")
                print(f"问题行: {e.doc[max(0, e.pos-50):min(len(e.doc), e.pos+50)]}")
                print(f"完整输出内容:\n{process.stdout}")
                    
    except Exception as e:
        error_message_from_che = f"调用计算脚本时发生系统错误: {str(e)}"
        print(error_message_from_che)

    if error_message_from_che:
        flash(f'加工时间计算失败: {error_message_from_che}')
        return render_template('index.html',
                             step='edit',
                             filename=filename,
                             material=material,
                             quantity=quantity,
                             shape_features=current_shape_features,
                             NUMERIC_FIELDS=NUMERIC_FIELDS,
                             ARRAY_FIELDS=ARRAY_FIELDS,
                             materials=MATERIALS,
                             output=error_message_from_che)

    # 如果成功获取计算结果
    return render_template('index.html',
                         step='result',
                         calculation_details=calculation_details,
                         quantity=quantity,
                         filename=filename,
                         material=material)

def seconds_to_hms(seconds):
    seconds = int(round(seconds))
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}小时{m}分{s}秒"
    elif m > 0:
        return f"{m}分{s}秒"
    else:
        return f"{s}秒"

app.jinja_env.filters['hms'] = seconds_to_hms

if __name__ == '__main__':
    app.run(debug=True) 