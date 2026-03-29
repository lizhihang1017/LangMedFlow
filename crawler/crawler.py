import requests
from bs4 import BeautifulSoup
import json

def get_case_links(main_url):
    """
    从主页面抓取所有病例详情页链接
    """
    links = []
    try:
        # 1. 发送请求
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(main_url, headers=headers, timeout=10)
        response.raise_for_status()  # 检查请求是否成功
        response.encoding = 'utf-8'  # 设置编码

        # 2. 解析HTML
        soup = BeautifulSoup(response.text, 'html.parser')

        # 3. 定位到容器 (根据您提供的class)
        case_container = soup.find('div', class_='case_database_box')
        if not case_container:
            print("未找到 class='case_database_box' 的容器")
            return links

        # 4. 找到所有class="li"的div，然后提取其中的a标签
        # 使用更精确的选择器：直接在容器下查找特定结构的a标签
        # 根据描述，每个 class="li" 的 div 下有一个 class="name" 的 a 标签
        for li_div in case_container.find_all('div', class_='li'):
            a_tag = li_div.find('a', class_='name')
            if a_tag and a_tag.has_attr('href'):
                href = a_tag['href'].strip()
                # 构建完整URL，注意去除可能存在的多余斜杠
                full_url = requests.compat.urljoin(main_url.rstrip('/').replace('cull','') + '/', href.lstrip('/'))
                links.append(full_url)

        print(f"成功提取到 {len(links)} 个详情页链接。")
        return links

    except requests.exceptions.RequestException as e:
        print(f"网络请求出错: {e}")
        return links
    except Exception as e:
        print(f"解析过程中出现错误: {e}")
        return links

def save_links_to_json(links, filename='case_links.json'):
    """将链接列表保存为JSON文件"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(links, f, ensure_ascii=False, indent=4)
        print(f"链接已保存到文件: {filename}")
    except IOError as e:
        print(f"保存文件时出错: {e}")

if __name__ == "__main__":
    # 主页面URL
    MAIN_URL = "https://bingli.iiyi.com/cull/"

    # 获取所有链接
    all_links = get_case_links(MAIN_URL)

    # 保存为JSON
    if all_links:
        save_links_to_json(all_links)
        # 也可以在控制台打印前几个链接作为预览
        print("前5个链接预览：")
        for i, link in enumerate(all_links[:5]):
            print(f"  {i+1}. {link}")
    else:
        print("未获取到任何链接，请检查页面结构或网络连接。")