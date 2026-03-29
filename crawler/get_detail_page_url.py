import requests
from bs4 import BeautifulSoup
import json
import time


def create_session():
    """创建带有完整请求头的会话"""
    session = requests.Session()

    # 完整的请求头，模拟浏览器
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 Edg/144.0.0.0',
        'Accept': 'application/json, text/javascript, */*; q=0.01',
        'Accept-Encoding': 'gzip, deflate, br',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8,en-GB;q=0.7,en-US;q=0.6',
        'Connection': 'keep-alive',
        'Host': 'bingli.iiyi.com',
        'Origin': 'https://bingli.iiyi.com',
        'X-Requested-With': 'XMLHttpRequest',
        'Sec-Ch-Ua': '"Not(A:Brand";v="8", "Chromium";v="144", "Microsoft Edge";v="144"',
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-origin',
    })

    return session


def extract_links_from_html(html_content):
    """从HTML中提取病例详情页链接"""
    links = []
    soup = BeautifulSoup(html_content, 'html.parser')

    # 方法1: 直接查找所有class="name"的a标签
    for a_tag in soup.find_all('a', class_='name'):
        if a_tag and a_tag.has_attr('href'):
            href = a_tag['href'].strip()
            full_url = requests.compat.urljoin('https://bingli.iiyi.com/', href)
            links.append(full_url)

    # 方法2: 如果没找到，尝试通过容器查找
    if not links:
        case_container = soup.find('div', class_='case_database_box')
        if case_container:
            for li_div in case_container.find_all('div', class_='li'):
                a_tag = li_div.find('a', class_='name')
                if a_tag and a_tag.has_attr('href'):
                    href = a_tag['href'].strip()
                    full_url = requests.compat.urljoin('https://bingli.iiyi.com/', href)
                    links.append(full_url)

    return links


def get_links_from_page(session, page_url, page_number, referer_url):
    """
    向指定的分页URL发送请求，并提取该页的链接
    """
    try:
        print(f"正在抓取第 {page_number} 页: {page_url}")

        # 更新Referer头
        session.headers.update({'Referer': referer_url})

        # 第一页用GET，后续分页用POST
        if page_number == 1:
            response = session.get(page_url, timeout=15)
            response.encoding = 'utf-8'
            html_content = response.text

            # 保存Cookie用于后续请求
            if 'Set-Cookie' in response.headers:
                print("已获取Cookie")
        else:
            # POST请求，可能需要设置Content-Type
            session.headers.update({
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'Content-Length': '0'  # 明确设置为0
            })

            response = session.post(page_url, timeout=15)
            print(response)
            response.encoding = 'utf-8'

            # 尝试解析为JSON
            try:
                if response.text.strip():  # 确保响应不为空
                    json_data = response.json()
                    print(f"JSON响应结构: {list(json_data.keys()) if isinstance(json_data, dict) else '不是字典'}")

                    # 从JSON中提取HTML片段
                    if isinstance(json_data, dict) and 'data' in json_data and 'html' in json_data['data']:
                        html_content = json_data['data']['html']
                    elif isinstance(json_data, dict) and 'html' in json_data:
                        html_content = json_data['html']
                    elif isinstance(json_data, dict) and 'list' in json_data:
                        # 可能是其他结构
                        html_content = str(json_data)  # 转换为字符串再处理
                    else:
                        print(f"JSON格式不符合预期: {json_data[:200] if len(str(json_data)) > 200 else json_data}")
                        return None
                else:
                    print("响应为空")
                    return None
            except json.JSONDecodeError:
                # 如果不是JSON，可能是HTML
                html_content = response.text
                print(f"响应不是JSON，可能是HTML，长度: {len(html_content)}")
            except Exception as e:
                print(f"解析响应时出错: {e}")
                print(f"响应内容前500字符: {response.text[:500]}")
                return None

        # 提取链接
        page_links = extract_links_from_html(html_content)

        if page_links:
            print(f"  第 {page_number} 页成功提取到 {len(page_links)} 个链接。")
            return page_links
        else:
            print(f"  第 {page_number} 页未提取到链接。")
            print(f"  响应预览: {html_content[:500] if html_content else '空响应'}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"  请求第 {page_number} 页时出错: {e}")
        return None
    except Exception as e:
        print(f"  处理第 {page_number} 页时发生意外错误: {e}")
        return None


def get_all_case_links(start_url, max_pages=20):
    """
    主函数：从起始页开始，自动遍历所有分页以获取全部链接
    """
    # 创建会话
    session = create_session()
    all_links = []

    # 1. 抓取第一页
    print("=" * 50)
    print("开始抓取起始页...")
    first_page_links = get_links_from_page(session, start_url, 1, start_url)
    if first_page_links:
        all_links.extend(first_page_links)
        print(f"起始页抓取成功，获得 {len(first_page_links)} 个链接。")
    else:
        print("起始页抓取失败，程序终止。")
        return []

    # 2. 抓取后续分页
    print("\n" + "=" * 50)
    print("开始抓取后续分页...")
    base_url = "https://bingli.iiyi.com/cull"

    for page_num in range(2, max_pages + 1):
        # 构建分页URL
        page_url = f"{base_url}/{page_num}.html"

        # 设置Referer为上一页（如果是第二页，Referer为首页）
        if page_num == 2:
            referer = start_url
        else:
            referer = f"{base_url}/{page_num - 1}.html"

        page_links = get_links_from_page(session, page_url, page_num, referer)

        # 判断是否继续
        if page_links is None:
            print(f"第 {page_num} 页抓取失败，尝试下一页...")
            # 继续尝试下一页，可能只是当前页有问题
            time.sleep(2)
            continue
        elif len(page_links) == 0:
            print(f"第 {page_num} 页无链接，停止抓取。")
            break
        else:
            all_links.extend(page_links)

        # 随机延迟，模拟人类行为
        delay = 1.5 + (page_num % 3) * 0.5  # 1.5-3秒之间的随机延迟
        time.sleep(delay)

        # 每5页输出一次进度
        if page_num % 5 == 0:
            print(f"已抓取 {page_num} 页，累计 {len(all_links)} 个链接...")

    # 3. 去重（保持顺序）
    unique_links = []
    seen = set()
    for link in all_links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)

    print("=" * 50)
    print(f"所有页面抓取完成！")
    print(f"原始链接数: {len(all_links)}")
    print(f"去重后链接数: {len(unique_links)}")

    # 关闭会话
    session.close()

    return unique_links


def save_links_to_json(links, filename='all_case_links.json'):
    """将链接列表保存为JSON文件"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(links, f, ensure_ascii=False, indent=4)
        print(f"所有链接已保存到文件: {filename}")
        return True
    except IOError as e:
        print(f"保存文件时出错: {e}")
        return False



if __name__ == "__main__":

    # 设置起始URL（第一页）
    START_URL = "https://bingli.iiyi.com/cull/"
    # 设置一个安全上限
    MAX_PAGES_TO_TRY = 10  # 先测试10页

    print("开始抓取病例链接...")
    final_links = get_all_case_links(START_URL, MAX_PAGES_TO_TRY)

    # 保存为JSON
    if final_links:
        save_links_to_json(final_links)

        # 预览
        print("\n前10个链接预览：")
        for i, link in enumerate(final_links[:10]):
            print(f"  {i + 1}. {link}")

        # 统计信息
        print(f"\n链接统计：")
        print(f"  总链接数：{len(final_links)}")

        # 检查链接格式
        print(f"\n链接格式示例：")
        if final_links:
            sample = final_links[0]
            print(f"  示例：{sample}")
            print(f"  是否包含'show'：{'show' in sample}")
    else:
        print("未获取到任何链接。")
