import json
import os

# 输入文件夹和输出文件名
INPUT_DIR = "output_data"
OUTPUT_FILE = "merged_data.json"

def merge_json_files(folder, output):
    merged = []
    for filename in os.listdir(folder):
        if filename.endswith('.json'):
            filepath = os.path.join(folder, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # 若文件内容是列表，则将其元素添加到合并列表
                    if isinstance(data, list):
                        merged.extend(data)
                    # 若文件内容是单个对象，则直接添加
                    elif isinstance(data, dict):
                        merged.append(data)
                    else:
                        print(f"警告：文件 {filename} 包含非对象/数组数据，已跳过")
            except Exception as e:
                print(f"错误：无法读取文件 {filename} - {e}")

    with open(output, 'w', encoding='utf-8') as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)
    print(f"合并完成！共 {len(merged)} 条记录，已保存至 {output}")

if __name__ == "__main__":
    merge_json_files(INPUT_DIR, OUTPUT_FILE)