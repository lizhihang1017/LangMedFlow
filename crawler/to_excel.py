import pandas as pd
import json

def processed(data):
    processed_data = []
    for item in data:
        record = {}

        # 顶层字段
        record['标题'] = item.get('标题', '')
        record['科室'] = item.get('科室', '')
        record['病例摘要'] = item.get('病例摘要', '')
        record['分析总结'] = item.get('分析总结', '')
        record['url'] = item.get('url', '')

        # 病案介绍中的所有字段
        bingan = item.get('病案介绍', {})
        if isinstance(bingan, dict):
            for key, value in bingan.items():
                record[f'{key}(病案介绍)'] = str(value) if not isinstance(value, str) else value

        # 诊治过程中的所有字段
        zhenszhi = item.get('诊治过程', {})
        if isinstance(zhenszhi, dict):
            for key, value in zhenszhi.items():
                record[f'{key}(诊治过程)'] = str(value) if not isinstance(value, str) else value

        processed_data.append(record)
    return processed_data





if __name__ == '__main__':

    input_file_list = [
        './output_data/xiaohua_details_data.json',
        './output_data/xinxueguan_details_data.json',
        './output_data/shenzang_details_data.json',
        './output_data/puwai_details_data.json',
        './output_data/gu_details_data.json',
        './output_data/chanke_details_data.json',
        './output_data/fuke_details_data.json',
        './output_data/fukeneifenmi_details_data.json',
        './output_data/fukezhongliu_details_data.json',
        './output_data/gangchangwaike_details_data.json',
        './output_data/miniaowaike_details_data.json',

    ]

    data = []

    for input_file in input_file_list:
        # 读取JSON文件
        with open(input_file, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        data = data + json_data

    processed_data = processed(data)
    data_count = len(processed_data)

    # 转换为DataFrame并保存
    df = pd.DataFrame(processed_data)

    # 保存到Excel
    output_file = './to_excel/data_{}.xlsx'.format(data_count)
    df.to_excel(output_file, index=False)
    print(f"转换完成！文件已保存为: {output_file}")
    print(f"总记录数: {len(df)}")
    print(f"字段数: {len(df.columns)}")
    print("\n字段列表:")
    for col in df.columns:
        print(f"- {col}")

